"""
Rate Limiter module for the domain checker system.

This module provides rate limiting functionality with:
- Serial access control per registry (no parallel requests to same registry)
- Request tracking within configurable time windows
- Adaptive delay calculation for 429/503 responses
- Support for per-TLD, per-endpoint, global, and per-IP limits
"""

import asyncio
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from domain_checker.config import RateLimitConfig, RateLimitRule


@dataclass
class RateLimitStatus:
    """Result of a rate limit check."""

    allowed: bool
    wait_seconds: float
    reason: Optional[str] = None


class RateLimiter:
    """
    Rate limiter with serial access control per registry.
    
    Ensures:
    - No parallel requests to the same registry (via asyncio.Lock)
    - Request counts stay within configured limits
    - Adaptive delays on 429/503 responses
    """

    # Base multiplier for adaptive delay calculation
    ADAPTIVE_DELAY_BASE = 2.0
    # Maximum adaptive delay in seconds
    MAX_ADAPTIVE_DELAY = 300.0
    # Default delay for 429/503 when no specific rule exists
    DEFAULT_ERROR_DELAY = 5.0

    def __init__(self, config: RateLimitConfig) -> None:
        """
        Initialize the rate limiter.
        
        Args:
            config: Rate limit configuration with per-TLD, per-endpoint,
                   global, and per-IP limits.
        """
        self._config = config
        # Track request timestamps per key (tld, endpoint, global, ip)
        self._request_times: dict[str, list[float]] = defaultdict(list)
        # Locks for serial access per registry
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Track consecutive errors for adaptive delay
        self._consecutive_errors: dict[str, int] = defaultdict(int)


    @asynccontextmanager
    async def acquire(self, tld: str, endpoint: str) -> AsyncIterator[RateLimitStatus]:
        """
        Acquire permission to make a request, enforcing serial access.
        
        This is an async context manager that:
        1. Acquires a lock for the registry (ensuring serial access)
        2. Checks all applicable rate limits
        3. Yields the status (holds lock during the request)
        4. Releases the lock when the context exits
        
        Usage:
            async with rate_limiter.acquire(tld, endpoint) as status:
                if status.allowed:
                    # Make the request while holding the lock
                    response = await make_request()
                    rate_limiter.record_request(tld, endpoint)
        
        Args:
            tld: The TLD being queried (e.g., "de", "com")
            endpoint: The endpoint URL being accessed
            
        Yields:
            RateLimitStatus indicating if request is allowed and any wait time
        """
        # Create a registry key for the lock (combines tld and endpoint)
        registry_key = f"{tld}:{endpoint}"
        
        # Acquire the lock for this registry (ensures serial access)
        async with self._locks[registry_key]:
            # Calculate required wait time based on all applicable limits
            wait_seconds, reason = self._calculate_wait_time(tld, endpoint)
            
            if wait_seconds > 0:
                yield RateLimitStatus(
                    allowed=False,
                    wait_seconds=wait_seconds,
                    reason=reason,
                )
            else:
                yield RateLimitStatus(
                    allowed=True,
                    wait_seconds=0.0,
                    reason=None,
                )

    def _calculate_wait_time(self, tld: str, endpoint: str) -> tuple[float, Optional[str]]:
        """
        Calculate the required wait time based on all applicable rate limits.
        
        Checks limits in order of specificity:
        1. Per-TLD limits
        2. Per-endpoint limits
        3. Global limits
        4. Per-IP limits (using 'ip' as key)
        
        Returns:
            Tuple of (wait_seconds, reason) where reason explains the limit
        """
        current_time = time.monotonic()
        max_wait = 0.0
        wait_reason = None

        # Check per-TLD limit
        if tld in self._config.per_tld:
            rule = self._config.per_tld[tld]
            wait, reason = self._check_rule(f"tld:{tld}", rule, current_time)
            if wait > max_wait:
                max_wait = wait
                wait_reason = reason

        # Check per-endpoint limit
        if endpoint in self._config.per_endpoint:
            rule = self._config.per_endpoint[endpoint]
            wait, reason = self._check_rule(f"endpoint:{endpoint}", rule, current_time)
            if wait > max_wait:
                max_wait = wait
                wait_reason = reason

        # Check global limit
        if self._config.global_limit:
            wait, reason = self._check_rule("global", self._config.global_limit, current_time)
            if wait > max_wait:
                max_wait = wait
                wait_reason = reason

        # Check per-IP limit (using 'ip' as a generic key)
        if self._config.per_ip:
            wait, reason = self._check_rule("ip", self._config.per_ip, current_time)
            if wait > max_wait:
                max_wait = wait
                wait_reason = reason

        return max_wait, wait_reason

    def _check_rule(
        self, key: str, rule: RateLimitRule, current_time: float
    ) -> tuple[float, Optional[str]]:
        """
        Check a single rate limit rule and calculate wait time if needed.
        
        Args:
            key: The tracking key for this rule
            rule: The rate limit rule to check
            current_time: Current monotonic time
            
        Returns:
            Tuple of (wait_seconds, reason)
        """
        # Clean up old request times outside the window
        window_start = current_time - rule.window_seconds
        self._request_times[key] = [
            t for t in self._request_times[key] if t > window_start
        ]

        request_count = len(self._request_times[key])

        # Check if we're at or approaching the limit
        if request_count >= rule.max_requests:
            # Calculate when the oldest request will expire from the window
            if self._request_times[key]:
                oldest_request = min(self._request_times[key])
                wait_until = oldest_request + rule.window_seconds
                wait_seconds = max(0.0, wait_until - current_time)
                return wait_seconds, f"Rate limit reached for {key}: {request_count}/{rule.max_requests}"
            return rule.min_delay_seconds, f"Rate limit reached for {key}"

        # Apply minimum delay if configured
        if rule.min_delay_seconds > 0 and self._request_times[key]:
            last_request = max(self._request_times[key])
            time_since_last = current_time - last_request
            if time_since_last < rule.min_delay_seconds:
                wait_seconds = rule.min_delay_seconds - time_since_last
                return wait_seconds, f"Minimum delay for {key}"

        return 0.0, None

    def record_request(self, tld: str, endpoint: str) -> None:
        """
        Record that a request was made.
        
        Should be called after a successful request to track usage.
        
        Args:
            tld: The TLD that was queried
            endpoint: The endpoint that was accessed
        """
        current_time = time.monotonic()

        # Record for all applicable tracking keys
        if tld in self._config.per_tld:
            self._request_times[f"tld:{tld}"].append(current_time)

        if endpoint in self._config.per_endpoint:
            self._request_times[f"endpoint:{endpoint}"].append(current_time)

        if self._config.global_limit:
            self._request_times["global"].append(current_time)

        if self._config.per_ip:
            self._request_times["ip"].append(current_time)

        # Reset consecutive errors on successful request
        registry_key = f"{tld}:{endpoint}"
        self._consecutive_errors[registry_key] = 0

    def apply_adaptive_delay(self, tld: str, endpoint: str, error_code: int) -> float:
        """
        Calculate adaptive wait time for error responses (429, 503).
        
        Uses exponential backoff based on consecutive errors:
        delay = base_delay * (2 ^ consecutive_errors)
        
        Args:
            tld: The TLD that was queried
            endpoint: The endpoint that returned the error
            error_code: HTTP status code (429 or 503)
            
        Returns:
            Recommended wait time in seconds before retrying
        """
        if error_code not in (429, 503):
            return 0.0

        registry_key = f"{tld}:{endpoint}"
        
        # Increment consecutive error count
        self._consecutive_errors[registry_key] += 1
        consecutive = self._consecutive_errors[registry_key]

        # Get base delay from config or use default
        base_delay = self.DEFAULT_ERROR_DELAY
        
        # Try to get a more specific delay from config
        if tld in self._config.per_tld:
            base_delay = max(base_delay, self._config.per_tld[tld].min_delay_seconds)
        if endpoint in self._config.per_endpoint:
            base_delay = max(base_delay, self._config.per_endpoint[endpoint].min_delay_seconds)

        # Calculate exponential backoff
        delay = base_delay * (self.ADAPTIVE_DELAY_BASE ** (consecutive - 1))
        
        # Cap at maximum
        return min(delay, self.MAX_ADAPTIVE_DELAY)

    def reset_error_count(self, tld: str, endpoint: str) -> None:
        """
        Reset the consecutive error count for a registry.
        
        Should be called after a successful request.
        
        Args:
            tld: The TLD
            endpoint: The endpoint
        """
        registry_key = f"{tld}:{endpoint}"
        self._consecutive_errors[registry_key] = 0

    def get_lock(self, tld: str, endpoint: str) -> asyncio.Lock:
        """
        Get the lock for a specific registry.
        
        This allows external code to ensure serial access when needed.
        
        Args:
            tld: The TLD
            endpoint: The endpoint
            
        Returns:
            The asyncio.Lock for this registry
        """
        registry_key = f"{tld}:{endpoint}"
        return self._locks[registry_key]
