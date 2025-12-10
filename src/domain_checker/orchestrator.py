"""
Check Orchestrator for the domain checker system.

This module provides the main orchestration layer that coordinates all components
to perform domain availability checks. It integrates:
- Domain validation and normalization
- Rate limiting for registry access
- RDAP and WHOIS clients for data retrieval
- Retry logic for transient errors
- Decision engine for availability determination
- State persistence for tracking results
- Notification routing for alerts

Requirements covered:
- 2.1: Query official RDAP endpoint of the respective registry
- 3.1: Query secondary RDAP when primary indicates availability
- 6.1: Available only with definitive 404 AND secondary confirmation
"""

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .audit_logger import AuditLogger
from .config import SystemConfig, TLDConfig
from .decision_engine import DecisionEngine
from .domain_validator import DomainValidator
from .enums import AvailabilityStatus, LogLevel, RDAPStatus
from .models import CheckMetadata, CheckResult
from .notifications import NotificationPayload, NotificationRouter
from .rate_limiter import RateLimiter
from .rdap_client import RDAPClient, RDAPResponse
from .retry_manager import RetryManager
from .state_store import StateStore
from .whois_client import WHOISClient, WHOISResponse


@dataclass
class OrchestratorResult:
    """Result of an orchestrated domain check."""

    check_result: CheckResult
    notification_sent: bool
    errors: list[str]


