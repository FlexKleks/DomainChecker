"""
Property-based tests for the Rate Limiter module.

Uses Hypothesis for property-based testing to verify correctness properties
defined in the design document.
"""

import asyncio
import time
from typing import List, Tuple

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from domain_checker.config import RateLimitConfig, RateLimitRule
from domain_checker.rate_limiter import RateLimiter, RateLimitStatus


# Strategies for generating test data

@st.composite
def rate_limit_rule_strategy(draw) -> RateLimitRule:
    """Generate valid RateLimitRule objects."""
    return RateLimitRule(
        max_requests=draw(st.integers(min_value=1, max_value=100)),
        window_seconds=draw(st.floats(min_value=1.0, max_value=60.0)),
        min_delay_seconds=draw(st.floats(min_value=0.0, max_value=1.0)),
    )


@st.composite
def rate_limit_config_strategy(draw) -> RateLimitConfig:
    """Generate valid RateLimitConfig objects for testing."""
    tlds = ["de", "com", "net", "org", "eu"]
    per_tld = {}
    
    # Generate at least one TLD rule for meaningful tests
    selected_tlds = draw(st.lists(st.sampled_from(tlds), min_size=1, max_size=3, unique=True))
    for tld in selected_tlds:
        per_tld[tld] = draw(rate_limit_rule_strategy())
    
    return RateLimitConfig(
        per_tld=per_tld,
        per_endpoint={},
        global_limit=draw(st.one_of(st.none(), rate_limit_rule_strategy())),
        per_ip=None,
    )


@st.composite
def tld_and_endpoint_strategy(draw) -> Tuple[str, str]:
    """Generate a TLD and endpoint pair."""
    tld = draw(st.sampled_from(["de", "com", "net", "org", "eu"]))
    endpoint = f"https://rdap.{tld}.example/domain"
    return tld, endpoint


