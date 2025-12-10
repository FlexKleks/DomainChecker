"""
Decision Engine for domain availability determination.

This module implements the conservative decision logic that evaluates
domain availability based on multiple sources. A domain is only marked
as "available" when there is definitive proof from multiple sources.

Requirements covered:
- 3.1: Query secondary RDAP when primary indicates availability
- 3.2: Source disagreement results in taken (conservative approach)
- 6.1: Available only with definitive 404 AND secondary confirmation
- 6.2: Any uncertainty results in taken
- 6.3: Network errors, timeouts, inconsistent responses result in taken
- 6.4: Accept only explicitly defined criteria without heuristics
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .enums import AvailabilityStatus, Confidence, RDAPStatus, WHOISStatus
from .models import CheckMetadata, CheckResult, SourceResult
from .rdap_client import RDAPResponse
from .whois_client import WHOISResponse


@dataclass
class EvaluationContext:
    """Context for evaluation with all source results."""

    primary_result: Optional[RDAPResponse]
    secondary_result: Optional[RDAPResponse]
    whois_result: Optional[WHOISResponse]


class DecisionEngine:
    """
    Conservative decision engine for domain availability.

    This engine follows the principle "when in doubt, mark as taken".
    A domain is only marked as AVAILABLE when:
    1. Primary RDAP returns definitive 404 (NOT_FOUND)
    2. Secondary RDAP confirms (NOT_FOUND) OR is unavailable but WHOIS confirms

    Any uncertainty, error, or disagreement results in TAKEN status.
    """

    def evaluate(
        self,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse] = None,
        whois_result: Optional[WHOISResponse] = None,
    ) -> AvailabilityStatus:
        """
        Evaluate domain availability based on all source results.

        Implements conservative decision logic per Requirements 3.2, 6.1-6.4.

        Args:
            primary_result: Result from primary RDAP query
            secondary_result: Optional result from secondary RDAP query
            whois_result: Optional result from WHOIS fallback query

        Returns:
            AvailabilityStatus - AVAILABLE only with definitive multi-source proof
        """
        # No primary result means we can't determine anything -> TAKEN
        if primary_result is None:
            return AvailabilityStatus.TAKEN

        # Primary has error -> TAKEN (Requirement 6.3)
        if primary_result.status == RDAPStatus.ERROR:
            return AvailabilityStatus.TAKEN

        # Primary indicates domain is registered -> TAKEN
        if primary_result.status == RDAPStatus.FOUND:
            return AvailabilityStatus.TAKEN

        # Primary indicates NOT_FOUND - need secondary confirmation
        if primary_result.status == RDAPStatus.NOT_FOUND:
            return self._evaluate_with_secondary(
                primary_result, secondary_result, whois_result
            )

        # Unknown status -> TAKEN (conservative)
        return AvailabilityStatus.TAKEN

    def _evaluate_with_secondary(
        self,
        primary_result: RDAPResponse,
        secondary_result: Optional[RDAPResponse],
        whois_result: Optional[WHOISResponse],
    ) -> AvailabilityStatus:
        """
        Evaluate when primary indicates NOT_FOUND.

        Per Requirement 6.1: Available only when primary RDAP returns 404
        AND secondary confirms OR WHOIS confirms when secondary unavailable.

        Per Requirement 3.2: Source disagreement results in TAKEN.
        """
        # If we have a secondary RDAP result
        if secondary_result is not None:
            # Secondary has error -> check WHOIS if available, else TAKEN
            if secondary_result.status == RDAPStatus.ERROR:
                return self._evaluate_with_whois_only(whois_result)

            # Secondary says FOUND but primary says NOT_FOUND -> disagreement -> TAKEN
            # (Requirement 3.2)
            if secondary_result.status == RDAPStatus.FOUND:
                return AvailabilityStatus.TAKEN

            # Secondary confirms NOT_FOUND -> AVAILABLE
            if secondary_result.status == RDAPStatus.NOT_FOUND:
                return AvailabilityStatus.AVAILABLE

            # Unknown secondary status -> TAKEN
            return AvailabilityStatus.TAKEN

        # No secondary result - try WHOIS fallback
        return self._evaluate_with_whois_only(whois_result)

    def _evaluate_with_whois_only(
        self,
        whois_result: Optional[WHOISResponse],
    ) -> AvailabilityStatus:
        """
        Evaluate using only WHOIS when secondary RDAP is unavailable.

        Per Requirement 3.4: Ambiguous WHOIS results in TAKEN.
        """
        if whois_result is None:
            # No secondary confirmation available -> TAKEN (conservative)
            return AvailabilityStatus.TAKEN

        # WHOIS error -> TAKEN (Requirement 6.3)
        if whois_result.status == WHOISStatus.ERROR:
            return AvailabilityStatus.TAKEN

        # WHOIS says FOUND -> TAKEN
        if whois_result.status == WHOISStatus.FOUND:
            return AvailabilityStatus.TAKEN

        # WHOIS is ambiguous -> TAKEN (Requirement 3.4)
        if whois_result.status == WHOISStatus.AMBIGUOUS:
            return AvailabilityStatus.TAKEN

        # WHOIS confirms NOT_FOUND -> AVAILABLE
        if whois_result.status == WHOISStatus.NOT_FOUND:
            return AvailabilityStatus.AVAILABLE

        # Unknown status -> TAKEN
        return AvailabilityStatus.TAKEN

    def determine_confidence(
        self,
        status: AvailabilityStatus,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse],
        whois_result: Optional[WHOISResponse],
    ) -> Confidence:
        """
        Determine confidence level of the availability determination.

        HIGH confidence when:
        - Multiple sources agree
        - No errors occurred

        LOW confidence when:
        - Only one source available
        - Errors occurred but conservative decision made
        """
        if status == AvailabilityStatus.TAKEN:
            # TAKEN is always high confidence (conservative approach)
            return Confidence.HIGH

        if status == AvailabilityStatus.UNKNOWN:
            return Confidence.LOW

        # For AVAILABLE status, check source agreement
        sources_confirming = 0

        if primary_result and primary_result.status == RDAPStatus.NOT_FOUND:
            sources_confirming += 1

        if secondary_result and secondary_result.status == RDAPStatus.NOT_FOUND:
            sources_confirming += 1

        if whois_result and whois_result.status == WHOISStatus.NOT_FOUND:
            sources_confirming += 1

        # High confidence if 2+ sources confirm
        return Confidence.HIGH if sources_confirming >= 2 else Confidence.LOW

    def build_check_result(
        self,
        domain: str,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse] = None,
        whois_result: Optional[WHOISResponse] = None,
        metadata: Optional[CheckMetadata] = None,
    ) -> CheckResult:
        """
        Build a complete CheckResult from source results.

        Args:
            domain: The domain that was checked
            primary_result: Result from primary RDAP
            secondary_result: Optional result from secondary RDAP
            whois_result: Optional result from WHOIS
            metadata: Optional check metadata

        Returns:
            Complete CheckResult with status, confidence, sources, and timestamp
        """
        # Evaluate availability
        status = self.evaluate(primary_result, secondary_result, whois_result)

        # Determine confidence
        confidence = self.determine_confidence(
            status, primary_result, secondary_result, whois_result
        )

        # Build source results list
        sources = self._build_source_results(
            primary_result, secondary_result, whois_result
        )

        # Generate timestamp
        timestamp = datetime.now(timezone.utc).isoformat()

        # Use provided metadata or create default
        if metadata is None:
            metadata = CheckMetadata(
                total_duration_ms=0.0,
                retry_count=0,
                rate_limit_delays=0,
            )

        return CheckResult(
            domain=domain,
            status=status,
            confidence=confidence,
            sources=sources,
            timestamp=timestamp,
            metadata=metadata,
        )

    def _build_source_results(
        self,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse],
        whois_result: Optional[WHOISResponse],
    ) -> list[SourceResult]:
        """Build list of SourceResult from all source responses."""
        sources: list[SourceResult] = []

        if primary_result is not None:
            sources.append(
                SourceResult(
                    source="rdap_primary",
                    status=primary_result.status.value,
                    http_status_code=primary_result.http_status_code,
                    response_time_ms=primary_result.response_time_ms,
                )
            )

        if secondary_result is not None:
            sources.append(
                SourceResult(
                    source="rdap_secondary",
                    status=secondary_result.status.value,
                    http_status_code=secondary_result.http_status_code,
                    response_time_ms=secondary_result.response_time_ms,
                )
            )

        if whois_result is not None:
            sources.append(
                SourceResult(
                    source="whois",
                    status=whois_result.status.value,
                    http_status_code=None,  # WHOIS doesn't use HTTP
                    response_time_ms=0.0,  # WHOIS client doesn't track this
                )
            )

        return sources

    def has_any_error(
        self,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse],
        whois_result: Optional[WHOISResponse],
    ) -> bool:
        """
        Check if any source returned an error.

        Useful for logging and diagnostics.
        """
        if primary_result and primary_result.status == RDAPStatus.ERROR:
            return True
        if secondary_result and secondary_result.status == RDAPStatus.ERROR:
            return True
        if whois_result and whois_result.status == WHOISStatus.ERROR:
            return True
        return False

    def sources_disagree(
        self,
        primary_result: Optional[RDAPResponse],
        secondary_result: Optional[RDAPResponse],
    ) -> bool:
        """
        Check if primary and secondary RDAP sources disagree.

        Disagreement occurs when one says FOUND and the other says NOT_FOUND.
        """
        if primary_result is None or secondary_result is None:
            return False

        # Skip if either has an error
        if primary_result.status == RDAPStatus.ERROR:
            return False
        if secondary_result.status == RDAPStatus.ERROR:
            return False

        # Check for disagreement
        primary_found = primary_result.status == RDAPStatus.FOUND
        secondary_found = secondary_result.status == RDAPStatus.FOUND
        primary_not_found = primary_result.status == RDAPStatus.NOT_FOUND
        secondary_not_found = secondary_result.status == RDAPStatus.NOT_FOUND

        # Disagreement: one FOUND, other NOT_FOUND
        return (primary_found and secondary_not_found) or (
            primary_not_found and secondary_found
        )
