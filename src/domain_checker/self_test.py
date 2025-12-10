"""
Startup Self-Test module for the domain checker system.

This module provides connectivity tests for all configured endpoints
and configuration validation to ensure the system is properly set up
before starting operations.

Implements Requirement 10.4:
WHERE startup self-test is enabled WHEN the system starts
THEN the Domain-Checker SHALL verify connectivity to all configured endpoints
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx

from .config import SystemConfig, TLDConfig

from .i18n import get_message


@dataclass
class EndpointTestResult:
    """Result of testing a single endpoint."""

    endpoint: str
    tld: str
    endpoint_type: str  # 'rdap_primary', 'rdap_secondary', 'whois'
    success: bool
    response_time_ms: float
    error: Optional[str] = None
    http_status_code: Optional[int] = None


@dataclass
class ConfigValidationResult:
    """Result of configuration validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class SelfTestResult:
    """Complete self-test result."""

    success: bool
    config_validation: ConfigValidationResult
    endpoint_results: list[EndpointTestResult] = field(default_factory=list)
    total_duration_ms: float = 0.0

    @property
    def failed_endpoints(self) -> list[EndpointTestResult]:
        """Return list of failed endpoint tests."""
        return [r for r in self.endpoint_results if not r.success]

    @property
    def successful_endpoints(self) -> list[EndpointTestResult]:
        """Return list of successful endpoint tests."""
        return [r for r in self.endpoint_results if r.success]


