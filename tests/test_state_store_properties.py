"""
Property-based tests for State Store module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.enums import AvailabilityStatus, Confidence
from domain_checker.exceptions import TamperingError
from domain_checker.models import (
    CheckHistoryEntry,
    CheckMetadata,
    CheckResult,
    DomainState,
    SourceResult,
    StoredState,
)
from domain_checker.state_store import StateStore


# Strategies for generating valid test data

@st.composite
def timestamp_strategy(draw) -> str:
    """Generate valid ISO format timestamps."""
    year = draw(st.integers(min_value=2020, max_value=2030))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    second = draw(st.integers(min_value=0, max_value=59))
    return f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}+00:00"


@st.composite
def check_history_entry_strategy(draw) -> CheckHistoryEntry:
    """Generate valid CheckHistoryEntry objects."""
    return CheckHistoryEntry(
        timestamp=draw(timestamp_strategy()),
        status=draw(st.sampled_from(["available", "taken", "unknown"])),
        sources=draw(st.lists(
            st.sampled_from(["rdap_primary", "rdap_secondary", "whois"]),
            min_size=1,
            max_size=3,
            unique=True,
        )),
    )


@st.composite
def domain_state_strategy(draw) -> DomainState:
    """Generate valid DomainState objects."""
    # Generate a valid domain name
    sld = draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
        min_size=1,
        max_size=20,
    ))
    tld = draw(st.sampled_from(["de", "com", "net", "org", "eu"]))
    canonical_domain = f"{sld}.{tld}"
    
    return DomainState(
        canonical_domain=canonical_domain,
        last_status=draw(st.sampled_from(["available", "taken", "unknown"])),
        last_checked=draw(timestamp_strategy()),
        last_notified=draw(st.one_of(st.none(), timestamp_strategy())),
        check_history=draw(st.lists(
            check_history_entry_strategy(),
            min_size=0,
            max_size=10,
        )),
    )


@st.composite
def stored_state_strategy(draw) -> StoredState:
    """Generate valid StoredState objects."""
    # Generate domain states with unique domain names
    num_domains = draw(st.integers(min_value=0, max_value=5))
    domains = {}
    for i in range(num_domains):
        state = draw(domain_state_strategy())
        # Ensure unique domain names by appending index
        unique_domain = f"domain{i}.{state.canonical_domain.split('.')[-1]}"
        state = DomainState(
            canonical_domain=unique_domain,
            last_status=state.last_status,
            last_checked=state.last_checked,
            last_notified=state.last_notified,
            check_history=state.check_history,
        )
        domains[unique_domain] = state
    
    return StoredState(
        version=1,
        domains=domains,
        last_updated=draw(timestamp_strategy()),
        hmac="",  # Will be computed during save
    )


@st.composite
def source_result_strategy(draw) -> SourceResult:
    """Generate valid SourceResult objects."""
    return SourceResult(
        source=draw(st.sampled_from(["rdap_primary", "rdap_secondary", "whois"])),
        status=draw(st.sampled_from(["found", "not_found", "error"])),
        http_status_code=draw(st.one_of(
            st.none(),
            st.sampled_from([200, 404, 429, 500, 503]),
        )),
        response_time_ms=draw(st.floats(min_value=0.0, max_value=10000.0)),
    )


@st.composite
def check_result_strategy(draw) -> CheckResult:
    """Generate valid CheckResult objects."""
    sld = draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
        min_size=1,
        max_size=20,
    ))
    tld = draw(st.sampled_from(["de", "com", "net", "org", "eu"]))
    domain = f"{sld}.{tld}"
    
    return CheckResult(
        domain=domain,
        status=draw(st.sampled_from(list(AvailabilityStatus))),
        confidence=draw(st.sampled_from(list(Confidence))),
        sources=draw(st.lists(source_result_strategy(), min_size=1, max_size=3)),
        timestamp=draw(timestamp_strategy()),
        metadata=CheckMetadata(
            total_duration_ms=draw(st.floats(min_value=0.0, max_value=60000.0)),
            retry_count=draw(st.integers(min_value=0, max_value=5)),
            rate_limit_delays=draw(st.integers(min_value=0, max_value=10)),
        ),
    )


@st.composite
def hmac_secret_strategy(draw) -> str:
    """Generate valid HMAC secrets."""
    return draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        min_size=16,
        max_size=64,
    ))


class TestHMACProtectionProperty:
    """
    Property-based tests for HMAC protection.
    
    **Feature: domain-availability-checker, Property 19: HMAC protects stored data**
    **Validates: Requirements 7.2**
    """

    @given(
        state=stored_state_strategy(),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_hmac_protects_stored_data(self, state: StoredState, secret: str) -> None:
        """
        Property 19: HMAC protects stored data.
        
        *For any* StoredState, the computed HMAC over the data (excluding the hmac field)
        SHALL match the stored hmac field. Modifying any data field SHALL cause HMAC
        validation to fail.
        
        **Feature: domain-availability-checker, Property 19: HMAC protects stored data**
        **Validates: Requirements 7.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Save state
            store.save(state)
            
            # Load and verify HMAC matches
            loaded = store.load()
            assert loaded is not None
            
            # Verify the stored HMAC is valid
            data_for_hmac = {
                "version": loaded.version,
                "domains": self._domains_to_dict(loaded.domains),
                "last_updated": loaded.last_updated,
            }
            computed = store.compute_hmac(data_for_hmac)
            assert store.validate_hmac(loaded.hmac, computed)
    
    @given(
        state=stored_state_strategy(),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_modified_data_fails_hmac_validation(self, state: StoredState, secret: str) -> None:
        """
        Property 19b: Modified data fails HMAC validation.
        
        *For any* stored state, modifying any data field SHALL cause HMAC validation to fail.
        
        **Feature: domain-availability-checker, Property 19: HMAC protects stored data**
        **Validates: Requirements 7.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Save state
            store.save(state)
            
            # Read raw file and modify data
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            # Modify the version field
            raw_data["version"] = raw_data["version"] + 1
            
            # Write back modified data (keeping original HMAC)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f)
            
            # Loading should fail with TamperingError
            store2 = StateStore(file_path, secret)
            try:
                store2.load()
                assert False, "Expected TamperingError"
            except TamperingError:
                pass  # Expected
    
    def _domains_to_dict(self, domains: dict[str, DomainState]) -> dict:
        """Convert domains dict to serializable format."""
        result = {}
        for name, state in domains.items():
            result[name] = {
                "canonical_domain": state.canonical_domain,
                "last_status": state.last_status,
                "last_checked": state.last_checked,
                "last_notified": state.last_notified,
                "check_history": [
                    {
                        "timestamp": e.timestamp,
                        "status": e.status,
                        "sources": e.sources,
                    }
                    for e in state.check_history
                ],
            }
        return result


class TestStateRoundTripProperty:
    """
    Property-based tests for state round-trip.
    
    **Feature: domain-availability-checker, Property 20: State data round-trips without data loss**
    **Validates: Requirements 13.2**
    """

    @given(
        state=stored_state_strategy(),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_state_round_trip_preserves_data(self, state: StoredState, secret: str) -> None:
        """
        Property 20: State data round-trips without data loss.
        
        *For any* valid StoredState object, serializing to JSON and deserializing back
        SHALL produce an equivalent StoredState object.
        
        **Feature: domain-availability-checker, Property 20: State data round-trips without data loss**
        **Validates: Requirements 13.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Save state
            store.save(state)
            
            # Load state back
            loaded = store.load()
            assert loaded is not None
            
            # Verify version matches
            assert loaded.version == state.version
            
            # Verify all domains are preserved
            assert set(loaded.domains.keys()) == set(state.domains.keys())
            
            for domain_name in state.domains:
                orig = state.domains[domain_name]
                recon = loaded.domains[domain_name]
                
                assert recon.canonical_domain == orig.canonical_domain
                assert recon.last_status == orig.last_status
                assert recon.last_checked == orig.last_checked
                assert recon.last_notified == orig.last_notified
                
                # Verify check history
                assert len(recon.check_history) == len(orig.check_history)
                for orig_entry, recon_entry in zip(orig.check_history, recon.check_history):
                    assert recon_entry.timestamp == orig_entry.timestamp
                    assert recon_entry.status == orig_entry.status
                    assert recon_entry.sources == orig_entry.sources

    @given(
        state=stored_state_strategy(),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_state_round_trip_is_idempotent(self, state: StoredState, secret: str) -> None:
        """
        Property 20b: State round-trip is idempotent.
        
        *For any* valid StoredState, round-tripping twice produces the same result
        as round-tripping once.
        
        **Feature: domain-availability-checker, Property 20: State data round-trips without data loss**
        **Validates: Requirements 13.2**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # First round-trip
            store.save(state)
            loaded1 = store.load()
            
            # Second round-trip
            store.save(loaded1)
            loaded2 = store.load()
            
            # Read raw JSON for comparison
            with open(file_path, "r", encoding="utf-8") as f:
                json1 = f.read()
            
            store.save(loaded2)
            with open(file_path, "r", encoding="utf-8") as f:
                json2 = f.read()
            
            # JSON should be identical after second round-trip
            # (timestamps may differ, so we compare structure)
            data1 = json.loads(json1)
            data2 = json.loads(json2)
            
            # Compare domains (excluding last_updated which changes)
            assert data1["domains"] == data2["domains"]
            assert data1["version"] == data2["version"]


class TestInvalidHMACRejectionProperty:
    """
    Property-based tests for invalid HMAC rejection.
    
    **Feature: domain-availability-checker, Property 22: Invalid HMAC causes rejection**
    **Validates: Requirements 13.4**
    """

    @given(
        state=stored_state_strategy(),
        secret=hmac_secret_strategy(),
        tampered_hmac=st.text(
            alphabet=st.sampled_from("0123456789abcdef"),
            min_size=64,
            max_size=64,
        ),
    )
    @settings(max_examples=100)
    def test_invalid_hmac_causes_rejection(
        self, state: StoredState, secret: str, tampered_hmac: str
    ) -> None:
        """
        Property 22: Invalid HMAC causes rejection.
        
        *For any* stored JSON data where the hmac field does not match the computed
        HMAC of the data, loading SHALL fail with a tampering error.
        
        **Feature: domain-availability-checker, Property 22: Invalid HMAC causes rejection**
        **Validates: Requirements 13.4**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Save state
            store.save(state)
            
            # Read and tamper with HMAC
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            original_hmac = raw_data["hmac"]
            
            # Only test if tampered HMAC is different from original
            assume(tampered_hmac != original_hmac)
            
            raw_data["hmac"] = tampered_hmac
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(raw_data, f)
            
            # Loading should fail with TamperingError
            store2 = StateStore(file_path, secret)
            try:
                store2.load()
                assert False, "Expected TamperingError for invalid HMAC"
            except TamperingError as e:
                assert e.code == "hmac_mismatch"

    @given(
        state=stored_state_strategy(),
        secret1=hmac_secret_strategy(),
        secret2=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_wrong_secret_causes_rejection(
        self, state: StoredState, secret1: str, secret2: str
    ) -> None:
        """
        Property 22b: Wrong secret causes rejection.
        
        *For any* stored state, loading with a different secret SHALL fail.
        
        **Feature: domain-availability-checker, Property 22: Invalid HMAC causes rejection**
        **Validates: Requirements 13.4**
        """
        # Only test if secrets are different
        assume(secret1 != secret2)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            
            # Save with secret1
            store1 = StateStore(file_path, secret1)
            store1.save(state)
            
            # Try to load with secret2
            store2 = StateStore(file_path, secret2)
            try:
                store2.load()
                assert False, "Expected TamperingError for wrong secret"
            except TamperingError:
                pass  # Expected


class TestStoredMetadataProperty:
    """
    Property-based tests for stored metadata.
    
    **Feature: domain-availability-checker, Property 18: Check results stored with timestamp and metadata**
    **Validates: Requirements 7.1, 7.4**
    """

    @given(
        result=check_result_strategy(),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_check_results_stored_with_timestamp_and_metadata(
        self, result: CheckResult, secret: str
    ) -> None:
        """
        Property 18: Check results stored with timestamp and metadata.
        
        *For any* completed domain check, the stored DomainState SHALL contain:
        last_checked timestamp, last_status, and check_history with source information.
        
        **Feature: domain-availability-checker, Property 18: Check results stored with timestamp and metadata**
        **Validates: Requirements 7.1, 7.4**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Update domain state with check result
            store.update_domain_state(result.domain, result)
            
            # Save and reload
            store.save()
            loaded = store.load()
            
            assert loaded is not None
            assert result.domain in loaded.domains
            
            domain_state = loaded.domains[result.domain]
            
            # Verify timestamp is stored
            assert domain_state.last_checked == result.timestamp
            
            # Verify status is stored
            assert domain_state.last_status == result.status.value
            
            # Verify check history contains source information
            assert len(domain_state.check_history) >= 1
            latest_entry = domain_state.check_history[-1]
            assert latest_entry.timestamp == result.timestamp
            assert latest_entry.status == result.status.value
            
            # Verify sources are recorded
            expected_sources = [src.source for src in result.sources]
            assert latest_entry.sources == expected_sources

    @given(
        results=st.lists(check_result_strategy(), min_size=2, max_size=5),
        secret=hmac_secret_strategy(),
    )
    @settings(max_examples=100)
    def test_multiple_checks_accumulate_history(
        self, results: list[CheckResult], secret: str
    ) -> None:
        """
        Property 18b: Multiple checks accumulate history.
        
        *For any* sequence of check results for the same domain, all results
        SHALL be recorded in the check_history.
        
        **Feature: domain-availability-checker, Property 18: Check results stored with timestamp and metadata**
        **Validates: Requirements 7.1, 7.4**
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "state.json"
            store = StateStore(file_path, secret)
            
            # Use same domain for all results
            domain = "test.example.com"
            
            # Update with each result
            for result in results:
                # Create result with same domain
                modified_result = CheckResult(
                    domain=domain,
                    status=result.status,
                    confidence=result.confidence,
                    sources=result.sources,
                    timestamp=result.timestamp,
                    metadata=result.metadata,
                )
                store.update_domain_state(domain, modified_result)
            
            # Save and reload
            store.save()
            loaded = store.load()
            
            assert loaded is not None
            assert domain in loaded.domains
            
            domain_state = loaded.domains[domain]
            
            # Verify all results are in history
            assert len(domain_state.check_history) == len(results)
            
            # Verify last status matches last result
            assert domain_state.last_status == results[-1].status.value
            assert domain_state.last_checked == results[-1].timestamp
