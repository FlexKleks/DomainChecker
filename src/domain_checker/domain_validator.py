"""
Domain validation and normalization module.

Provides domain validation, normalization to canonical form, and TLD validation
according to Requirements 1.1-1.5.
"""

import re
from dataclasses import dataclass
from typing import Optional

import idna

from domain_checker.enums import DomainValidationErrorCode
from domain_checker.exceptions import ValidationError


# Forbidden characters in domain names (control chars, spaces, special symbols)
# Based on RFC 1035 and RFC 5891 (IDNA2008)
# Valid domain characters: a-z, A-Z, 0-9, hyphen (-), dot (.), and non-ASCII for IDN
FORBIDDEN_CHARS_PATTERN = re.compile(
    r'[\x00-\x1f\x7f'           # Control characters
    r'\s'                        # Whitespace
    r'!@#$%^&*()+=\[\]{}|\\:;"\'<>,?/`~]'  # Special symbols not allowed
)


@dataclass
class DomainValidationError:
    """Structured error information for domain validation failures."""

    code: DomainValidationErrorCode
    message: str
    details: dict


@dataclass
class DomainValidationResult:
    """Result of domain validation operation."""

    valid: bool
    canonical_domain: Optional[str]
    error: Optional[DomainValidationError]


class DomainValidator:
    """
    Validates and normalizes domain names.

    Handles:
    - Conversion to lowercase canonical form (Req 1.1)
    - IDNA encoding for international characters (Req 1.2)
    - Rejection of forbidden characters (Req 1.3)
    - TLD validation against configured list (Req 1.4)
    - Storage in canonical form (Req 1.5)
    """

    def __init__(self, allowed_tlds: list[str]) -> None:
        """
        Initialize validator with allowed TLDs.

        Args:
            allowed_tlds: List of allowed top-level domains (e.g., ['de', 'com', 'eu'])
        """
        self._allowed_tlds = set(tld.lower() for tld in allowed_tlds)

    def validate(self, raw_domain: str) -> DomainValidationResult:
        """
        Validate and normalize a domain string.

        Args:
            raw_domain: The raw domain string to validate

        Returns:
            DomainValidationResult with validation status and canonical form or error
        """
        # Check for empty input
        if not raw_domain or not raw_domain.strip():
            return DomainValidationResult(
                valid=False,
                canonical_domain=None,
                error=DomainValidationError(
                    code=DomainValidationErrorCode.EMPTY_INPUT,
                    message="Domain input is empty",
                    details={"raw_input": raw_domain},
                ),
            )

        # Strip whitespace from ends
        domain = raw_domain.strip()

        # Check for forbidden characters before normalization
        if FORBIDDEN_CHARS_PATTERN.search(domain):
            forbidden_found = FORBIDDEN_CHARS_PATTERN.findall(domain)
            return DomainValidationResult(
                valid=False,
                canonical_domain=None,
                error=DomainValidationError(
                    code=DomainValidationErrorCode.FORBIDDEN_CHARS,
                    message="Domain contains forbidden characters",
                    details={
                        "raw_input": raw_domain,
                        "forbidden_chars": forbidden_found,
                    },
                ),
            )

        # Normalize to canonical form
        try:
            canonical = self.normalize_to_canonical(domain)
        except ValidationError as e:
            return DomainValidationResult(
                valid=False,
                canonical_domain=None,
                error=DomainValidationError(
                    code=DomainValidationErrorCode.IDNA_ERROR,
                    message=str(e.message),
                    details=e.details,
                ),
            )

        # Extract and validate TLD
        tld = self._extract_tld(canonical)
        if not tld:
            return DomainValidationResult(
                valid=False,
                canonical_domain=None,
                error=DomainValidationError(
                    code=DomainValidationErrorCode.INVALID_TLD,
                    message="Could not extract TLD from domain",
                    details={"raw_input": raw_domain, "canonical": canonical},
                ),
            )

        if not self.is_valid_tld(tld):
            return DomainValidationResult(
                valid=False,
                canonical_domain=None,
                error=DomainValidationError(
                    code=DomainValidationErrorCode.INVALID_TLD,
                    message=f"TLD '{tld}' is not in the configured allowed list",
                    details={
                        "raw_input": raw_domain,
                        "tld": tld,
                        "allowed_tlds": list(self._allowed_tlds),
                    },
                ),
            )

        return DomainValidationResult(
            valid=True,
            canonical_domain=canonical,
            error=None,
        )

    def normalize_to_canonical(self, domain: str) -> str:
        """
        Convert domain to canonical form (lowercase, IDNA-encoded).

        Args:
            domain: Domain string to normalize

        Returns:
            Canonical form of the domain (lowercase, IDNA if needed)

        Raises:
            ValidationError: If IDNA encoding fails
        """
        # Convert to lowercase first
        domain_lower = domain.lower()

        # Check if domain contains non-ASCII characters (international domain)
        has_non_ascii = any(ord(c) > 127 for c in domain_lower)

        if has_non_ascii:
            try:
                # Encode using IDNA (Internationalized Domain Names in Applications)
                # Use IDNA 2008 via the idna library
                canonical = idna.encode(domain_lower, uts46=True).decode("ascii")
            except idna.IDNAError as e:
                raise ValidationError(
                    code=DomainValidationErrorCode.IDNA_ERROR.value,
                    message=f"IDNA encoding failed: {e}",
                    details={"domain": domain, "idna_error": str(e)},
                )
        else:
            canonical = domain_lower

        return canonical

    def is_valid_tld(self, tld: str) -> bool:
        """
        Check if TLD is in the allowed list.

        Args:
            tld: Top-level domain to check (without leading dot)

        Returns:
            True if TLD is allowed, False otherwise
        """
        return tld.lower() in self._allowed_tlds

    def _extract_tld(self, domain: str) -> Optional[str]:
        """
        Extract TLD from a domain name.

        Args:
            domain: Domain name (e.g., 'example.com')

        Returns:
            TLD string (e.g., 'com') or None if extraction fails
        """
        if not domain or "." not in domain:
            return None

        parts = domain.rsplit(".", 1)
        if len(parts) != 2 or not parts[1]:
            return None

        return parts[1].lower()