class SelfTest:
    """
    Startup self-test for the domain checker system.

    Performs:
    1. Configuration validation
    2. Connectivity tests for all RDAP endpoints
    3. Connectivity tests for WHOIS servers (if enabled)

    Per Requirement 10.4: Verifies connectivity to all configured endpoints
    when startup self-test is enabled.
    """

    # Timeout for connectivity tests (shorter than normal operations)
    CONNECTIVITY_TIMEOUT = 5.0

    def __init__(
        self,
        config: SystemConfig,
        logger: Optional[object] = None,
    ) -> None:
        """
        Initialize the self-test.

        Args:
            config: System configuration to validate and test
            logger: Optional logger for output
        """
        self._config = config
        self._logger = logger

    async def run(self) -> SelfTestResult:
        """
        Run the complete self-test.

        Returns:
            SelfTestResult with validation and connectivity results
        """
        import time

        start_time = time.perf_counter()

        # Step 1: Validate configuration
        config_result = self.validate_config()

        # If config is invalid, don't proceed with connectivity tests
        if not config_result.valid:
            return SelfTestResult(
                success=False,
                config_validation=config_result,
                endpoint_results=[],
                total_duration_ms=self._elapsed_ms(start_time),
            )

        # Step 2: Test endpoint connectivity
        endpoint_results = await self._test_all_endpoints()

        # Determine overall success
        all_endpoints_ok = all(r.success for r in endpoint_results)
        success = config_result.valid and all_endpoints_ok

        return SelfTestResult(
            success=success,
            config_validation=config_result,
            endpoint_results=endpoint_results,
            total_duration_ms=self._elapsed_ms(start_time),
        )

    def validate_config(self) -> ConfigValidationResult:
        """
        Validate the system configuration.

        Checks:
        - At least one TLD is configured
        - All RDAP endpoints use HTTPS
        - Required fields are present
        - HMAC secret is not the default value

        Returns:
            ConfigValidationResult with validation status
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Check TLDs
        if not self._config.tlds:
            errors.append("No TLDs configured")
        else:
            for tld_config in self._config.tlds:
                tld_errors, tld_warnings = self._validate_tld_config(tld_config)
                errors.extend(tld_errors)
                warnings.extend(tld_warnings)

        # Check persistence config
        if not self._config.persistence.hmac_secret:
            errors.append("HMAC secret is not configured")
        elif self._config.persistence.hmac_secret == "default-secret-change-me":
            warnings.append("HMAC secret is using default value - please change for production")

        # Check rate limits
        if self._config.rate_limits.global_limit is None:
            warnings.append("No global rate limit configured")

        # Check retry config
        if self._config.retry.max_retries < 1:
            warnings.append("max_retries is less than 1 - no retries will be performed")

        # Check language
        if self._config.language not in ("de", "en"):
            errors.append(f"Unsupported language: {self._config.language}")

        return ConfigValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_tld_config(self, tld_config: TLDConfig) -> tuple[list[str], list[str]]:
        """
        Validate a single TLD configuration.

        Args:
            tld_config: TLD configuration to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors: list[str] = []
        warnings: list[str] = []
        tld = tld_config.tld

        # Check TLD name
        if not tld:
            errors.append("TLD name is empty")
            return errors, warnings

        # Check RDAP endpoint
        if not tld_config.rdap_endpoint:
            errors.append(f"TLD '{tld}': No RDAP endpoint configured")
        else:
            # Validate HTTPS requirement (Requirement 2.5)
            parsed = urlparse(tld_config.rdap_endpoint)
            if parsed.scheme.lower() != "https":
                errors.append(
                    f"TLD '{tld}': RDAP endpoint must use HTTPS: {tld_config.rdap_endpoint}"
                )

        # Check secondary RDAP endpoint if configured
        if tld_config.secondary_rdap_endpoint:
            parsed = urlparse(tld_config.secondary_rdap_endpoint)
            if parsed.scheme.lower() != "https":
                errors.append(
                    f"TLD '{tld}': Secondary RDAP endpoint must use HTTPS: "
                    f"{tld_config.secondary_rdap_endpoint}"
                )
        else:
            warnings.append(f"TLD '{tld}': No secondary RDAP endpoint configured")

        # Check WHOIS configuration
        if tld_config.whois_enabled and not tld_config.whois_server:
            errors.append(f"TLD '{tld}': WHOIS enabled but no server configured")

        return errors, warnings

    async def _test_all_endpoints(self) -> list[EndpointTestResult]:
        """
        Test connectivity to all configured endpoints.

        Returns:
            List of endpoint test results
        """
        results: list[EndpointTestResult] = []

        # Create tasks for all endpoint tests
        tasks = []
        for tld_config in self._config.tlds:
            # Test primary RDAP endpoint
            if tld_config.rdap_endpoint:
                tasks.append(
                    self._test_rdap_endpoint(
                        endpoint=tld_config.rdap_endpoint,
                        tld=tld_config.tld,
                        endpoint_type="rdap_primary",
                    )
                )

            # Test secondary RDAP endpoint if configured
            if tld_config.secondary_rdap_endpoint:
                tasks.append(
                    self._test_rdap_endpoint(
                        endpoint=tld_config.secondary_rdap_endpoint,
                        tld=tld_config.tld,
                        endpoint_type="rdap_secondary",
                    )
                )

            # Test WHOIS server if enabled
            if tld_config.whois_enabled and tld_config.whois_server:
                tasks.append(
                    self._test_whois_server(
                        server=tld_config.whois_server,
                        tld=tld_config.tld,
                    )
                )

        # Run all tests concurrently
        if tasks:
            results = await asyncio.gather(*tasks)

        return list(results)

    async def _test_rdap_endpoint(
        self,
        endpoint: str,
        tld: str,
        endpoint_type: str,
    ) -> EndpointTestResult:
        """
        Test connectivity to an RDAP endpoint.

        Performs a simple HEAD or GET request to verify the endpoint is reachable.

        Args:
            endpoint: RDAP endpoint URL
            tld: TLD this endpoint serves
            endpoint_type: Type of endpoint ('rdap_primary' or 'rdap_secondary')

        Returns:
            EndpointTestResult with test outcome
        """
        import time

        start_time = time.perf_counter()

        # Validate HTTPS requirement
        parsed = urlparse(endpoint)
        if parsed.scheme.lower() != "https":
            return EndpointTestResult(
                endpoint=endpoint,
                tld=tld,
                endpoint_type=endpoint_type,
                success=False,
                response_time_ms=self._elapsed_ms(start_time),
                error="Endpoint does not use HTTPS",
            )

        try:
            async with httpx.AsyncClient(
                verify=True,
                timeout=httpx.Timeout(self.CONNECTIVITY_TIMEOUT),
            ) as client:
                # Try HEAD request first (lighter), fall back to GET
                try:
                    response = await client.head(
                        endpoint,
                        headers={"Accept": "application/rdap+json"},
                    )
                except httpx.HTTPStatusError:
                    # Some servers don't support HEAD, try GET
                    response = await client.get(
                        endpoint,
                        headers={"Accept": "application/rdap+json"},
                    )

                # Consider 2xx, 3xx, 4xx as "reachable" (server responded)
                # Only 5xx or connection errors indicate problems
                success = response.status_code < 500

                return EndpointTestResult(
                    endpoint=endpoint,
                    tld=tld,
                    endpoint_type=endpoint_type,
                    success=success,
                    response_time_ms=self._elapsed_ms(start_time),
                    http_status_code=response.status_code,
                    error=None if success else f"Server error: {response.status_code}",
                )

        except httpx.TimeoutException:
            return EndpointTestResult(
                endpoint=endpoint,
                tld=tld,
                endpoint_type=endpoint_type,
                success=False,
                response_time_ms=self._elapsed_ms(start_time),
                error=f"Connection timed out after {self.CONNECTIVITY_TIMEOUT}s",
            )
        except httpx.ConnectError as e:
            error_msg = str(e)
            if "ssl" in error_msg.lower() or "certificate" in error_msg.lower():
                error = f"TLS/SSL error: {error_msg}"
            else:
                error = f"Connection error: {error_msg}"

            return EndpointTestResult(
                endpoint=endpoint,
                tld=tld,
                endpoint_type=endpoint_type,
                success=False,
                response_time_ms=self._elapsed_ms(start_time),
                error=error,
            )
        except Exception as e:
            return EndpointTestResult(
                endpoint=endpoint,
                tld=tld,
                endpoint_type=endpoint_type,
                success=False,
                response_time_ms=self._elapsed_ms(start_time),
                error=f"Unexpected error: {e}",
            )

    async def _test_whois_server(
        self,
        server: str,
        tld: str,
    ) -> EndpointTestResult:
        """
        Test connectivity to a WHOIS server.

        Attempts to establish a TCP connection to port 43.

        Args:
            server: WHOIS server hostname
            tld: TLD this server serves

        Returns:
            EndpointTestResult with test outcome
        """
        import socket
        import time

        start_time = time.perf_counter()

        loop = asyncio.get_event_loop()

        def _sync_test() -> tuple[bool, Optional[str]]:
            """Synchronous socket test."""
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(self.CONNECTIVITY_TIMEOUT)
                    sock.connect((server, 43))
                    return True, None
            except socket.timeout:
                return False, f"Connection timed out after {self.CONNECTIVITY_TIMEOUT}s"
            except socket.gaierror as e:
                return False, f"DNS resolution failed: {e}"
            except socket.error as e:
                return False, f"Socket error: {e}"
            except Exception as e:
                return False, f"Unexpected error: {e}"

        try:
            success, error = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_test),
                timeout=self.CONNECTIVITY_TIMEOUT + 1,
            )

            return EndpointTestResult(
                endpoint=f"{server}:43",
                tld=tld,
                endpoint_type="whois",
                success=success,
                response_time_ms=self._elapsed_ms(start_time),
                error=error,
            )
        except asyncio.TimeoutError:
            return EndpointTestResult(
                endpoint=f"{server}:43",
                tld=tld,
                endpoint_type="whois",
                success=False,
                response_time_ms=self._elapsed_ms(start_time),
                error=f"Connection timed out after {self.CONNECTIVITY_TIMEOUT}s",
            )

    def _elapsed_ms(self, start_time: float) -> float:
        """Calculate elapsed time in milliseconds."""
        import time
        return (time.perf_counter() - start_time) * 1000

    def print_results(self, result: SelfTestResult, language: str = "de") -> None:
        """
        Print self-test results to stdout.

        Args:
            result: Self-test result to print
            language: Output language ('de' or 'en')
        """
        print(get_message("selftest.header", language))
        print("=" * 60)

        # Configuration validation
        print(f"\n{get_message('selftest.config_validation', language)}")
        if result.config_validation.valid:
            print(f"  ✓ {get_message('selftest.config_valid', language)}")
        else:
            print(f"  ✗ {get_message('selftest.config_invalid', language)}")
            for error in result.config_validation.errors:
                print(f"    - {error}")

        if result.config_validation.warnings:
            print(f"\n  {get_message('selftest.warnings', language)}")
            for warning in result.config_validation.warnings:
                print(f"    - {warning}")

        # Endpoint connectivity
        if result.endpoint_results:
            print(f"\n{get_message('selftest.connectivity', language)}")

            for endpoint_result in result.endpoint_results:
                status = "✓" if endpoint_result.success else "✗"
                type_label = {
                    "rdap_primary": "RDAP",
                    "rdap_secondary": "RDAP (secondary)",
                    "whois": "WHOIS",
                }.get(endpoint_result.endpoint_type, endpoint_result.endpoint_type)

                print(
                    f"  {status} [{endpoint_result.tld}] {type_label}: "
                    f"{endpoint_result.endpoint} "
                    f"({endpoint_result.response_time_ms:.0f}ms)"
                )
                if endpoint_result.error:
                    print(f"      Error: {endpoint_result.error}")

        # Summary
        print(f"\n{'-' * 60}")
        if result.success:
            print(f"✓ {get_message('selftest.success', language)}")
        else:
            print(f"✗ {get_message('selftest.failed', language)}")

        print(f"  {get_message('selftest.duration', language)}: {result.total_duration_ms:.0f}ms")


async def run_self_test(
    config: SystemConfig,
    print_output: bool = True,
    language: str = "de",
) -> SelfTestResult:
    """
    Convenience function to run self-test.

    Args:
        config: System configuration to test
        print_output: Whether to print results to stdout
        language: Output language

    Returns:
        SelfTestResult with test outcomes
    """
    self_test = SelfTest(config)
    result = await self_test.run()

    if print_output:
        self_test.print_results(result, language)

    return result
