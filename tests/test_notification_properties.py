"""
Property-based tests for Notification Router module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Optional

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.audit_logger import AuditLogger
from domain_checker.config import RetryConfig
from domain_checker.enums import AvailabilityStatus, LogLevel
from domain_checker.models import DomainState
from domain_checker.notifications import (
    NotificationChannel,
    NotificationPayload,
    NotificationResult,
    NotificationRouter,
)


# Test doubles for notification channels


@dataclass
class MockChannelConfig:
    """Configuration for mock channel behavior."""

    name: str
    should_succeed: bool = True
    fail_count: int = 0  # Number of times to fail before succeeding
    delay_seconds: float = 0.0


class MockNotificationChannel:
    """Mock notification channel for testing."""

    def __init__(self, config: MockChannelConfig) -> None:
        self._config = config
        self._call_count = 0
        self._payloads: list[NotificationPayload] = []

    async def send(self, payload: NotificationPayload) -> bool:
        """Record the call and return configured result."""
        self._call_count += 1
        self._payloads.append(payload)

        if self._config.delay_seconds > 0:
            await asyncio.sleep(self._config.delay_seconds)

        # Fail for the first N attempts if configured
        if self._config.fail_count > 0 and self._call_count <= self._config.fail_count:
            return False

        return self._config.should_succeed

    def get_name(self) -> str:
        return self._config.name

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def payloads(self) -> list[NotificationPayload]:
        return self._payloads.copy()


class FailingNotificationChannel:
    """Channel that always fails with an exception."""

    def __init__(self, name: str = "failing") -> None:
        self._name = name
        self._call_count = 0

    async def send(self, payload: NotificationPayload) -> bool:
        self._call_count += 1
        raise Exception("Simulated channel failure")

    def get_name(self) -> str:
        return self._name

    @property
    def call_count(self) -> int:
        return self._call_count


# Strategies for generating test data


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
def domain_strategy(draw) -> str:
    """Generate valid domain names."""
    sld = draw(
        st.text(
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789"),
            min_size=1,
            max_size=20,
        )
    )
    tld = draw(st.sampled_from(["de", "com", "net", "org", "eu"]))
    return f"{sld}.{tld}"


@st.composite
def notification_payload_strategy(draw) -> NotificationPayload:
    """Generate valid NotificationPayload objects."""
    return NotificationPayload(
        domain=draw(domain_strategy()),
        status=draw(st.sampled_from([s.value for s in AvailabilityStatus])),
        timestamp=draw(timestamp_strategy()),
        language=draw(st.sampled_from(["de", "en"])),
    )


@st.composite
def domain_state_strategy(draw, status: Optional[str] = None) -> DomainState:
    """Generate valid DomainState objects."""
    return DomainState(
        canonical_domain=draw(domain_strategy()),
        last_status=status or draw(st.sampled_from(["available", "taken", "unknown"])),
        last_checked=draw(timestamp_strategy()),
        last_notified=draw(st.one_of(st.none(), timestamp_strategy())),
        check_history=[],
    )


@st.composite
def retry_config_strategy(draw) -> RetryConfig:
    """Generate valid RetryConfig objects."""
    max_retries = draw(st.integers(min_value=0, max_value=5))
    base_delay = draw(st.floats(min_value=0.001, max_value=0.01))
    max_delay = draw(st.floats(min_value=base_delay, max_value=0.1))
    return RetryConfig(
        max_retries=max_retries,
        base_delay_seconds=base_delay,
        max_delay_seconds=max_delay,
    )


def run_async(coro):
    """Helper to run async code in tests."""
    return asyncio.new_event_loop().run_until_complete(coro)


class TestNotificationSuppressionProperty:
    """
    Property-based tests for notification suppression.

    **Feature: domain-availability-checker, Property 23: Unchanged status suppresses notification**
    **Validates: Requirements 7.3, 9.2**
    """

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
    )
    @settings(max_examples=100)
    def test_unchanged_available_status_suppresses_notification(
        self, domain: str, timestamp: str, language: str
    ) -> None:
        """
        Property 23: Unchanged status suppresses notification.

        *For any* domain where the previous status equals the current status (AVAILABLE),
        the notification router SHALL not send a notification.

        **Feature: domain-availability-checker, Property 23: Unchanged status suppresses notification**
        **Validates: Requirements 7.3, 9.2**
        """
        retry_config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        # Register a mock channel
        mock_channel = MockNotificationChannel(MockChannelConfig(name="test"))
        router.register_channel(mock_channel)

        # Create payload with AVAILABLE status
        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        # Create previous state with AVAILABLE status
        previous_state = DomainState(
            canonical_domain=domain,
            last_status=AvailabilityStatus.AVAILABLE.value,
            last_checked=timestamp,
            last_notified=None,
            check_history=[],
        )

        # Send notification - should be suppressed
        results = run_async(
            router.notify(payload, AvailabilityStatus.AVAILABLE, previous_state)
        )

        # No notifications should be sent
        assert len(results) == 0
        assert mock_channel.call_count == 0

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        non_available_status=st.sampled_from(
            [AvailabilityStatus.TAKEN, AvailabilityStatus.UNKNOWN]
        ),
    )
    @settings(max_examples=100)
    def test_non_available_status_suppresses_notification(
        self,
        domain: str,
        timestamp: str,
        language: str,
        non_available_status: AvailabilityStatus,
    ) -> None:
        """
        Property 23b: Non-available status suppresses notification.

        *For any* domain with status other than AVAILABLE, the notification router
        SHALL not send a notification (we only notify on availability).

        **Feature: domain-availability-checker, Property 23: Unchanged status suppresses notification**
        **Validates: Requirements 7.3, 9.2**
        """
        retry_config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        mock_channel = MockNotificationChannel(MockChannelConfig(name="test"))
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=non_available_status.value,
            timestamp=timestamp,
            language=language,
        )

        # No previous state
        results = run_async(router.notify(payload, non_available_status, None))

        # No notifications should be sent for non-available status
        assert len(results) == 0
        assert mock_channel.call_count == 0


class TestFirstAvailabilityNotificationProperty:
    """
    Property-based tests for first availability notification.

    **Feature: domain-availability-checker, Property 24: First availability triggers notification**
    **Validates: Requirements 9.1**
    """

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
    )
    @settings(max_examples=100)
    def test_first_availability_triggers_notification_no_previous_state(
        self, domain: str, timestamp: str, language: str
    ) -> None:
        """
        Property 24: First availability triggers notification (no previous state).

        *For any* domain where the current status is AVAILABLE and no previous state exists,
        the notification router SHALL send a notification.

        **Feature: domain-availability-checker, Property 24: First availability triggers notification**
        **Validates: Requirements 9.1**
        """
        retry_config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        mock_channel = MockNotificationChannel(MockChannelConfig(name="test"))
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        # No previous state - first check
        results = run_async(router.notify(payload, AvailabilityStatus.AVAILABLE, None))

        # Notification should be sent
        assert len(results) == 1
        assert results[0].success is True
        assert mock_channel.call_count == 1
        assert mock_channel.payloads[0].domain == domain

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        previous_status=st.sampled_from(
            [AvailabilityStatus.TAKEN, AvailabilityStatus.UNKNOWN]
        ),
    )
    @settings(max_examples=100)
    def test_first_availability_triggers_notification_was_taken(
        self,
        domain: str,
        timestamp: str,
        language: str,
        previous_status: AvailabilityStatus,
    ) -> None:
        """
        Property 24b: First availability triggers notification (was taken/unknown).

        *For any* domain where the current status is AVAILABLE and the previous status
        was TAKEN or UNKNOWN, the notification router SHALL send a notification.

        **Feature: domain-availability-checker, Property 24: First availability triggers notification**
        **Validates: Requirements 9.1**
        """
        retry_config = RetryConfig(
            max_retries=0,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        mock_channel = MockNotificationChannel(MockChannelConfig(name="test"))
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        # Previous state was TAKEN or UNKNOWN
        previous_state = DomainState(
            canonical_domain=domain,
            last_status=previous_status.value,
            last_checked=timestamp,
            last_notified=None,
            check_history=[],
        )

        results = run_async(
            router.notify(payload, AvailabilityStatus.AVAILABLE, previous_state)
        )

        # Notification should be sent
        assert len(results) == 1
        assert results[0].success is True
        assert mock_channel.call_count == 1



class TestNotificationRetryProperty:
    """
    Property-based tests for notification retry with exponential backoff.

    **Feature: domain-availability-checker, Property 25: Failed notification retries with exponential backoff**
    **Validates: Requirements 9.4**
    """

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        max_retries=st.integers(min_value=1, max_value=4),
    )
    @settings(max_examples=100)
    def test_failed_notification_retries_with_exponential_backoff(
        self, domain: str, timestamp: str, language: str, max_retries: int
    ) -> None:
        """
        Property 25: Failed notification retries with exponential backoff.

        *For any* notification delivery that fails, the router SHALL retry with delays
        following exponential backoff pattern, up to the configured max retries.

        **Feature: domain-availability-checker, Property 25: Failed notification retries with exponential backoff**
        **Validates: Requirements 9.4**
        """
        retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=0.001,  # Very small for fast tests
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        # Channel that fails a specific number of times then succeeds
        fail_count = max_retries  # Fail exactly max_retries times
        mock_channel = MockNotificationChannel(
            MockChannelConfig(name="test", fail_count=fail_count)
        )
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        # Use notify_without_suppression to bypass suppression logic
        results = run_async(router.notify_without_suppression(payload))

        # Should have retried and eventually succeeded
        assert len(results) == 1
        result = results[0]

        # Total attempts = fail_count + 1 (the successful one)
        expected_attempts = fail_count + 1
        assert result.attempts == expected_attempts
        assert result.success is True
        assert mock_channel.call_count == expected_attempts

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        max_retries=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_all_retries_exhausted_returns_failure(
        self, domain: str, timestamp: str, language: str, max_retries: int
    ) -> None:
        """
        Property 25b: All retries exhausted returns failure.

        *For any* notification where all retry attempts fail, the result SHALL
        indicate failure with the total number of attempts.

        **Feature: domain-availability-checker, Property 25: Failed notification retries with exponential backoff**
        **Validates: Requirements 9.4**
        """
        retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        # Channel that always fails
        mock_channel = MockNotificationChannel(
            MockChannelConfig(name="test", should_succeed=False)
        )
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        results = run_async(router.notify_without_suppression(payload))

        assert len(results) == 1
        result = results[0]

        # Total attempts = 1 initial + max_retries
        expected_attempts = max_retries + 1
        assert result.attempts == expected_attempts
        assert result.success is False
        assert mock_channel.call_count == expected_attempts

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        max_retries=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_exception_triggers_retry(
        self, domain: str, timestamp: str, language: str, max_retries: int
    ) -> None:
        """
        Property 25c: Exception triggers retry.

        *For any* notification where the channel raises an exception, the router
        SHALL retry following the same exponential backoff pattern.

        **Feature: domain-availability-checker, Property 25: Failed notification retries with exponential backoff**
        **Validates: Requirements 9.4**
        """
        retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config)

        # Channel that always raises exception
        failing_channel = FailingNotificationChannel(name="failing")
        router.register_channel(failing_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        results = run_async(router.notify_without_suppression(payload))

        assert len(results) == 1
        result = results[0]

        # Total attempts = 1 initial + max_retries
        expected_attempts = max_retries + 1
        assert result.attempts == expected_attempts
        assert result.success is False
        assert failing_channel.call_count == expected_attempts
        assert result.error is not None


class TestFailedNotificationLoggingProperty:
    """
    Property-based tests for failed notification logging.

    **Feature: domain-availability-checker, Property 26: All retries failed logs error with full details**
    **Validates: Requirements 9.5**
    """

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        max_retries=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_all_retries_failed_logs_error_with_full_details(
        self, domain: str, timestamp: str, language: str, max_retries: int
    ) -> None:
        """
        Property 26: All retries failed logs error with full details.

        *For any* notification where all retry attempts fail, the logger SHALL record
        an error entry containing: channel name, all attempt errors, and the original payload.

        **Feature: domain-availability-checker, Property 26: All retries failed logs error with full details**
        **Validates: Requirements 9.5**
        """
        # Create logger with string output for inspection
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)

        retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config, logger=logger)

        # Channel that always fails
        mock_channel = MockNotificationChannel(
            MockChannelConfig(name="test_channel", should_succeed=False)
        )
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        run_async(router.notify_without_suppression(payload))

        # Check that error was logged
        assert len(logger.entries) == 1
        entry = logger.entries[0]

        # Verify log level is ERROR
        assert entry.level == LogLevel.ERROR

        # Verify component is NotificationRouter
        assert entry.component == "NotificationRouter"

        # Verify data contains required fields
        assert "channel" in entry.data
        assert entry.data["channel"] == "test_channel"

        assert "domain" in entry.data
        assert entry.data["domain"] == domain

        assert "status" in entry.data
        assert entry.data["status"] == AvailabilityStatus.AVAILABLE.value

        assert "timestamp" in entry.data
        assert entry.data["timestamp"] == timestamp

        assert "language" in entry.data
        assert entry.data["language"] == language

        # Verify attempts are logged
        assert "total_attempts" in entry.data
        assert entry.data["total_attempts"] == max_retries + 1

        assert "attempts" in entry.data
        assert len(entry.data["attempts"]) == max_retries + 1

        # Verify each attempt has error information
        for attempt_data in entry.data["attempts"]:
            assert "attempt" in attempt_data
            assert "error" in attempt_data
            assert "timestamp" in attempt_data

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
        max_retries=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100)
    def test_exception_errors_logged_with_details(
        self, domain: str, timestamp: str, language: str, max_retries: int
    ) -> None:
        """
        Property 26b: Exception errors logged with details.

        *For any* notification where the channel raises exceptions, the error log
        SHALL contain the exception messages.

        **Feature: domain-availability-checker, Property 26: All retries failed logs error with full details**
        **Validates: Requirements 9.5**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)

        retry_config = RetryConfig(
            max_retries=max_retries,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config, logger=logger)

        # Channel that raises exceptions
        failing_channel = FailingNotificationChannel(name="failing_channel")
        router.register_channel(failing_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        run_async(router.notify_without_suppression(payload))

        # Check that error was logged
        assert len(logger.entries) == 1
        entry = logger.entries[0]

        # Verify error messages contain exception text
        for attempt_data in entry.data["attempts"]:
            assert "Simulated channel failure" in attempt_data["error"]

    @given(
        domain=domain_strategy(),
        timestamp=timestamp_strategy(),
        language=st.sampled_from(["de", "en"]),
    )
    @settings(max_examples=100)
    def test_successful_notification_does_not_log_error(
        self, domain: str, timestamp: str, language: str
    ) -> None:
        """
        Property 26c: Successful notification does not log error.

        *For any* notification that succeeds, no error SHALL be logged.

        **Feature: domain-availability-checker, Property 26: All retries failed logs error with full details**
        **Validates: Requirements 9.5**
        """
        output = StringIO()
        logger = AuditLogger(output_format="json", output_stream=output)

        retry_config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.001,
            max_delay_seconds=0.01,
        )
        router = NotificationRouter(retry_config, logger=logger)

        # Channel that succeeds
        mock_channel = MockNotificationChannel(
            MockChannelConfig(name="test", should_succeed=True)
        )
        router.register_channel(mock_channel)

        payload = NotificationPayload(
            domain=domain,
            status=AvailabilityStatus.AVAILABLE.value,
            timestamp=timestamp,
            language=language,
        )

        results = run_async(router.notify_without_suppression(payload))

        # Notification should succeed
        assert len(results) == 1
        assert results[0].success is True

        # No error should be logged
        assert len(logger.entries) == 0