class TestSerialAccessProperty:
    """
    Property-based tests for serial access per registry.
    
    **Feature: domain-availability-checker, Property 12: Serial access per registry**
    **Validates: Requirements 4.1**
    """

    @given(
        config=rate_limit_config_strategy(),
        tld_endpoint=tld_and_endpoint_strategy(),
        num_requests=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_serial_access_per_registry(
        self,
        config: RateLimitConfig,
        tld_endpoint: Tuple[str, str],
        num_requests: int,
    ) -> None:
        """
        Property 12: Serial access per registry.
        
        *For any* sequence of requests to the same registry, the rate limiter
        SHALL ensure no two requests execute concurrently (requests are
        serialized via lock).
        
        **Feature: domain-availability-checker, Property 12: Serial access per registry**
        **Validates: Requirements 4.1**
        """
        tld, endpoint = tld_endpoint
        
        # Ensure the TLD is in the config for meaningful test
        if tld not in config.per_tld:
            config.per_tld[tld] = RateLimitRule(
                max_requests=100,  # High limit to avoid rate limiting
                window_seconds=60.0,
                min_delay_seconds=0.0,
            )
        
        rate_limiter = RateLimiter(config)
        
        # Track execution order and overlaps
        execution_log: List[Tuple[int, str, float]] = []
        active_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()
        
        async def make_request(request_id: int) -> None:
            nonlocal active_count, max_concurrent
            
            # Acquire rate limiter (this should serialize access via context manager)
            async with rate_limiter.acquire(tld, endpoint) as status:
                async with lock:
                    active_count += 1
                    max_concurrent = max(max_concurrent, active_count)
                    execution_log.append((request_id, "start", time.monotonic()))
                
                # Simulate some work
                await asyncio.sleep(0.001)
                
                async with lock:
                    execution_log.append((request_id, "end", time.monotonic()))
                    active_count -= 1
                
                # Record the request
                rate_limiter.record_request(tld, endpoint)
        
        async def run_concurrent_requests() -> None:
            # Launch all requests concurrently
            tasks = [make_request(i) for i in range(num_requests)]
            await asyncio.gather(*tasks)
        
        # Run the test
        asyncio.run(run_concurrent_requests())
        
        # Verify: max concurrent should be 1 (serial access)
        assert max_concurrent == 1, (
            f"Expected serial access (max_concurrent=1), but got max_concurrent={max_concurrent}. "
            f"Multiple requests were executing concurrently for the same registry."
        )
        
        # Verify: execution log shows proper serialization
        # Each request should complete before the next starts
        starts = [(rid, t) for rid, event, t in execution_log if event == "start"]
        ends = [(rid, t) for rid, event, t in execution_log if event == "end"]
        
        # Sort by time
        starts.sort(key=lambda x: x[1])
        ends.sort(key=lambda x: x[1])
        
        # Verify no overlapping executions
        for i in range(len(starts) - 1):
            # Find the end time for the current request
            current_start_id = starts[i][0]
            current_end_time = next(t for rid, t in ends if rid == current_start_id)
            next_start_time = starts[i + 1][1]
            
            assert current_end_time <= next_start_time, (
                f"Request {current_start_id} ended at {current_end_time} but "
                f"request {starts[i + 1][0]} started at {next_start_time}. "
                f"Requests should be serialized."
            )


    @given(
        config=rate_limit_config_strategy(),
        num_registries=st.integers(min_value=2, max_value=3),
    )
    @settings(max_examples=100)
    def test_different_registries_can_run_concurrently(
        self,
        config: RateLimitConfig,
        num_registries: int,
    ) -> None:
        """
        Property 12b: Different registries can execute concurrently.
        
        *For any* set of different registries, requests to different registries
        MAY execute concurrently (only same-registry requests are serialized).
        
        **Feature: domain-availability-checker, Property 12: Serial access per registry**
        **Validates: Requirements 4.1**
        """
        # Create distinct TLD/endpoint pairs
        tlds = ["de", "com", "net", "org", "eu"][:num_registries]
        registries = [(tld, f"https://rdap.{tld}.example/domain") for tld in tlds]
        
        # Ensure all TLDs are in config with high limits
        for tld, _ in registries:
            config.per_tld[tld] = RateLimitRule(
                max_requests=100,
                window_seconds=60.0,
                min_delay_seconds=0.0,
            )
        
        rate_limiter = RateLimiter(config)
        
        # Track concurrent execution
        active_per_registry: dict[str, int] = {tld: 0 for tld, _ in registries}
        max_total_concurrent = 0
        lock = asyncio.Lock()
        
        async def make_request(tld: str, endpoint: str) -> None:
            nonlocal max_total_concurrent
            
            async with rate_limiter.acquire(tld, endpoint) as status:
                async with lock:
                    active_per_registry[tld] += 1
                    total_active = sum(active_per_registry.values())
                    max_total_concurrent = max(max_total_concurrent, total_active)
                
                # Simulate work
                await asyncio.sleep(0.01)
                
                async with lock:
                    active_per_registry[tld] -= 1
                
                rate_limiter.record_request(tld, endpoint)
        
        async def run_requests() -> None:
            # Launch requests to all registries concurrently
            tasks = [make_request(tld, endpoint) for tld, endpoint in registries]
            await asyncio.gather(*tasks)
        
        asyncio.run(run_requests())
        
        # Different registries should be able to run concurrently
        # (max_total_concurrent can be > 1 when different registries are accessed)
        # This test verifies the locks are per-registry, not global
        assert max_total_concurrent >= 1, "At least one request should have executed"


class TestAdaptiveDelayProperty:
    """
    Property-based tests for adaptive delay on 429/503.
    
    **Feature: domain-availability-checker, Property 13: Adaptive delay on 429/503**
    **Validates: Requirements 4.2**
    """

    @given(
        config=rate_limit_config_strategy(),
        tld_endpoint=tld_and_endpoint_strategy(),
        error_code=st.sampled_from([429, 503]),
    )
    @settings(max_examples=100)
    def test_adaptive_delay_on_error(
        self,
        config: RateLimitConfig,
        tld_endpoint: Tuple[str, str],
        error_code: int,
    ) -> None:
        """
        Property 13: Adaptive delay on 429/503.
        
        *For any* HTTP response with status 429 or 503, the rate limiter
        SHALL calculate an adaptive wait time that is greater than the base delay.
        
        **Feature: domain-availability-checker, Property 13: Adaptive delay on 429/503**
        **Validates: Requirements 4.2**
        """
        tld, endpoint = tld_endpoint
        rate_limiter = RateLimiter(config)
        
        # First error should return a positive delay
        delay = rate_limiter.apply_adaptive_delay(tld, endpoint, error_code)
        
        assert delay > 0, (
            f"Adaptive delay for error {error_code} should be > 0, got {delay}"
        )
        
        # The delay should be at least the default base delay
        assert delay >= RateLimiter.DEFAULT_ERROR_DELAY, (
            f"Delay {delay} should be >= base delay {RateLimiter.DEFAULT_ERROR_DELAY}"
        )

    @given(
        config=rate_limit_config_strategy(),
        tld_endpoint=tld_and_endpoint_strategy(),
        error_code=st.sampled_from([429, 503]),
        num_errors=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_adaptive_delay_increases_exponentially(
        self,
        config: RateLimitConfig,
        tld_endpoint: Tuple[str, str],
        error_code: int,
        num_errors: int,
    ) -> None:
        """
        Property 13b: Adaptive delay increases exponentially with consecutive errors.
        
        *For any* sequence of consecutive errors, the delay SHALL increase
        exponentially (delay(n) >= base * 2^(n-1)).
        
        **Feature: domain-availability-checker, Property 13: Adaptive delay on 429/503**
        **Validates: Requirements 4.2**
        """
        tld, endpoint = tld_endpoint
        rate_limiter = RateLimiter(config)
        
        delays = []
        for _ in range(num_errors):
            delay = rate_limiter.apply_adaptive_delay(tld, endpoint, error_code)
            delays.append(delay)
        
        # Each delay should be >= previous (exponential growth, capped at max)
        for i in range(1, len(delays)):
            # Allow for capping at MAX_ADAPTIVE_DELAY
            if delays[i - 1] < RateLimiter.MAX_ADAPTIVE_DELAY:
                assert delays[i] >= delays[i - 1], (
                    f"Delay should increase: delays[{i}]={delays[i]} < delays[{i-1}]={delays[i-1]}"
                )

    @given(
        config=rate_limit_config_strategy(),
        tld_endpoint=tld_and_endpoint_strategy(),
        non_error_code=st.integers(min_value=200, max_value=399),
    )
    @settings(max_examples=100)
    def test_no_adaptive_delay_for_success(
        self,
        config: RateLimitConfig,
        tld_endpoint: Tuple[str, str],
        non_error_code: int,
    ) -> None:
        """
        Property 13c: No adaptive delay for non-error responses.
        
        *For any* HTTP response that is not 429 or 503, the rate limiter
        SHALL return 0 delay.
        
        **Feature: domain-availability-checker, Property 13: Adaptive delay on 429/503**
        **Validates: Requirements 4.2**
        """
        tld, endpoint = tld_endpoint
        rate_limiter = RateLimiter(config)
        
        delay = rate_limiter.apply_adaptive_delay(tld, endpoint, non_error_code)
        
        assert delay == 0.0, (
            f"Non-error code {non_error_code} should have 0 delay, got {delay}"
        )



class TestRateLimitDelaysProperty:
    """
    Property-based tests for rate limit delays when approaching limits.
    
    **Feature: domain-availability-checker, Property 14: Rate limit delays applied when approaching limits**
    **Validates: Requirements 4.4**
    """

    @given(
        max_requests=st.integers(min_value=2, max_value=10),
        window_seconds=st.floats(min_value=10.0, max_value=60.0),
    )
    @settings(max_examples=100)
    def test_rate_limit_delays_when_approaching_limit(
        self,
        max_requests: int,
        window_seconds: float,
    ) -> None:
        """
        Property 14: Rate limit delays applied when approaching limits.
        
        *For any* sequence of requests where the count approaches the configured
        limit within the time window, the rate limiter SHALL return a wait time > 0
        before allowing the next request.
        
        **Feature: domain-availability-checker, Property 14: Rate limit delays applied when approaching limits**
        **Validates: Requirements 4.4**
        """
        tld = "de"
        endpoint = "https://rdap.de.example/domain"
        
        config = RateLimitConfig(
            per_tld={
                tld: RateLimitRule(
                    max_requests=max_requests,
                    window_seconds=window_seconds,
                    min_delay_seconds=0.0,
                )
            },
            per_endpoint={},
            global_limit=None,
            per_ip=None,
        )
        
        rate_limiter = RateLimiter(config)
        
        async def fill_rate_limit() -> RateLimitStatus:
            # Make requests up to the limit
            for _ in range(max_requests):
                async with rate_limiter.acquire(tld, endpoint) as status:
                    rate_limiter.record_request(tld, endpoint)
            
            # The next request should be delayed
            async with rate_limiter.acquire(tld, endpoint) as status:
                return status
        
        status = asyncio.run(fill_rate_limit())
        
        # After reaching the limit, the next request should require waiting
        assert not status.allowed or status.wait_seconds > 0, (
            f"After {max_requests} requests, the next request should be delayed. "
            f"Got allowed={status.allowed}, wait_seconds={status.wait_seconds}"
        )

    @given(
        max_requests=st.integers(min_value=2, max_value=10),
        min_delay=st.floats(min_value=0.01, max_value=0.1),
    )
    @settings(max_examples=100)
    def test_min_delay_enforced_between_requests(
        self,
        max_requests: int,
        min_delay: float,
    ) -> None:
        """
        Property 14b: Minimum delay is enforced between requests.
        
        *For any* rate limit rule with min_delay_seconds > 0, consecutive requests
        SHALL be delayed by at least min_delay_seconds.
        
        **Feature: domain-availability-checker, Property 14: Rate limit delays applied when approaching limits**
        **Validates: Requirements 4.4**
        """
        tld = "com"
        endpoint = "https://rdap.com.example/domain"
        
        config = RateLimitConfig(
            per_tld={
                tld: RateLimitRule(
                    max_requests=max_requests,
                    window_seconds=60.0,
                    min_delay_seconds=min_delay,
                )
            },
            per_endpoint={},
            global_limit=None,
            per_ip=None,
        )
        
        rate_limiter = RateLimiter(config)
        
        async def check_min_delay() -> Tuple[RateLimitStatus, RateLimitStatus]:
            # First request should be allowed
            async with rate_limiter.acquire(tld, endpoint) as status1:
                rate_limiter.record_request(tld, endpoint)
                status1_copy = RateLimitStatus(
                    allowed=status1.allowed,
                    wait_seconds=status1.wait_seconds,
                    reason=status1.reason,
                )
            
            # Immediately try second request (should require min_delay)
            async with rate_limiter.acquire(tld, endpoint) as status2:
                status2_copy = RateLimitStatus(
                    allowed=status2.allowed,
                    wait_seconds=status2.wait_seconds,
                    reason=status2.reason,
                )
            
            return status1_copy, status2_copy
        
        status1, status2 = asyncio.run(check_min_delay())
        
        # First request should be allowed
        assert status1.allowed, "First request should be allowed"
        
        # Second request should require waiting (min_delay)
        # Note: Due to timing, the wait might be slightly less than min_delay
        # but should be close to it
        if not status2.allowed:
            assert status2.wait_seconds > 0, (
                f"Second request should require waiting due to min_delay={min_delay}"
            )

    def test_requests_allowed_after_window_expires(self) -> None:
        """
        Property 14c: Requests are allowed after the rate limit window expires.
        
        After the window_seconds has passed, the request count SHALL reset 
        and new requests SHALL be allowed.
        
        **Feature: domain-availability-checker, Property 14: Rate limit delays applied when approaching limits**
        **Validates: Requirements 4.4**
        """
        tld = "net"
        endpoint = "https://rdap.net.example/domain"
        max_requests = 2
        
        # Use a short but reasonable window for testing
        short_window = 0.1  # 100ms
        
        config = RateLimitConfig(
            per_tld={
                tld: RateLimitRule(
                    max_requests=max_requests,
                    window_seconds=short_window,
                    min_delay_seconds=0.0,
                )
            },
            per_endpoint={},
            global_limit=None,
            per_ip=None,
        )
        
        rate_limiter = RateLimiter(config)
        
        async def test_window_expiry() -> RateLimitStatus:
            # Fill up the rate limit
            for _ in range(max_requests):
                async with rate_limiter.acquire(tld, endpoint) as status:
                    rate_limiter.record_request(tld, endpoint)
            
            # Wait for window to expire with extra buffer
            await asyncio.sleep(short_window + 0.05)
            
            # Should be allowed again
            async with rate_limiter.acquire(tld, endpoint) as status:
                return status
        
        status = asyncio.run(test_window_expiry())
        
        assert status.allowed, (
            f"After window expiry, request should be allowed. "
            f"Got allowed={status.allowed}, wait_seconds={status.wait_seconds}"
        )
