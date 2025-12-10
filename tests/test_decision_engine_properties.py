"""
Property-based tests for Decision Engine module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.decision_engine import DecisionEngine
from domain_checker.enums import AvailabilityStatus, RDAPStatus, WHOISStatus
from domain_checker.rdap_client import RDAPResponse, RDAPError, RDAPParsedFields
from domain_checker.whois_client import WHOISResponse, WHOISError
from domain_checker.enums import RDAPErrorCode, WHOISErrorCode


# Strategies for generating RDAP responses
def rdap_response_strategy(
    status: RDAPStatus,
    http_status_code: int = 200,
) -> st.SearchStrategy[RDAPResponse]:
    """Generate RDAP responses with specific status."""
    if status == RDAPStatus.FOUND:
        return st.builds(
            RDAPResponse,
            status=st.just(RDAPStatus.FOUND),
            http_status_code=st.just(http_status_code),
            raw_response=st.just({"ldhName": "example.com", "status": ["active"]}),
            parsed_fields=st.just(
                RDAPParsedFields(
                    domain_name="example.com",
                    status=["active"],
                    events=[],
                    nameservers=[],
                )
            ),
            error=st.none(),
            response_time_ms=st.floats(min_value=0.0, max_value=1000.0),
        )
    elif status == RDAPStatus.NOT_FOUND:
        return st.builds(
            RDAPResponse,
            status=st.just(RDAPStatus.NOT_FOUND),
            http_status_code=st.just(404),
            raw_response=st.none(),
            parsed_fields=st.none(),
            error=st.none(),
            response_time_ms=st.floats(min_value=0.0, max_value=1000.0),
        )
    else:  # ERROR
        return st.builds(
            RDAPResponse,
            status=st.just(RDAPStatus.ERROR),
            http_status_code=st.sampled_from([0, 429, 500, 502, 503]),
            raw_response=st.none(),
            parsed_fields=st.none(),
            error=st.builds(
                RDAPError,
                code=st.sampled_from(list(RDAPErrorCode)),
                message=st.text(min_size=1, max_size=50),
                http_status_code=st.one_of(st.none(), st.integers(400, 599)),
            ),
            response_time_ms=st.floats(min_value=0.0, max_value=1000.0),
        )


def whois_response_strategy(
    status: WHOISStatus,
) -> st.SearchStrategy[WHOISResponse]:
    """Generate WHOIS responses with specific status."""
    if status == WHOISStatus.FOUND:
        return st.builds(
            WHOISResponse,
            status=st.just(WHOISStatus.FOUND),
            raw_response=st.just("Domain Name: example.com\nRegistrar: Test"),
            no_match_signal_detected=st.just(False),
            error=st.none(),
        )
    elif status == WHOISStatus.NOT_FOUND:
        return st.builds(
            WHOISResponse,
            status=st.just(WHOISStatus.NOT_FOUND),
            raw_response=st.just("Status: free"),
            no_match_signal_detected=st.just(True),
            error=st.none(),
        )
    elif status == WHOISStatus.AMBIGUOUS:
        return st.builds(
            WHOISResponse,
            status=st.just(WHOISStatus.AMBIGUOUS),
            raw_response=st.text(min_size=0, max_size=100),
            no_match_signal_detected=st.just(False),
            error=st.none(),
        )
    else:  # ERROR
        return st.builds(
            WHOISResponse,
            status=st.just(WHOISStatus.ERROR),
            raw_response=st.none(),
            no_match_signal_detected=st.just(False),
            error=st.builds(
                WHOISError,
                code=st.sampled_from(list(WHOISErrorCode)),
                message=st.text(min_size=1, max_size=50),
            ),
        )


class TestSourceDisagreementProperty:
    """
    Property-based tests for source disagreement handling.

    **Feature: domain-availability-checker, Property 8: Source disagreement results in taken**
    **Validates: Requirements 3.2**
    """

    @given(
        response_time_primary=st.floats(min_value=0.0, max_value=1000.0),
        response_time_secondary=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_found_secondary_not_found_results_in_taken(
        self,
        response_time_primary: float,
        response_time_secondary: float,
    ) -> None:
        """
        Property 8a: Primary FOUND + Secondary NOT_FOUND = TAKEN.

        *For any* combination where primary RDAP says FOUND and secondary
        says NOT_FOUND, the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 8: Source disagreement results in taken**
        **Validates: Requirements 3.2**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.FOUND,
            http_status_code=200,
            raw_response={"ldhName": "example.com", "status": ["active"]},
            parsed_fields=RDAPParsedFields(
                domain_name="example.com",
                status=["active"],
                events=[],
                nameservers=[],
            ),
            error=None,
            response_time_ms=response_time_primary,
        )

        secondary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_secondary,
        )

        result = engine.evaluate(primary, secondary)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary FOUND + Secondary NOT_FOUND should result in TAKEN, "
            f"got {result}"
        )

    @given(
        response_time_primary=st.floats(min_value=0.0, max_value=1000.0),
        response_time_secondary=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_not_found_secondary_found_results_in_taken(
        self,
        response_time_primary: float,
        response_time_secondary: float,
    ) -> None:
        """
        Property 8b: Primary NOT_FOUND + Secondary FOUND = TAKEN.

        *For any* combination where primary RDAP says NOT_FOUND and secondary
        says FOUND, the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 8: Source disagreement results in taken**
        **Validates: Requirements 3.2**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_primary,
        )

        secondary = RDAPResponse(
            status=RDAPStatus.FOUND,
            http_status_code=200,
            raw_response={"ldhName": "example.com", "status": ["active"]},
            parsed_fields=RDAPParsedFields(
                domain_name="example.com",
                status=["active"],
                events=[],
                nameservers=[],
            ),
            error=None,
            response_time_ms=response_time_secondary,
        )

        result = engine.evaluate(primary, secondary)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND + Secondary FOUND should result in TAKEN, "
            f"got {result}"
        )

    @given(
        primary_status=st.sampled_from([RDAPStatus.FOUND, RDAPStatus.NOT_FOUND]),
        secondary_status=st.sampled_from([RDAPStatus.FOUND, RDAPStatus.NOT_FOUND]),
    )
    @settings(max_examples=100)
    def test_disagreement_always_results_in_taken(
        self,
        primary_status: RDAPStatus,
        secondary_status: RDAPStatus,
    ) -> None:
        """
        Property 8c: Any disagreement between sources results in TAKEN.

        *For any* combination where primary and secondary RDAP disagree
        (one FOUND, one NOT_FOUND), the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 8: Source disagreement results in taken**
        **Validates: Requirements 3.2**
        """
        # Only test when there's actual disagreement
        assume(primary_status != secondary_status)

        engine = DecisionEngine()

        if primary_status == RDAPStatus.FOUND:
            primary = RDAPResponse(
                status=RDAPStatus.FOUND,
                http_status_code=200,
                raw_response={"ldhName": "example.com", "status": ["active"]},
                parsed_fields=RDAPParsedFields(
                    domain_name="example.com",
                    status=["active"],
                    events=[],
                    nameservers=[],
                ),
                error=None,
                response_time_ms=50.0,
            )
        else:
            primary = RDAPResponse(
                status=RDAPStatus.NOT_FOUND,
                http_status_code=404,
                raw_response=None,
                parsed_fields=None,
                error=None,
                response_time_ms=50.0,
            )

        if secondary_status == RDAPStatus.FOUND:
            secondary = RDAPResponse(
                status=RDAPStatus.FOUND,
                http_status_code=200,
                raw_response={"ldhName": "example.com", "status": ["active"]},
                parsed_fields=RDAPParsedFields(
                    domain_name="example.com",
                    status=["active"],
                    events=[],
                    nameservers=[],
                ),
                error=None,
                response_time_ms=50.0,
            )
        else:
            secondary = RDAPResponse(
                status=RDAPStatus.NOT_FOUND,
                http_status_code=404,
                raw_response=None,
                parsed_fields=None,
                error=None,
                response_time_ms=50.0,
            )

        result = engine.evaluate(primary, secondary)

        assert result == AvailabilityStatus.TAKEN, (
            f"Disagreement (primary={primary_status}, secondary={secondary_status}) "
            f"should result in TAKEN, got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_sources_disagree_helper_detects_disagreement(
        self,
        response_time: float,
    ) -> None:
        """
        Property 8d: sources_disagree() correctly identifies disagreement.

        *For any* pair of RDAP responses where one is FOUND and one is NOT_FOUND,
        the sources_disagree() method SHALL return True.

        **Feature: domain-availability-checker, Property 8: Source disagreement results in taken**
        **Validates: Requirements 3.2**
        """
        engine = DecisionEngine()

        found_response = RDAPResponse(
            status=RDAPStatus.FOUND,
            http_status_code=200,
            raw_response={"ldhName": "example.com", "status": ["active"]},
            parsed_fields=RDAPParsedFields(
                domain_name="example.com",
                status=["active"],
                events=[],
                nameservers=[],
            ),
            error=None,
            response_time_ms=response_time,
        )

        not_found_response = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        # Test both directions of disagreement
        assert engine.sources_disagree(found_response, not_found_response), (
            "sources_disagree should return True for FOUND vs NOT_FOUND"
        )
        assert engine.sources_disagree(not_found_response, found_response), (
            "sources_disagree should return True for NOT_FOUND vs FOUND"
        )

        # Test agreement cases
        assert not engine.sources_disagree(found_response, found_response), (
            "sources_disagree should return False for FOUND vs FOUND"
        )
        assert not engine.sources_disagree(not_found_response, not_found_response), (
            "sources_disagree should return False for NOT_FOUND vs NOT_FOUND"
        )



class TestConfirmedAvailabilityProperty:
    """
    Property-based tests for confirmed availability handling.

    **Feature: domain-availability-checker, Property 10: Confirmed availability from multiple sources results in available**
    **Validates: Requirements 6.1**
    """

    @given(
        response_time_primary=st.floats(min_value=0.0, max_value=1000.0),
        response_time_secondary=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_and_secondary_not_found_results_in_available(
        self,
        response_time_primary: float,
        response_time_secondary: float,
    ) -> None:
        """
        Property 10a: Primary NOT_FOUND + Secondary NOT_FOUND = AVAILABLE.

        *For any* check where primary RDAP returns 404 AND secondary RDAP
        confirms with 404, the decision engine SHALL return AVAILABLE.

        **Feature: domain-availability-checker, Property 10: Confirmed availability from multiple sources results in available**
        **Validates: Requirements 6.1**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_primary,
        )

        secondary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_secondary,
        )

        result = engine.evaluate(primary, secondary)

        assert result == AvailabilityStatus.AVAILABLE, (
            f"Primary NOT_FOUND + Secondary NOT_FOUND should result in AVAILABLE, "
            f"got {result}"
        )

    @given(
        response_time_primary=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_not_found_whois_not_found_results_in_available(
        self,
        response_time_primary: float,
    ) -> None:
        """
        Property 10b: Primary NOT_FOUND + WHOIS NOT_FOUND = AVAILABLE.

        *For any* check where primary RDAP returns 404 AND secondary is unavailable
        but WHOIS confirms with exact "no match", the decision engine SHALL
        return AVAILABLE.

        **Feature: domain-availability-checker, Property 10: Confirmed availability from multiple sources results in available**
        **Validates: Requirements 6.1**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_primary,
        )

        whois = WHOISResponse(
            status=WHOISStatus.NOT_FOUND,
            raw_response="Status: free",
            no_match_signal_detected=True,
            error=None,
        )

        # No secondary RDAP, but WHOIS confirms
        result = engine.evaluate(primary, None, whois)

        assert result == AvailabilityStatus.AVAILABLE, (
            f"Primary NOT_FOUND + WHOIS NOT_FOUND should result in AVAILABLE, "
            f"got {result}"
        )

    @given(
        response_time_primary=st.floats(min_value=0.0, max_value=1000.0),
        error_code=st.sampled_from(list(RDAPErrorCode)),
    )
    @settings(max_examples=100)
    def test_primary_not_found_secondary_error_whois_not_found_results_in_available(
        self,
        response_time_primary: float,
        error_code: RDAPErrorCode,
    ) -> None:
        """
        Property 10c: Primary NOT_FOUND + Secondary ERROR + WHOIS NOT_FOUND = AVAILABLE.

        *For any* check where primary RDAP returns 404, secondary has an error,
        but WHOIS confirms with exact "no match", the decision engine SHALL
        return AVAILABLE.

        **Feature: domain-availability-checker, Property 10: Confirmed availability from multiple sources results in available**
        **Validates: Requirements 6.1**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time_primary,
        )

        secondary = RDAPResponse(
            status=RDAPStatus.ERROR,
            http_status_code=500,
            raw_response=None,
            parsed_fields=None,
            error=RDAPError(
                code=error_code,
                message="Server error",
                http_status_code=500,
            ),
            response_time_ms=50.0,
        )

        whois = WHOISResponse(
            status=WHOISStatus.NOT_FOUND,
            raw_response="Status: free",
            no_match_signal_detected=True,
            error=None,
        )

        result = engine.evaluate(primary, secondary, whois)

        assert result == AvailabilityStatus.AVAILABLE, (
            f"Primary NOT_FOUND + Secondary ERROR + WHOIS NOT_FOUND "
            f"should result in AVAILABLE, got {result}"
        )


