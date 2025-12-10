"""
Enumeration types for the domain checker system.

These enums provide type-safe constants for status codes, error codes,
and configuration options throughout the system.
"""

from enum import Enum


class AvailabilityStatus(Enum):
    """Domain availability status after check."""

    AVAILABLE = "available"
    TAKEN = "taken"
    UNKNOWN = "unknown"


class Confidence(Enum):
    """Confidence level of availability determination."""

    HIGH = "high"
    LOW = "low"


class LogLevel(Enum):
    """Logging severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class DomainValidationErrorCode(Enum):
    """Error codes for domain validation failures."""

    FORBIDDEN_CHARS = "forbidden_chars"
    INVALID_TLD = "invalid_tld"
    IDNA_ERROR = "idna_error"
    EMPTY_INPUT = "empty_input"


class RDAPErrorCode(Enum):
    """Error codes for RDAP client operations."""

    NETWORK_ERROR = "network_error"
    TLS_ERROR = "tls_error"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"


class RDAPStatus(Enum):
    """RDAP query result status."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"


class WHOISErrorCode(Enum):
    """Error codes for WHOIS client operations."""

    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    PARSE_ERROR = "parse_error"
    RATE_LIMITED = "rate_limited"


class WHOISStatus(Enum):
    """WHOIS query result status."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    ERROR = "error"
