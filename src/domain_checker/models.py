"""
Data models for the domain checker system.

This module defines all data structures used for domain representation,
check results, state persistence, and session management.
"""

from dataclasses import dataclass, field
from typing import Optional

from .enums import AvailabilityStatus, Confidence


@dataclass
class Domain:
    """Represents a domain with its normalized form."""

    raw: str  # Original input
    canonical: str  # Normalized form (lowercase, IDNA)
    tld: str  # Extracted TLD
    sld: str  # Second-level domain
    is_idn: bool = False  # Contains international characters


@dataclass
class SourceResult:
    """Result from a single data source (RDAP/WHOIS)."""

    source: str  # 'rdap_primary', 'rdap_secondary', 'whois'
    status: str  # 'found', 'not_found', 'error'
    http_status_code: Optional[int] = None
    response_time_ms: float = 0.0


@dataclass
class CheckMetadata:
    """Metadata about a domain check operation."""

    total_duration_ms: float
    retry_count: int = 0
    rate_limit_delays: int = 0


@dataclass
class CheckResult:
    """Complete result of a domain availability check."""

    domain: str
    status: AvailabilityStatus
    confidence: Confidence
    sources: list[SourceResult]
    timestamp: str
    metadata: CheckMetadata


@dataclass
class CheckHistoryEntry:
    """A single entry in the check history for a domain."""

    timestamp: str
    status: str
    sources: list[str]


@dataclass
class DomainState:
    """Persistent state for a single domain."""

    canonical_domain: str
    last_status: str
    last_checked: str
    last_notified: Optional[str] = None
    check_history: list[CheckHistoryEntry] = field(default_factory=list)


@dataclass
class StoredState:
    """Complete stored state with HMAC protection."""

    version: int
    domains: dict[str, DomainState]
    last_updated: str
    hmac: str


@dataclass
class SessionError:
    """Error that occurred during a check session."""

    domain: str
    error: str
    timestamp: str


@dataclass
class CheckSession:
    """A session containing multiple domain checks."""

    id: str
    start_time: str
    end_time: Optional[str]
    domains: list[str]
    results: dict[str, CheckResult] = field(default_factory=dict)
    errors: list[SessionError] = field(default_factory=list)


@dataclass
class PersistedData:
    """
    Generic wrapper for all persisted data with HMAC protection.

    All data stored to disk uses this format to ensure integrity.
    """

    version: int
    created_at: str
    updated_at: str
    data: dict
    hmac: str  # HMAC-SHA256 over json.dumps(data, sort_keys=True)
