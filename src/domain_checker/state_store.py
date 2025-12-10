"""
State Store module for persistent domain check results.

This module provides HMAC-protected storage for domain check results,
ensuring data integrity and detecting tampering.
"""

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .exceptions import PersistenceError, TamperingError
from .models import (
    CheckHistoryEntry,
    CheckResult,
    DomainState,
    StoredState,
)


class StateStore:
    """
    Persistent state storage with HMAC protection.
    
    Stores domain check results to disk with HMAC validation to detect
    tampering. Supports loading, saving, and updating domain states.
    """
    
    VERSION = 1
    
    def __init__(self, file_path: Path, hmac_secret: str) -> None:
        """
        Initialize the state store.
        
        Args:
            file_path: Path to the state file (JSON format)
            hmac_secret: Secret key for HMAC computation
        """
        self._file_path = file_path
        self._hmac_secret = hmac_secret.encode("utf-8")
        self._state: Optional[StoredState] = None
    
    def load(self) -> Optional[StoredState]:
        """
        Load state from file and validate HMAC.
        
        Returns:
            StoredState if file exists and is valid, None if file doesn't exist
            
        Raises:
            TamperingError: If HMAC validation fails
            PersistenceError: If file cannot be read or parsed
        """
        if not self._file_path.exists():
            return None
        
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            raise PersistenceError(
                code="parse_error",
                message=f"Failed to parse state file: {e}",
                details={"file_path": str(self._file_path)},
            )
        except OSError as e:
            raise PersistenceError(
                code="io_error",
                message=f"Failed to read state file: {e}",
                details={"file_path": str(self._file_path)},
            )
        
        # Extract stored HMAC
        stored_hmac = raw_data.get("hmac", "")
        
        # Compute HMAC over data (excluding hmac field)
        data_for_hmac = {
            "version": raw_data.get("version"),
            "domains": raw_data.get("domains", {}),
            "last_updated": raw_data.get("last_updated"),
        }
        computed_hmac = self.compute_hmac(data_for_hmac)
        
        # Validate HMAC
        if not self.validate_hmac(stored_hmac, computed_hmac):
            raise TamperingError(
                code="hmac_mismatch",
                message="HMAC validation failed - data may have been tampered with",
                details={
                    "file_path": str(self._file_path),
                    "expected_hmac": computed_hmac,
                    "stored_hmac": stored_hmac,
                },
            )
        
        # Reconstruct StoredState
        domains = {}
        for domain_name, domain_data in raw_data.get("domains", {}).items():
            check_history = [
                CheckHistoryEntry(
                    timestamp=entry["timestamp"],
                    status=entry["status"],
                    sources=entry["sources"],
                )
                for entry in domain_data.get("check_history", [])
            ]
            domains[domain_name] = DomainState(
                canonical_domain=domain_data["canonical_domain"],
                last_status=domain_data["last_status"],
                last_checked=domain_data["last_checked"],
                last_notified=domain_data.get("last_notified"),
                check_history=check_history,
            )
        
        self._state = StoredState(
            version=raw_data.get("version", self.VERSION),
            domains=domains,
            last_updated=raw_data.get("last_updated", ""),
            hmac=stored_hmac,
        )
        
        return self._state
    
    def save(self, state: Optional[StoredState] = None) -> None:
        """
        Save state to file with HMAC protection.
        
        Args:
            state: State to save. If None, saves the current internal state.
            
        Raises:
            PersistenceError: If file cannot be written
        """
        if state is not None:
            self._state = state
        
        if self._state is None:
            raise PersistenceError(
                code="no_state",
                message="No state to save",
                details={},
            )
        
        # Update timestamp
        now = datetime.now(timezone.utc).isoformat()
        
        # Prepare data for serialization
        domains_dict = {}
        for domain_name, domain_state in self._state.domains.items():
            domains_dict[domain_name] = {
                "canonical_domain": domain_state.canonical_domain,
                "last_status": domain_state.last_status,
                "last_checked": domain_state.last_checked,
                "last_notified": domain_state.last_notified,
                "check_history": [
                    {
                        "timestamp": entry.timestamp,
                        "status": entry.status,
                        "sources": entry.sources,
                    }
                    for entry in domain_state.check_history
                ],
            }
        
        # Compute HMAC over data
        data_for_hmac = {
            "version": self._state.version,
            "domains": domains_dict,
            "last_updated": now,
        }
        computed_hmac = self.compute_hmac(data_for_hmac)
        
        # Build final data with HMAC
        output_data = {
            "version": self._state.version,
            "domains": domains_dict,
            "last_updated": now,
            "hmac": computed_hmac,
        }
        
        # Ensure parent directory exists
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, sort_keys=True)
        except OSError as e:
            raise PersistenceError(
                code="io_error",
                message=f"Failed to write state file: {e}",
                details={"file_path": str(self._file_path)},
            )
        
        # Update internal state with new HMAC and timestamp
        self._state = StoredState(
            version=self._state.version,
            domains=self._state.domains,
            last_updated=now,
            hmac=computed_hmac,
        )
    
    def get_domain_state(self, domain: str) -> Optional[DomainState]:
        """
        Get the state for a specific domain.
        
        Args:
            domain: The canonical domain name
            
        Returns:
            DomainState if found, None otherwise
        """
        if self._state is None:
            return None
        return self._state.domains.get(domain)
    
    def update_domain_state(self, domain: str, result: CheckResult) -> None:
        """
        Update domain state based on a check result.
        
        Creates a new DomainState if the domain doesn't exist, or updates
        the existing state with new check information.
        
        Args:
            domain: The canonical domain name
            result: The check result to store
        """
        if self._state is None:
            # Initialize empty state
            self._state = StoredState(
                version=self.VERSION,
                domains={},
                last_updated="",
                hmac="",
            )
        
        # Create history entry from result
        history_entry = CheckHistoryEntry(
            timestamp=result.timestamp,
            status=result.status.value,
            sources=[src.source for src in result.sources],
        )
        
        existing_state = self._state.domains.get(domain)
        
        if existing_state is not None:
            # Update existing state
            check_history = existing_state.check_history.copy()
            check_history.append(history_entry)
            
            # Keep only last 100 history entries to prevent unbounded growth
            if len(check_history) > 100:
                check_history = check_history[-100:]
            
            new_state = DomainState(
                canonical_domain=domain,
                last_status=result.status.value,
                last_checked=result.timestamp,
                last_notified=existing_state.last_notified,
                check_history=check_history,
            )
        else:
            # Create new state
            new_state = DomainState(
                canonical_domain=domain,
                last_status=result.status.value,
                last_checked=result.timestamp,
                last_notified=None,
                check_history=[history_entry],
            )
        
        self._state.domains[domain] = new_state
    
    def mark_notified(self, domain: str, timestamp: str) -> None:
        """
        Mark a domain as having been notified.
        
        Args:
            domain: The canonical domain name
            timestamp: The notification timestamp
        """
        if self._state is None or domain not in self._state.domains:
            return
        
        existing = self._state.domains[domain]
        self._state.domains[domain] = DomainState(
            canonical_domain=existing.canonical_domain,
            last_status=existing.last_status,
            last_checked=existing.last_checked,
            last_notified=timestamp,
            check_history=existing.check_history,
        )
    
    def compute_hmac(self, data: dict) -> str:
        """
        Compute HMAC-SHA256 over serialized data.
        
        Args:
            data: Dictionary to compute HMAC over
            
        Returns:
            Hexadecimal HMAC string
        """
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hmac.new(
            self._hmac_secret,
            serialized.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    
    def validate_hmac(self, stored_hmac: str, computed_hmac: str) -> bool:
        """
        Validate HMAC using constant-time comparison.
        
        Args:
            stored_hmac: The HMAC stored in the file
            computed_hmac: The freshly computed HMAC
            
        Returns:
            True if HMACs match, False otherwise
        """
        return hmac.compare_digest(stored_hmac, computed_hmac)
    
    @property
    def state(self) -> Optional[StoredState]:
        """Get the current internal state."""
        return self._state
    
    @property
    def file_path(self) -> Path:
        """Get the state file path."""
        return self._file_path