class TestUncertaintyResultsInTakenProperty:
    """
    Property-based tests for uncertainty handling.

    **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
    **Validates: Requirements 6.2, 6.3**
    """

    @given(
        error_code=st.sampled_from(list(RDAPErrorCode)),
        http_status=st.sampled_from([0, 429, 500, 502, 503]),
    )
    @settings(max_examples=100)
    def test_primary_error_results_in_taken(
        self,
        error_code: RDAPErrorCode,
        http_status: int,
    ) -> None:
        """
        Property 11a: Primary RDAP error results in TAKEN.

        *For any* check where primary RDAP returns an error (network error,
        timeout, server error), the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.ERROR,
            http_status_code=http_status,
            raw_response=None,
            parsed_fields=None,
            error=RDAPError(
                code=error_code,
                message="Error occurred",
                http_status_code=http_status if http_status > 0 else None,
            ),
            response_time_ms=50.0,
        )

        result = engine.evaluate(primary)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary ERROR ({error_code}) should result in TAKEN, got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_no_primary_result_results_in_taken(
        self,
        response_time: float,
    ) -> None:
        """
        Property 11b: No primary result results in TAKEN.

        *For any* check where no primary RDAP result is available,
        the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        result = engine.evaluate(None)

        assert result == AvailabilityStatus.TAKEN, (
            f"No primary result should result in TAKEN, got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_not_found_no_confirmation_results_in_taken(
        self,
        response_time: float,
    ) -> None:
        """
        Property 11c: Primary NOT_FOUND without confirmation results in TAKEN.

        *For any* check where primary RDAP returns NOT_FOUND but no secondary
        source is available to confirm, the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        # No secondary, no WHOIS
        result = engine.evaluate(primary, None, None)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND without confirmation should result in TAKEN, "
            f"got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
        whois_error_code=st.sampled_from(list(WHOISErrorCode)),
    )
    @settings(max_examples=100)
    def test_primary_not_found_whois_error_results_in_taken(
        self,
        response_time: float,
        whois_error_code: WHOISErrorCode,
    ) -> None:
        """
        Property 11d: Primary NOT_FOUND + WHOIS error results in TAKEN.

        *For any* check where primary RDAP returns NOT_FOUND but WHOIS
        returns an error, the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        whois = WHOISResponse(
            status=WHOISStatus.ERROR,
            raw_response=None,
            no_match_signal_detected=False,
            error=WHOISError(
                code=whois_error_code,
                message="WHOIS error",
            ),
        )

        result = engine.evaluate(primary, None, whois)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND + WHOIS ERROR should result in TAKEN, got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_not_found_whois_ambiguous_results_in_taken(
        self,
        response_time: float,
    ) -> None:
        """
        Property 11e: Primary NOT_FOUND + WHOIS ambiguous results in TAKEN.

        *For any* check where primary RDAP returns NOT_FOUND but WHOIS
        returns an ambiguous response, the decision engine SHALL return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        whois = WHOISResponse(
            status=WHOISStatus.AMBIGUOUS,
            raw_response="Some unclear response",
            no_match_signal_detected=False,
            error=None,
        )

        result = engine.evaluate(primary, None, whois)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND + WHOIS AMBIGUOUS should result in TAKEN, "
            f"got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
    )
    @settings(max_examples=100)
    def test_primary_not_found_whois_found_results_in_taken(
        self,
        response_time: float,
    ) -> None:
        """
        Property 11f: Primary NOT_FOUND + WHOIS FOUND results in TAKEN.

        *For any* check where primary RDAP returns NOT_FOUND but WHOIS
        indicates the domain is registered, the decision engine SHALL
        return TAKEN (disagreement).

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        whois = WHOISResponse(
            status=WHOISStatus.FOUND,
            raw_response="Domain Name: example.com\nRegistrar: Test",
            no_match_signal_detected=False,
            error=None,
        )

        result = engine.evaluate(primary, None, whois)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND + WHOIS FOUND should result in TAKEN, got {result}"
        )

    @given(
        response_time=st.floats(min_value=0.0, max_value=1000.0),
        error_code=st.sampled_from(list(RDAPErrorCode)),
    )
    @settings(max_examples=100)
    def test_primary_not_found_secondary_error_no_whois_results_in_taken(
        self,
        response_time: float,
        error_code: RDAPErrorCode,
    ) -> None:
        """
        Property 11g: Primary NOT_FOUND + Secondary ERROR + no WHOIS = TAKEN.

        *For any* check where primary RDAP returns NOT_FOUND, secondary has
        an error, and no WHOIS is available, the decision engine SHALL
        return TAKEN.

        **Feature: domain-availability-checker, Property 11: Any uncertainty or error results in taken**
        **Validates: Requirements 6.2, 6.3**
        """
        engine = DecisionEngine()

        primary = RDAPResponse(
            status=RDAPStatus.NOT_FOUND,
            http_status_code=404,
            raw_response=None,
            parsed_fields=None,
            error=None,
            response_time_ms=response_time,
        )

        secondary = RDAPResponse(
            status=RDAPStatus.ERROR,
            http_status_code=500,
            raw_response=None,
            parsed_fields=None,
            error=RDAPError(
                code=error_code,
                message="Server error",
                http_status_code=500,
            ),
            response_time_ms=50.0,
        )

        result = engine.evaluate(primary, secondary, None)

        assert result == AvailabilityStatus.TAKEN, (
            f"Primary NOT_FOUND + Secondary ERROR + no WHOIS "
            f"should result in TAKEN, got {result}"
        )