class CheckOrchestrator:
    """
    Main orchestrator for domain availability checks.

    Coordinates all system components to perform comprehensive domain
    availability checks with proper rate limiting, retry logic, and
    multi-source validation.
    """

    async def __aenter__(self) -> "CheckOrchestrator":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        pass

    def __init__(
        self,
        config: SystemConfig,
        state_store: Optional[StateStore] = None,
        notification_router: Optional[NotificationRouter] = None,
        logger: Optional[AuditLogger] = None,
    ) -> None:
        """
        Initialize the check orchestrator.

        Args:
            config: System configuration
            state_store: Optional state store for persistence
            notification_router: Optional notification router for alerts
            logger: Optional audit logger for logging
        """
        self._config = config
        self._logger = logger

        # Build TLD lookup maps
        self._tld_configs: dict[str, TLDConfig] = {
            tld_config.tld.lower(): tld_config for tld_config in config.tlds
        }

        # Initialize domain validator with allowed TLDs
        allowed_tlds = [tld_config.tld for tld_config in config.tlds]
        self._domain_validator = DomainValidator(allowed_tlds)

        # Initialize rate limiter
        self._rate_limiter = RateLimiter(config.rate_limits)

        # Initialize retry manager
        self._retry_manager = RetryManager(config.retry)

        # Initialize decision engine
        self._decision_engine = DecisionEngine()

        # Build RDAP endpoint maps
        primary_endpoints = {
            tld_config.tld.lower(): tld_config.rdap_endpoint
            for tld_config in config.tlds
        }
        secondary_endpoints = {
            tld_config.tld.lower(): tld_config.secondary_rdap_endpoint
            for tld_config in config.tlds
            if tld_config.secondary_rdap_endpoint
        }

        # Initialize RDAP clients
        self._rdap_primary = RDAPClient(
            tld_endpoints=primary_endpoints,
            timeout=10.0,
            simulation_mode=config.simulation_mode,
        )
        self._rdap_secondary = RDAPClient(
            tld_endpoints=secondary_endpoints,
            timeout=10.0,
            simulation_mode=config.simulation_mode,
        ) if secondary_endpoints else None

        # Initialize WHOIS client
        whois_servers = {
            tld_config.tld.lower(): tld_config.whois_server
            for tld_config in config.tlds
            if tld_config.whois_server and tld_config.whois_enabled
        }
        self._whois_client = WHOISClient(
            timeout=10.0,
            custom_servers=whois_servers if whois_servers else None,
            simulation_mode=config.simulation_mode,
        )

        # Store optional components
        self._state_store = state_store
        self._notification_router = notification_router

    async def check_domain(self, raw_domain: str) -> OrchestratorResult:
        """
        Perform a complete domain availability check.

        This is the main entry point for domain checking. It:
        1. Validates and normalizes the domain
        2. Queries primary RDAP with rate limiting and retry
        3. If primary indicates availability, queries secondary sources
        4. Evaluates results using conservative decision logic
        5. Persists results and sends notifications if appropriate

        Args:
            raw_domain: The domain to check (can be in any format)

        Returns:
            OrchestratorResult with check result, notification status, and errors
        """
        start_time = time.perf_counter()
        errors: list[str] = []
        retry_count = 0
        rate_limit_delays = 0

        # Step 1: Validate and normalize domain
        validation_result = self._domain_validator.validate(raw_domain)
        if not validation_result.valid:
            self._log_error(
                "DomainValidator",
                f"Domain validation failed: {validation_result.error.message}",
                {"domain": raw_domain, "error": validation_result.error.details},
            )
            # Return TAKEN for invalid domains (conservative approach)
            return self._create_error_result(
                raw_domain,
                f"Validation error: {validation_result.error.message}",
                start_time,
            )

        canonical_domain = validation_result.canonical_domain
        tld = canonical_domain.rsplit(".", 1)[-1].lower()

        self._log_info(
            "CheckOrchestrator",
            f"Starting check for domain: {canonical_domain}",
            {"raw_domain": raw_domain, "canonical": canonical_domain, "tld": tld},
        )

        # Get TLD configuration
        tld_config = self._tld_configs.get(tld)
        if not tld_config:
            return self._create_error_result(
                canonical_domain,
                f"No configuration for TLD: {tld}",
                start_time,
            )

        # Step 2: Query primary RDAP with rate limiting
        primary_result, primary_retries, primary_delays = await self._query_primary_rdap(
            canonical_domain, tld_config
        )
        retry_count += primary_retries
        rate_limit_delays += primary_delays

        if primary_result.error:
            errors.append(f"Primary RDAP error: {primary_result.error.message}")

        # Step 3: Query secondary sources if primary indicates availability
        secondary_result: Optional[RDAPResponse] = None
        whois_result: Optional[WHOISResponse] = None

        if primary_result.status == RDAPStatus.NOT_FOUND:
            # Primary indicates potentially available - need secondary confirmation
            # (Requirement 3.1)
            secondary_result, secondary_retries, secondary_delays = (
                await self._query_secondary_rdap(canonical_domain, tld_config)
            )
            retry_count += secondary_retries
            rate_limit_delays += secondary_delays

            if secondary_result and secondary_result.error:
                errors.append(f"Secondary RDAP error: {secondary_result.error.message}")

            # If secondary is unavailable or errored, try WHOIS fallback
            if (
                secondary_result is None
                or secondary_result.status == RDAPStatus.ERROR
            ) and tld_config.whois_enabled:
                whois_result = await self._query_whois(canonical_domain)
                if whois_result.error:
                    errors.append(f"WHOIS error: {whois_result.error.message}")

        # Step 4: Build check result using decision engine
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        metadata = CheckMetadata(
            total_duration_ms=total_duration_ms,
            retry_count=retry_count,
            rate_limit_delays=rate_limit_delays,
        )

        check_result = self._decision_engine.build_check_result(
            domain=canonical_domain,
            primary_result=primary_result,
            secondary_result=secondary_result,
            whois_result=whois_result,
            metadata=metadata,
        )

        self._log_info(
            "CheckOrchestrator",
            f"Check completed for {canonical_domain}: {check_result.status.value}",
            {
                "domain": canonical_domain,
                "status": check_result.status.value,
                "confidence": check_result.confidence.value,
                "duration_ms": total_duration_ms,
            },
        )

        # Step 5: Persist result and send notifications
        notification_sent = False
        previous_state = None

        if self._state_store:
            previous_state = self._state_store.get_domain_state(canonical_domain)
            self._state_store.update_domain_state(canonical_domain, check_result)
            try:
                self._state_store.save()
            except Exception as e:
                errors.append(f"State save error: {e}")
                self._log_error(
                    "StateStore",
                    f"Failed to save state: {e}",
                    {"domain": canonical_domain},
                )

        if self._notification_router:
            notification_sent = await self._send_notification(
                check_result, previous_state
            )

        return OrchestratorResult(
            check_result=check_result,
            notification_sent=notification_sent,
            errors=errors,
        )

    async def _query_primary_rdap(
        self, domain: str, tld_config: TLDConfig
    ) -> tuple[RDAPResponse, int, int]:
        """
        Query primary RDAP with rate limiting and retry.

        Returns:
            Tuple of (response, retry_count, rate_limit_delay_count)
        """
        endpoint = tld_config.rdap_endpoint
        tld = tld_config.tld.lower()
        rate_limit_delays = 0

        # Acquire rate limit permission
        async with self._rate_limiter.acquire(tld, endpoint) as status:
            if not status.allowed:
                rate_limit_delays += 1
                self._log_info(
                    "RateLimiter",
                    f"Rate limit delay: {status.wait_seconds}s",
                    {"tld": tld, "endpoint": endpoint, "reason": status.reason},
                )
                # Wait for rate limit
                import asyncio
                await asyncio.sleep(status.wait_seconds)

        # Execute with retry
        async def do_query() -> RDAPResponse:
            async with self._rdap_primary:
                return await self._rdap_primary.query(domain, endpoint)

        response, attempts = await self._retry_manager.execute_rdap_with_retry(do_query)

        # Record the request
        self._rate_limiter.record_request(tld, endpoint)

        # Apply adaptive delay if we got rate limited
        if response.http_status_code in (429, 503):
            delay = self._rate_limiter.apply_adaptive_delay(
                tld, endpoint, response.http_status_code
            )
            self._log_info(
                "RateLimiter",
                f"Adaptive delay applied: {delay}s",
                {"tld": tld, "http_status": response.http_status_code},
            )

        return response, attempts - 1, rate_limit_delays

    async def _query_secondary_rdap(
        self, domain: str, tld_config: TLDConfig
    ) -> tuple[Optional[RDAPResponse], int, int]:
        """
        Query secondary RDAP with rate limiting and retry.

        Returns:
            Tuple of (response or None, retry_count, rate_limit_delay_count)
        """
        if not tld_config.secondary_rdap_endpoint or not self._rdap_secondary:
            return None, 0, 0

        endpoint = tld_config.secondary_rdap_endpoint
        tld = tld_config.tld.lower()
        rate_limit_delays = 0

        # Acquire rate limit permission
        async with self._rate_limiter.acquire(tld, endpoint) as status:
            if not status.allowed:
                rate_limit_delays += 1
                import asyncio
                await asyncio.sleep(status.wait_seconds)

        # Execute with retry
        async def do_query() -> RDAPResponse:
            async with self._rdap_secondary:
                return await self._rdap_secondary.query(domain, endpoint)

        response, attempts = await self._retry_manager.execute_rdap_with_retry(do_query)

        # Record the request
        self._rate_limiter.record_request(tld, endpoint)

        return response, attempts - 1, rate_limit_delays

    async def _query_whois(self, domain: str) -> WHOISResponse:
        """Query WHOIS as fallback."""
        return await self._whois_client.query(domain)

    async def _send_notification(
        self, check_result: CheckResult, previous_state
    ) -> bool:
        """
        Send notification if appropriate.

        Returns:
            True if notification was sent, False otherwise
        """
        if not self._notification_router:
            return False

        payload = NotificationPayload(
            domain=check_result.domain,
            status=check_result.status.value,
            timestamp=check_result.timestamp,
            language=self._config.language,
        )

        results = await self._notification_router.notify(
            payload=payload,
            current_status=check_result.status,
            previous_state=previous_state,
        )

        # Check if any notification was sent successfully
        sent = any(r.success for r in results)

        if sent and self._state_store:
            # Mark domain as notified
            self._state_store.mark_notified(
                check_result.domain,
                datetime.now(timezone.utc).isoformat(),
            )

        return sent

    def _create_error_result(
        self, domain: str, error_message: str, start_time: float
    ) -> OrchestratorResult:
        """Create an error result with TAKEN status (conservative approach)."""
        total_duration_ms = (time.perf_counter() - start_time) * 1000

        check_result = CheckResult(
            domain=domain,
            status=AvailabilityStatus.TAKEN,
            confidence=self._decision_engine.determine_confidence(
                AvailabilityStatus.TAKEN, None, None, None
            ),
            sources=[],
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=CheckMetadata(
                total_duration_ms=total_duration_ms,
                retry_count=0,
                rate_limit_delays=0,
            ),
        )

        return OrchestratorResult(
            check_result=check_result,
            notification_sent=False,
            errors=[error_message],
        )

    def _log_info(self, component: str, message: str, data: dict) -> None:
        """Log an info message if logger is available."""
        if self._logger:
            self._logger.log(LogLevel.INFO, component, message, data)

    def _log_error(self, component: str, message: str, data: dict) -> None:
        """Log an error message if logger is available."""
        if self._logger:
            self._logger.log(LogLevel.ERROR, component, message, data)

    @property
    def domain_validator(self) -> DomainValidator:
        """Get the domain validator instance."""
        return self._domain_validator

    @property
    def rate_limiter(self) -> RateLimiter:
        """Get the rate limiter instance."""
        return self._rate_limiter

    @property
    def decision_engine(self) -> DecisionEngine:
        """Get the decision engine instance."""
        return self._decision_engine

    @property
    def config(self) -> SystemConfig:
        """Get the system configuration."""
        return self._config
