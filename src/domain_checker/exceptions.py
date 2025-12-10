"""
Exception classes for the domain checker system.

All exceptions inherit from DomainCheckerError and provide structured
error information with codes, messages, and optional details.
"""

from typing import Optional


class DomainCheckerError(Exception):
    """Base exception for all domain checker errors."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict:
        """Convert exception to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(DomainCheckerError):
    """Raised when domain validation fails."""

    pass


class NetworkError(DomainCheckerError):
    """Raised when network operations fail."""

    pass


class ProtocolError(DomainCheckerError):
    """Raised when protocol-level errors occur (invalid RDAP response, malformed JSON)."""

    pass


class RateLimitError(DomainCheckerError):
    """Raised when rate limits are exceeded (HTTP 429, soft/hard bans)."""

    pass


class PersistenceError(DomainCheckerError):
    """Raised when persistence operations fail (file I/O, HMAC validation)."""

    pass


class TamperingError(PersistenceError):
    """Raised when HMAC validation fails, indicating data tampering."""

    pass


class NotificationError(DomainCheckerError):
    """Raised when notification delivery fails."""

    pass
