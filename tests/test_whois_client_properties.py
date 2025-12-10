"""
Property-based tests for WHOIS client module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import string

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.whois_client import WHOISClient, WHOISResponse
from domain_checker.enums import WHOISStatus


# Strategy for generating WHOIS response text that does NOT contain
# any defined "no match" signals
def ambiguous_whois_response(tld: str) -> st.SearchStrategy[str]:
    """
    Generate WHOIS response text that is ambiguous.
    
    Ambiguous means:
    - Does NOT contain any defined "no match" signal for the TLD
    - Does NOT contain clear registration indicators
    """
    # Characters that are safe to use in WHOIS responses
    safe_chars = string.ascii_letters + string.digits + " \n\r\t:.-_"
    
    # Generate random text that won't accidentally match signals
    return st.text(
        alphabet=safe_chars,
        min_size=10,
        max_size=200,
    ).filter(lambda s: _is_ambiguous_response(s, tld))


def _is_ambiguous_response(response: str, tld: str) -> bool:
    """Check if a response is truly ambiguous (no clear signals)."""
    # Get the no-match signals for this TLD
    signals = WHOISClient.NO_MATCH_SIGNALS.get(tld, [])
    
    # Check that none of the no-match signals are present
    for signal in signals:
        if signal in response:
            return False
    
    # Check that none of the registration indicators are present
    registration_indicators = [
        "Domain Name:",
        "Registrant:",
        "Creation Date:",
        "Registry Domain ID:",
        "Registrar:",
        "Name Server:",
        "DNSSEC:",
    ]
    for indicator in registration_indicators:
        if indicator in response:
            return False
    
    return True


# Strategy for generating valid domain names
def valid_domain(tlds: list[str]) -> st.SearchStrategy[str]:
    """Generate valid domain names for testing."""
    label = st.text(
        alphabet=string.ascii_lowercase + string.digits,
        min_size=1,
        max_size=20,
    ).filter(lambda s: s and s[0].isalnum() and s[-1].isalnum())
    
    return st.builds(
        lambda l, t: f"{l}.{t}",
        label,
        st.sampled_from(tlds),
    )


class TestAmbiguousWHOISProperty:
    """
    Property-based tests for ambiguous WHOIS response handling.
    
    **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
    **Validates: Requirements 3.4**
    """

    SUPPORTED_TLDS = list(WHOISClient.NO_MATCH_SIGNALS.keys())

    @given(
        tld=st.sampled_from(SUPPORTED_TLDS),
        response_text=st.text(
            alphabet=string.ascii_letters + string.digits + " \n\r\t:.-_",
            min_size=10,
            max_size=200,
        ),
    )
    @settings(max_examples=100)
    def test_ambiguous_whois_returns_ambiguous_status(
        self, tld: str, response_text: str
    ) -> None:
        """
        Property 9: Ambiguous WHOIS results in AMBIGUOUS status.
        
        *For any* WHOIS response that does not contain an exact match for a 
        defined "no match" signal, the parser SHALL return status AMBIGUOUS,
        and the decision engine SHALL treat this as TAKEN.
        
        **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
        **Validates: Requirements 3.4**
        """
        client = WHOISClient(simulation_mode=True)
        
        # Ensure the response is truly ambiguous
        assume(_is_ambiguous_response(response_text, tld))
        
        # Parse the response
        result = client._parse_response(response_text, tld)
        
        # Result must be AMBIGUOUS (not NOT_FOUND)
        assert result.status == WHOISStatus.AMBIGUOUS, (
            f"Response without 'no match' signal should be AMBIGUOUS, "
            f"got {result.status} for TLD '{tld}' with response: {repr(response_text[:100])}"
        )
        
        # no_match_signal_detected must be False
        assert not result.no_match_signal_detected, (
            f"no_match_signal_detected should be False for ambiguous response"
        )

    @given(tld=st.sampled_from(SUPPORTED_TLDS))
    @settings(max_examples=100)
    def test_empty_response_is_ambiguous(self, tld: str) -> None:
        """
        Property 9b: Empty WHOIS response is treated as ambiguous.
        
        *For any* TLD, an empty WHOIS response SHALL be treated as AMBIGUOUS.
        
        **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
        **Validates: Requirements 3.4**
        """
        client = WHOISClient(simulation_mode=True)
        
        # Test empty string
        result = client._parse_response("", tld)
        assert result.status == WHOISStatus.AMBIGUOUS, (
            f"Empty response should be AMBIGUOUS, got {result.status}"
        )
        
        # Test whitespace-only string
        result = client._parse_response("   \n\t  ", tld)
        assert result.status == WHOISStatus.AMBIGUOUS, (
            f"Whitespace-only response should be AMBIGUOUS, got {result.status}"
        )

    @given(
        tld=st.sampled_from(SUPPORTED_TLDS),
        prefix=st.text(
            alphabet=string.ascii_letters + string.digits + " \n",
            min_size=0,
            max_size=50,
        ),
        suffix=st.text(
            alphabet=string.ascii_letters + string.digits + " \n",
            min_size=0,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    def test_exact_no_match_signal_returns_not_found(
        self, tld: str, prefix: str, suffix: str
    ) -> None:
        """
        Property 9c: Exact "no match" signal returns NOT_FOUND (inverse property).
        
        *For any* WHOIS response containing an exact "no match" signal for the TLD,
        the parser SHALL return status NOT_FOUND.
        
        **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
        **Validates: Requirements 3.4**
        """
        client = WHOISClient(simulation_mode=True)
        
        signals = client.get_signals_for_tld(tld)
        assume(len(signals) > 0)
        
        # Use the first signal for this TLD
        signal = signals[0]
        
        # Construct response with the signal
        response = f"{prefix}\n{signal}\n{suffix}"
        
        result = client._parse_response(response, tld)
        
        # Result must be NOT_FOUND
        assert result.status == WHOISStatus.NOT_FOUND, (
            f"Response with exact 'no match' signal '{signal}' should be NOT_FOUND, "
            f"got {result.status}"
        )
        
        # no_match_signal_detected must be True
        assert result.no_match_signal_detected, (
            f"no_match_signal_detected should be True when signal is present"
        )

    @given(
        tld=st.sampled_from(SUPPORTED_TLDS),
        registration_indicator=st.sampled_from([
            "Domain Name:",
            "Registrant:",
            "Creation Date:",
            "Registry Domain ID:",
            "Registrar:",
            "Name Server:",
        ]),
        domain_value=st.text(
            alphabet=string.ascii_lowercase + string.digits + ".-",
            min_size=5,
            max_size=30,
        ),
    )
    @settings(max_examples=100)
    def test_registration_indicators_return_found(
        self, tld: str, registration_indicator: str, domain_value: str
    ) -> None:
        """
        Property 9d: Registration indicators return FOUND.
        
        *For any* WHOIS response containing registration indicators,
        the parser SHALL return status FOUND.
        
        **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
        **Validates: Requirements 3.4**
        """
        client = WHOISClient(simulation_mode=True)
        
        # Construct response with registration indicator
        response = f"{registration_indicator} {domain_value}\nSome other data"
        
        result = client._parse_response(response, tld)
        
        # Result must be FOUND
        assert result.status == WHOISStatus.FOUND, (
            f"Response with registration indicator '{registration_indicator}' "
            f"should be FOUND, got {result.status}"
        )
        
        # no_match_signal_detected must be False
        assert not result.no_match_signal_detected, (
            f"no_match_signal_detected should be False for registered domain"
        )

    @given(
        tld=st.sampled_from(SUPPORTED_TLDS),
        partial_signal_modifier=st.sampled_from([
            lambda s: s.lower(),  # lowercase
            lambda s: s.upper(),  # uppercase
            lambda s: s[:-1],     # truncated
            lambda s: s[1:],      # missing first char
            lambda s: s.replace(" ", "_"),  # modified whitespace
        ]),
    )
    @settings(max_examples=100)
    def test_partial_or_modified_signal_is_ambiguous(
        self, tld: str, partial_signal_modifier
    ) -> None:
        """
        Property 9e: Partial or modified signals are treated as ambiguous.
        
        *For any* WHOIS response containing a modified version of a "no match" signal
        (case changed, truncated, etc.), the parser SHALL return AMBIGUOUS
        because only EXACT matches are accepted.
        
        **Feature: domain-availability-checker, Property 9: Ambiguous WHOIS results in taken**
        **Validates: Requirements 3.4**
        """
        client = WHOISClient(simulation_mode=True)
        
        signals = client.get_signals_for_tld(tld)
        assume(len(signals) > 0)
        
        signal = signals[0]
        modified_signal = partial_signal_modifier(signal)
        
        # Skip if modification didn't actually change the signal
        assume(modified_signal != signal)
        
        # Skip if the modified signal still happens to match
        # (e.g., if original was already lowercase)
        assume(modified_signal not in signals)
        
        response = f"Some header\n{modified_signal}\nSome footer"
        
        # Ensure no registration indicators are present
        assume(_is_ambiguous_response(response, tld) or modified_signal in response)
        
        result = client._parse_response(response, tld)
        
        # If the modified signal doesn't match any exact signal,
        # and doesn't contain registration indicators, it should be AMBIGUOUS
        if modified_signal not in signals and _is_ambiguous_response(response, tld):
            assert result.status == WHOISStatus.AMBIGUOUS, (
                f"Modified signal '{modified_signal}' (from '{signal}') "
                f"should result in AMBIGUOUS, got {result.status}"
            )
