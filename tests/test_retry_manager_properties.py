"""
Property-based tests for the Retry Manager module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import asyncio
from typing import Optional

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.config import RetryConfig
from domain_checker.enums import RDAPErrorCode, RDAPStatus
from domain_checker.rdap_client import RDAPResponse, RDAPError, RDAPParsedFields
from domain_checker.retry_manager import RetryManager, RetryResult


# Strategies for generating test data

@st.composite
def retry_config_strategy(draw) -> RetryConfig:
    """Generate valid RetryConfig objects."""
    return RetryConfig(
        max_retries=draw(st.integers(min_value=1, max_value=5)),
        base_delay_seconds=draw(st.floats(min_value=0.001, max_value=0.01)),
        max_delay_seconds=draw(st.floats(min_value=0.01, max_value=0.1)),
        retryable_errors=["timeout", "server_error", "rate_limited", "network_error"],
    )


@st.composite
def transient_error_response_strategy(draw) -> RDAPResponse:
    """Generate RDAP responses with transient errors (should retry)."""
    error_code = draw(st.sampled_from([
        RDAPErrorCode.TIMEOUT,
        RDAPErrorCode.SERVER_ERROR,
        RDAPErrorCode.RATE_LIMITED,
        RDAPErrorCode.NETWORK_ERROR,
    ]))
    http_status = draw(st.sampled_from([0, 429, 500, 502, 503, 504]))
    
    return RDAPResponse(
        status=RDAPStatus.ERROR,
        http_status_code=http_status,
        raw_response=None,
        parsed_fields=None,
        error=RDAPError(
            code=error_code,
            message=f"Transient error: {error_code.value}",
            http_status_code=http_status if http_status > 0 else None,
        ),
        response_time_ms=100.0,
    )


@st.composite
def definitive_taken_response_strategy(draw) -> RDAPResponse:
    """Generate RDAP responses indicating domain is definitively taken."""
    domain_name = draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-"),
        min_size=3,
        max_size=20,
    )) + ".com"
    
    return RDAPResponse(
        status=RDAPStatus.FOUND,
        http_status_code=200,
        raw_response={"ldhName": domain_name, "status": ["active"]},
        parsed_fields=RDAPParsedFields(
            domain_name=domain_name,
            status=["active"],
            events=[],
            nameservers=[],
        ),
        error=None,
        response_time_ms=50.0,
    )


@st.composite
def not_found_response_strategy(draw) -> RDAPResponse:
    """Generate RDAP responses indicating domain not found."""
    return RDAPResponse(
        status=RDAPStatus.NOT_FOUND,
        http_status_code=404,
        raw_response=None,
        parsed_fields=None,
        error=None,
        response_time_ms=50.0,
    )


class TestExponentialBackoffProperty:
    """
    Property-based tests for exponential backoff on transient errors.
    
    **Feature: domain-availability-checker, Property 15: Exponential backoff on transient errors**
    **Validates: Requirements 5.1**
    """

    @given(
        config=retry_config_strategy(),
        num_attempts=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_exponential_backoff_delay_calculation(
        self,
        config: RetryConfig,
        num_attempts: int,
    ) -> None:
        """
        Property 15: Exponential backoff on transient errors.
        
        *For any* sequence of transient errors (timeout, 503, 429), the retry
        manager SHALL apply delays that increase exponentially:
        delay(n) >= base_delay * 2^n, capped at max_delay.
        
        **Feature: domain-availability-checker, Property 15: Exponential backoff on transient errors**
        **Validates: Requirements 5.1**
        """
        retry_manager = RetryManager(config)
        
        delays = []
        for attempt in range(num_attempts):
            delay = retry_manager._calculate_delay(attempt)
            delays.append(delay)
            
            # Verify exponential formula: delay >= base * 2^attempt
            expected_min = config.base_delay_seconds * (2 ** attempt)
            expected_delay = min(expected_min, config.max_delay_seconds)
            
            assert abs(delay - expected_delay) < 0.0001, (
                f"Delay for attempt {attempt} should be {expected_delay}, got {delay}"
            )
        
        # Verify delays are non-decreasing (exponential growth, capped)
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1], (
                f"Delays should be non-decreasing: delays[{i}]={delays[i]} < delays[{i-1}]={delays[i-1]}"
            )

    @given(
        config=retry_config_strategy(),
    )
    @settings(max_examples=100)
    def test_delay_capped_at_max(
        self,
        config: RetryConfig,
    ) -> None:
        """
        Property 15b: Delay is capped at max_delay_seconds.
        
        *For any* retry configuration, the calculated delay SHALL never
        exceed max_delay_seconds.
        
        **Feature: domain-availability-checker, Property 15: Exponential backoff on transient errors**
        **Validates: Requirements 5.1**
        """
        retry_manager = RetryManager(config)
        
        # Test with a high attempt number that would exceed max_delay
        for attempt in range(10):
            delay = retry_manager._calculate_delay(attempt)
            assert delay <= config.max_delay_seconds, (
                f"Delay {delay} exceeds max_delay {config.max_delay_seconds} at attempt {attempt}"
            )

    @given(
        config=retry_config_strategy(),
        error_response=transient_error_response_strategy(),
    )
    @settings(max_examples=100)
    def test_transient_errors_trigger_retry(
        self,
        config: RetryConfig,
        error_response: RDAPResponse,
    ) -> None:
        """
        Property 15c: Transient errors trigger retry.
        
        *For any* RDAP response with a transient error code (timeout, 503, 429),
        the retry manager SHALL indicate that a retry should occur.
        
        **Feature: domain-availability-checker, Property 15: Exponential backoff on transient errors**
        **Validates: Requirements 5.1**
        """
        retry_manager = RetryManager(config)
        
        should_retry = retry_manager.should_retry(error_response)
        
        assert should_retry, (
            f"Transient error {error_response.error.code} should trigger retry"
        )


class TestMaxRetriesExhaustedProperty:
    """
    Property-based tests for max retries exhausted behavior.
    
    **Feature: domain-availability-checker, Property 16: Max retries exhausted results in taken**
    **Validates: Requirements 5.2**
    """

    @given(
        config=retry_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_max_retries_exhausted_returns_failure(
        self,
        config: RetryConfig,
    ) -> None:
        """
        Property 16: Max retries exhausted results in taken.
        
        *For any* operation that fails with transient errors for max_retries + 1
        attempts, the retry manager SHALL return failure.
        
        **Feature: domain-availability-checker, Property 16: Max retries exhausted results in taken**
        **Validates: Requirements 5.2**
        """
        retry_manager = RetryManager(config)
        
        # Track number of calls
        call_count = 0
        
        async def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Simulated timeout")
        
        async def run_test() -> RetryResult:
            return await retry_manager.execute_with_retry(
                always_failing_operation,
                is_retryable=lambda e: isinstance(e, TimeoutError),
            )
        
        result = asyncio.run(run_test())
        
        # Should have attempted max_retries + 1 times
        expected_attempts = config.max_retries + 1
        assert result.attempts == expected_attempts, (
            f"Expected {expected_attempts} attempts, got {result.attempts}"
        )
        
        # Should return failure
        assert not result.success, "Should return failure after exhausting retries"
        assert result.result is None, "Result should be None on failure"
        assert result.last_error is not None, "Should have last_error set"

    @given(
        config=retry_config_strategy(),
    )
    @settings(max_examples=100, deadline=None)
    def test_rdap_max_retries_exhausted(
        self,
        config: RetryConfig,
    ) -> None:
        """
        Property 16b: RDAP-specific max retries exhausted.
        
        *For any* RDAP operation that returns transient errors for all attempts,
        the retry manager SHALL return the last error response.
        
        **Feature: domain-availability-checker, Property 16: Max retries exhausted results in taken**
        **Validates: Requirements 5.2**
        """
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        async def always_error_rdap():
            nonlocal call_count
            call_count += 1
            return RDAPResponse(
                status=RDAPStatus.ERROR,
                http_status_code=503,
                raw_response=None,
                parsed_fields=None,
                error=RDAPError(
                    code=RDAPErrorCode.SERVER_ERROR,
                    message="Server error",
                    http_status_code=503,
                ),
                response_time_ms=100.0,
            )
        
        async def run_test():
            return await retry_manager.execute_rdap_with_retry(always_error_rdap)
        
        response, attempts = asyncio.run(run_test())
        
        # Should have attempted max_retries + 1 times
        expected_attempts = config.max_retries + 1
        assert attempts == expected_attempts, (
            f"Expected {expected_attempts} attempts, got {attempts}"
        )
        
        # Should return error status
        assert response.status == RDAPStatus.ERROR, (
            f"Expected ERROR status, got {response.status}"
        )


class TestNoRetryOnTakenProperty:
    """
    Property-based tests for no retry on definitive taken signal.
    
    **Feature: domain-availability-checker, Property 17: No retry on definitive taken signal**
    **Validates: Requirements 5.3**
    """

    @given(
        config=retry_config_strategy(),
        taken_response=definitive_taken_response_strategy(),
    )
    @settings(max_examples=100)
    def test_no_retry_on_definitive_taken(
        self,
        config: RetryConfig,
        taken_response: RDAPResponse,
    ) -> None:
        """
        Property 17: No retry on definitive taken signal.
        
        *For any* RDAP response indicating the domain is registered (status FOUND),
        the retry manager SHALL not retry, regardless of retry configuration.
        
        **Feature: domain-availability-checker, Property 17: No retry on definitive taken signal**
        **Validates: Requirements 5.3**
        """
        retry_manager = RetryManager(config)
        
        # Verify is_definitive_taken returns True
        assert retry_manager.is_definitive_taken(taken_response), (
            f"Response with status {taken_response.status} should be definitive taken"
        )
        
        # Verify should_retry returns False
        should_retry = retry_manager.should_retry(taken_response)
        assert not should_retry, (
            f"Should not retry on definitive taken response"
        )

    @given(
        config=retry_config_strategy(),
        taken_response=definitive_taken_response_strategy(),
    )
    @settings(max_examples=100)
    def test_rdap_no_retry_on_found(
        self,
        config: RetryConfig,
        taken_response: RDAPResponse,
    ) -> None:
        """
        Property 17b: RDAP operation stops immediately on FOUND.
        
        *For any* RDAP operation that returns FOUND status, the retry manager
        SHALL return immediately without any retries.
        
        **Feature: domain-availability-checker, Property 17: No retry on definitive taken signal**
        **Validates: Requirements 5.3**
        """
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        async def returns_found():
            nonlocal call_count
            call_count += 1
            return taken_response
        
        async def run_test():
            return await retry_manager.execute_rdap_with_retry(returns_found)
        
        response, attempts = asyncio.run(run_test())
        
        # Should only call once (no retries)
        assert call_count == 1, (
            f"Expected 1 call (no retries), got {call_count} calls"
        )
        assert attempts == 1, (
            f"Expected 1 attempt, got {attempts}"
        )
        
        # Should return FOUND status
        assert response.status == RDAPStatus.FOUND, (
            f"Expected FOUND status, got {response.status}"
        )

    @given(
        config=retry_config_strategy(),
        not_found_response=not_found_response_strategy(),
    )
    @settings(max_examples=100)
    def test_no_retry_on_not_found(
        self,
        config: RetryConfig,
        not_found_response: RDAPResponse,
    ) -> None:
        """
        Property 17c: No retry on NOT_FOUND (successful availability check).
        
        *For any* RDAP response with NOT_FOUND status, the retry manager
        SHALL not retry (this is a successful result indicating availability).
        
        **Feature: domain-availability-checker, Property 17: No retry on definitive taken signal**
        **Validates: Requirements 5.3**
        """
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        async def returns_not_found():
            nonlocal call_count
            call_count += 1
            return not_found_response
        
        async def run_test():
            return await retry_manager.execute_rdap_with_retry(returns_not_found)
        
        response, attempts = asyncio.run(run_test())
        
        # Should only call once (no retries needed for successful result)
        assert call_count == 1, (
            f"Expected 1 call (no retries), got {call_count} calls"
        )
        
        # Should return NOT_FOUND status
        assert response.status == RDAPStatus.NOT_FOUND, (
            f"Expected NOT_FOUND status, got {response.status}"
        )

    @given(
        config=retry_config_strategy(),
        num_errors_before_success=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_retry_succeeds_after_transient_errors(
        self,
        config: RetryConfig,
        num_errors_before_success: int,
    ) -> None:
        """
        Property 17d: Retry succeeds after transient errors.
        
        *For any* operation that fails with transient errors but eventually
        succeeds, the retry manager SHALL return the successful result.
        
        **Feature: domain-availability-checker, Property 17: No retry on definitive taken signal**
        **Validates: Requirements 5.3**
        """
        # Ensure we have enough retries to succeed
        assume(num_errors_before_success <= config.max_retries)
        
        retry_manager = RetryManager(config)
        
        call_count = 0
        
        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count <= num_errors_before_success:
                return RDAPResponse(
                    status=RDAPStatus.ERROR,
                    http_status_code=503,
                    raw_response=None,
                    parsed_fields=None,
                    error=RDAPError(
                        code=RDAPErrorCode.SERVER_ERROR,
                        message="Temporary error",
                        http_status_code=503,
                    ),
                    response_time_ms=100.0,
                )
            else:
                return RDAPResponse(
                    status=RDAPStatus.NOT_FOUND,
                    http_status_code=404,
                    raw_response=None,
                    parsed_fields=None,
                    error=None,
                    response_time_ms=50.0,
                )
        
        async def run_test():
            return await retry_manager.execute_rdap_with_retry(eventually_succeeds)
        
        response, attempts = asyncio.run(run_test())
        
        # Should have made num_errors_before_success + 1 calls
        expected_calls = num_errors_before_success + 1
        assert call_count == expected_calls, (
            f"Expected {expected_calls} calls, got {call_count}"
        )
        
        # Should return successful NOT_FOUND status
        assert response.status == RDAPStatus.NOT_FOUND, (
            f"Expected NOT_FOUND status after retries, got {response.status}"
        )
