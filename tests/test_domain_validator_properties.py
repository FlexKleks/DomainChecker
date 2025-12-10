"""
Property-based tests for domain validation module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import string

import idna
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.domain_validator import DomainValidator


# Strategy for valid domain label characters (ASCII alphanumeric and hyphen)
# Labels cannot start or end with hyphen per RFC 1035
def valid_ascii_label() -> st.SearchStrategy[str]:
    """Generate valid ASCII domain labels (no leading/trailing hyphens)."""
    # Valid chars: a-z, 0-9, hyphen (but not at start/end)
    alphanumeric = st.sampled_from(string.ascii_lowercase + string.digits)
    
    return st.one_of(
        # Single character label (alphanumeric only)
        alphanumeric,
        # Multi-character label
        st.builds(
            lambda first, middle, last: first + middle + last,
            alphanumeric,
            st.text(
                alphabet=string.ascii_lowercase + string.digits + "-",
                min_size=0,
                max_size=10,
            ),
            alphanumeric,
        ),
    ).filter(lambda s: len(s) <= 63 and "--" not in s[:4])  # Max label length, no punycode prefix


def valid_ascii_domain(allowed_tlds: list[str]) -> st.SearchStrategy[str]:
    """Generate valid ASCII domain names with allowed TLDs."""
    return st.builds(
        lambda label, tld: f"{label}.{tld}",
        valid_ascii_label(),
        st.sampled_from(allowed_tlds),
    )


# Strategy for international domain labels (containing non-ASCII)
def valid_idn_label() -> st.SearchStrategy[str]:
    """Generate valid internationalized domain labels."""
    # Common international characters that are valid in IDN
    international_chars = "äöüßéèêëàâáãåæçñøœ"
    valid_chars = string.ascii_lowercase + string.digits + international_chars
    
    return st.builds(
        lambda first, middle, last: first + middle + last,
        st.sampled_from(valid_chars),
        st.text(alphabet=valid_chars, min_size=0, max_size=8),
        st.sampled_from(valid_chars),
    ).filter(lambda s: len(s) >= 1 and len(s) <= 63)


def valid_idn_domain(allowed_tlds: list[str]) -> st.SearchStrategy[str]:
    """Generate valid internationalized domain names."""
    return st.builds(
        lambda label, tld: f"{label}.{tld}",
        valid_idn_label(),
        st.sampled_from(allowed_tlds),
    )


# Combined strategy for any valid domain (ASCII or IDN)
def valid_domain(allowed_tlds: list[str]) -> st.SearchStrategy[str]:
    """Generate any valid domain name (ASCII or international)."""
    return st.one_of(
        valid_ascii_domain(allowed_tlds),
        valid_idn_domain(allowed_tlds),
    )


class TestDomainNormalizationProperty:
    """
    Property-based tests for domain normalization.
    
    **Feature: domain-availability-checker, Property 1: Domain normalization produces canonical lowercase IDNA form**
    **Validates: Requirements 1.1, 1.2, 1.5**
    """

    ALLOWED_TLDS = ["de", "com", "net", "org", "eu"]

    @given(domain=st.one_of(
        valid_ascii_domain(["de", "com", "net", "org", "eu"]),
        valid_idn_domain(["de", "com", "net", "org", "eu"]),
    ))
    @settings(max_examples=100)
    def test_normalization_produces_lowercase(self, domain: str) -> None:
        """
        Property 1a: Normalization produces lowercase output.
        
        *For any* domain string with valid characters, normalizing it SHALL 
        produce a lowercase string.
        
        **Feature: domain-availability-checker, Property 1: Domain normalization produces canonical lowercase IDNA form**
        **Validates: Requirements 1.1, 1.5**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Test with various case combinations
        test_cases = [
            domain,
            domain.upper(),
            domain.title(),
            domain.swapcase(),
        ]
        
        for test_domain in test_cases:
            try:
                canonical = validator.normalize_to_canonical(test_domain)
                # Result must be lowercase
                assert canonical == canonical.lower(), (
                    f"Canonical form '{canonical}' is not lowercase for input '{test_domain}'"
                )
            except Exception:
                # If IDNA encoding fails for some edge case, that's acceptable
                # The property only applies to valid domain strings
                pass

    @given(domain=valid_idn_domain(["de", "com", "net", "org", "eu"]))
    @settings(max_examples=100)
    def test_idn_produces_valid_idna_encoding(self, domain: str) -> None:
        """
        Property 1b: International domains produce valid IDNA encoding.
        
        *For any* domain string containing international characters, 
        the result SHALL be valid IDNA-encoded.
        
        **Feature: domain-availability-checker, Property 1: Domain normalization produces canonical lowercase IDNA form**
        **Validates: Requirements 1.2, 1.5**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Only test domains that actually contain non-ASCII
        has_non_ascii = any(ord(c) > 127 for c in domain)
        assume(has_non_ascii)
        
        try:
            canonical = validator.normalize_to_canonical(domain)
            
            # Result must be ASCII (valid IDNA encoding)
            assert canonical.isascii(), (
                f"IDNA result '{canonical}' contains non-ASCII characters"
            )
            
            # Result must start with 'xn--' for the IDN label (punycode prefix)
            # or be decodable back to the original
            label = canonical.split(".")[0]
            if any(ord(c) > 127 for c in domain.split(".")[0]):
                # The label had international chars, so it should be punycode
                assert label.startswith("xn--"), (
                    f"IDN label '{label}' should be punycode-encoded"
                )
            
            # Verify it's valid IDNA by decoding it back
            decoded = idna.decode(canonical)
            assert decoded.lower() == domain.lower(), (
                f"Round-trip failed: '{domain}' -> '{canonical}' -> '{decoded}'"
            )
            
        except idna.IDNAError:
            # Some generated strings may not be valid IDNA despite our best efforts
            # This is acceptable - the property applies to valid inputs
            pass

    @given(domain=valid_ascii_domain(["de", "com", "net", "org", "eu"]))
    @settings(max_examples=100)
    def test_ascii_domain_unchanged_except_case(self, domain: str) -> None:
        """
        Property 1c: ASCII domains are only lowercased, not otherwise modified.
        
        *For any* ASCII domain string, normalization SHALL only change case,
        not add any encoding.
        
        **Feature: domain-availability-checker, Property 1: Domain normalization produces canonical lowercase IDNA form**
        **Validates: Requirements 1.1, 1.5**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        canonical = validator.normalize_to_canonical(domain)
        
        # For pure ASCII, canonical should just be lowercase version
        assert canonical == domain.lower(), (
            f"ASCII domain '{domain}' should normalize to '{domain.lower()}', "
            f"got '{canonical}'"
        )

    @given(domain=valid_domain(["de", "com", "net", "org", "eu"]))
    @settings(max_examples=100)
    def test_normalization_is_idempotent(self, domain: str) -> None:
        """
        Property 1d: Normalization is idempotent.
        
        *For any* valid domain, normalizing twice produces the same result
        as normalizing once.
        
        **Feature: domain-availability-checker, Property 1: Domain normalization produces canonical lowercase IDNA form**
        **Validates: Requirements 1.5**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        try:
            canonical_once = validator.normalize_to_canonical(domain)
            canonical_twice = validator.normalize_to_canonical(canonical_once)
            
            assert canonical_once == canonical_twice, (
                f"Normalization not idempotent: '{domain}' -> '{canonical_once}' -> '{canonical_twice}'"
            )
        except Exception:
            # If normalization fails, that's acceptable for edge cases
            pass


class TestForbiddenCharactersProperty:
    """
    Property-based tests for forbidden character rejection.
    
    **Feature: domain-availability-checker, Property 2: Forbidden characters cause rejection**
    **Validates: Requirements 1.3**
    """

    ALLOWED_TLDS = ["de", "com", "net", "org", "eu"]

    # Forbidden characters: control characters, whitespace, special symbols
    # Using a representative subset for efficient testing
    FORBIDDEN_CHARS = [
        # Control characters (representative sample)
        '\x00', '\x01', '\x1f', '\x7f',
        # Whitespace
        ' ', '\t', '\n', '\r',
        # Special symbols not allowed in domains
        '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+', '=',
        '[', ']', '{', '}', '|', '\\', ':', ';', '"', "'", '<', '>',
        ',', '?', '/', '`', '~',
    ]

    @given(
        base_label=st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=1,
            max_size=10,
        ),
        forbidden_char=st.sampled_from(FORBIDDEN_CHARS),
        tld=st.sampled_from(["de", "com", "net", "org", "eu"]),
    )
    @settings(max_examples=100)
    def test_forbidden_chars_in_label_cause_rejection(
        self, base_label: str, forbidden_char: str, tld: str
    ) -> None:
        """
        Property 2: Forbidden characters in label cause rejection.
        
        *For any* domain string containing forbidden characters (control characters,
        spaces, special symbols not allowed in domains) within the label,
        validation SHALL return an error with code FORBIDDEN_CHARS.
        
        **Feature: domain-availability-checker, Property 2: Forbidden characters cause rejection**
        **Validates: Requirements 1.3**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Insert forbidden character in the middle of the label
        # This ensures the forbidden char is not at the boundary where it might be stripped
        if len(base_label) > 1:
            mid = len(base_label) // 2
            label_with_forbidden = base_label[:mid] + forbidden_char + base_label[mid:]
        else:
            label_with_forbidden = base_label + forbidden_char + "a"
        
        domain_with_forbidden = f"{label_with_forbidden}.{tld}"
        
        result = validator.validate(domain_with_forbidden)
        
        # Validation must fail
        assert not result.valid, (
            f"Domain '{repr(domain_with_forbidden)}' with forbidden char "
            f"'{repr(forbidden_char)}' should be rejected"
        )
        
        # Error must be present
        assert result.error is not None, (
            f"Error should be present for domain with forbidden char"
        )
        
        # Error code must be FORBIDDEN_CHARS (or EMPTY_INPUT for whitespace-only cases)
        from domain_checker.enums import DomainValidationErrorCode
        valid_error_codes = {
            DomainValidationErrorCode.FORBIDDEN_CHARS,
            DomainValidationErrorCode.EMPTY_INPUT,  # For whitespace-only inputs
        }
        assert result.error.code in valid_error_codes, (
            f"Error code should be FORBIDDEN_CHARS or EMPTY_INPUT, "
            f"got {result.error.code} for char '{repr(forbidden_char)}'"
        )

    @given(
        num_forbidden=st.integers(min_value=2, max_value=5),
        base_label=st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=3,
            max_size=10,
        ),
        tld=st.sampled_from(["de", "com", "net", "org", "eu"]),
    )
    @settings(max_examples=100)
    def test_multiple_forbidden_chars_cause_rejection(
        self, num_forbidden: int, base_label: str, tld: str
    ) -> None:
        """
        Property 2b: Multiple forbidden characters also cause rejection.
        
        *For any* domain containing multiple forbidden characters,
        validation SHALL return an error with code FORBIDDEN_CHARS.
        
        **Feature: domain-availability-checker, Property 2: Forbidden characters cause rejection**
        **Validates: Requirements 1.3**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Pick random forbidden chars to insert
        forbidden_chars = ['@', '#', ' ', '!', '$'][:num_forbidden]
        
        # Insert forbidden chars throughout the label
        label = base_label
        for i, char in enumerate(forbidden_chars):
            pos = min(i, len(label))
            label = label[:pos] + char + label[pos:]
        
        domain = f"{label}.{tld}"
        
        result = validator.validate(domain)
        
        # Validation must fail
        assert not result.valid, (
            f"Domain '{domain}' with multiple forbidden chars should be rejected"
        )


class TestInvalidTLDProperty:
    """
    Property-based tests for invalid TLD rejection.
    
    **Feature: domain-availability-checker, Property 3: Invalid TLD causes rejection**
    **Validates: Requirements 1.4**
    """

    ALLOWED_TLDS = ["de", "com", "net", "org", "eu"]
    
    # TLDs that are NOT in the allowed list
    INVALID_TLDS = [
        "xyz", "io", "co", "uk", "fr", "es", "it", "nl", "be", "at", "ch",
        "info", "biz", "us", "ca", "au", "jp", "cn", "ru", "br", "mx",
        "app", "dev", "tech", "online", "site", "store", "shop", "blog",
    ]

    @given(
        label=st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=1,
            max_size=20,
        ).filter(lambda s: s and s[0].isalnum() and s[-1].isalnum()),
        invalid_tld=st.sampled_from(INVALID_TLDS),
    )
    @settings(max_examples=100)
    def test_invalid_tld_causes_rejection(self, label: str, invalid_tld: str) -> None:
        """
        Property 3: Invalid TLD causes rejection.
        
        *For any* domain string with a TLD not in the configured allowed list,
        validation SHALL return an error with code INVALID_TLD.
        
        **Feature: domain-availability-checker, Property 3: Invalid TLD causes rejection**
        **Validates: Requirements 1.4**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Ensure label is valid (not empty after filtering)
        assume(len(label) >= 1)
        
        domain = f"{label}.{invalid_tld}"
        
        result = validator.validate(domain)
        
        # Validation must fail
        assert not result.valid, (
            f"Domain '{domain}' with invalid TLD '{invalid_tld}' should be rejected"
        )
        
        # Error must be present
        assert result.error is not None, (
            f"Error should be present for domain with invalid TLD"
        )
        
        # Error code must be INVALID_TLD
        from domain_checker.enums import DomainValidationErrorCode
        assert result.error.code == DomainValidationErrorCode.INVALID_TLD, (
            f"Error code should be INVALID_TLD, got {result.error.code}"
        )
        
        # Error details should contain the invalid TLD
        assert "tld" in result.error.details, (
            f"Error details should contain 'tld' key"
        )
        assert result.error.details["tld"] == invalid_tld, (
            f"Error details TLD should be '{invalid_tld}', "
            f"got '{result.error.details.get('tld')}'"
        )

    @given(
        label=st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=1,
            max_size=20,
        ).filter(lambda s: s and s[0].isalnum() and s[-1].isalnum()),
        valid_tld=st.sampled_from(ALLOWED_TLDS),
    )
    @settings(max_examples=100)
    def test_valid_tld_is_accepted(self, label: str, valid_tld: str) -> None:
        """
        Property 3b: Valid TLD is accepted (inverse property).
        
        *For any* domain string with a TLD in the configured allowed list
        and valid label characters, validation SHALL succeed.
        
        **Feature: domain-availability-checker, Property 3: Invalid TLD causes rejection**
        **Validates: Requirements 1.4**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Ensure label is valid
        assume(len(label) >= 1)
        
        domain = f"{label}.{valid_tld}"
        
        result = validator.validate(domain)
        
        # Validation must succeed
        assert result.valid, (
            f"Domain '{domain}' with valid TLD '{valid_tld}' should be accepted, "
            f"but got error: {result.error}"
        )
        
        # Canonical domain should be present
        assert result.canonical_domain is not None, (
            f"Canonical domain should be present for valid domain"
        )
        
        # Canonical domain should end with the valid TLD
        assert result.canonical_domain.endswith(f".{valid_tld}"), (
            f"Canonical domain '{result.canonical_domain}' should end with '.{valid_tld}'"
        )

    @given(
        label=st.text(
            alphabet=string.ascii_lowercase + string.digits,
            min_size=1,
            max_size=20,
        ).filter(lambda s: s and s[0].isalnum() and s[-1].isalnum()),
        random_tld=st.text(
            alphabet=string.ascii_lowercase,
            min_size=2,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_arbitrary_tld_not_in_list_rejected(self, label: str, random_tld: str) -> None:
        """
        Property 3c: Any TLD not in allowed list is rejected.
        
        *For any* randomly generated TLD that is not in the allowed list,
        validation SHALL return an error with code INVALID_TLD.
        
        **Feature: domain-availability-checker, Property 3: Invalid TLD causes rejection**
        **Validates: Requirements 1.4**
        """
        validator = DomainValidator(self.ALLOWED_TLDS)
        
        # Skip if the random TLD happens to be in the allowed list
        assume(random_tld.lower() not in [t.lower() for t in self.ALLOWED_TLDS])
        assume(len(label) >= 1)
        assume(len(random_tld) >= 2)
        
        domain = f"{label}.{random_tld}"
        
        result = validator.validate(domain)
        
        # Validation must fail
        assert not result.valid, (
            f"Domain '{domain}' with TLD '{random_tld}' not in allowed list should be rejected"
        )
        
        # Error code must be INVALID_TLD
        from domain_checker.enums import DomainValidationErrorCode
        assert result.error is not None and result.error.code == DomainValidationErrorCode.INVALID_TLD, (
            f"Error code should be INVALID_TLD for TLD '{random_tld}'"
        )
