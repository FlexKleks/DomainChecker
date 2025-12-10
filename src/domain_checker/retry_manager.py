"""
Retry Manager for the domain checker system.

This module provides retry logic with exponential backoff for transient errors,
respecting the conservative approach where exhausted retries result in "taken".

Requirements covered:
- 5.1: Retry with exponentially increasing wait times on transient errors
- 5.2: Max retries exhausted → mark domain as taken (conservative)
- 5.3: No retry on definitive "taken" signal
- 5.4: Allow customization of retry count and wait times
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable, Generic, Optional, TypeVar

from .config import RetryConfig
from .enums import RDAPErrorCode, RDAPStatus

if TYPE_CHECKING:
    from .rdap_client import RDAPResponse

T = TypeVar("T")


@dataclass
class RetryResult(Generic[T]):
    """Result of a retry operation."""

    success: bool
    result: Optional[T]
    attempts: int
    last_error: Optional[Exception]


class RetryManager:
    """
    Manages retry logic with exponential backoff.

    This class implements retry behavior for transient errors while
    respecting the conservative approach: if all retries are exhausted,
    the domain should be treated as taken.
    """

    # Error codes that indicate transient errors (should retry)
    TRANSIENT_ERROR_CODES = {
        RDAPErrorCode.TIMEOUT.value,
        RDAPErrorCode.SERVER_ERROR.value,
        RDAPErrorCode.RATE_LIMITED.value,
        RDAPErrorCode.NETWORK_ERROR.value,
        "timeout",
        "server_error",
        "rate_limited",
        "network_error",
    }

    # Status that indicates definitive "taken" (should NOT retry)
    DEFINITIVE_TAKEN_STATUS = RDAPStatus.FOUND

    def __init__(self, config: RetryConfig) -> None:
        """
        Initialize the retry manager.

        Args:
            config: Retry configuration with max_retries, delays, and retryable errors
        """
        self._config = config

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate wait time with exponential backoff.

        Requirement 5.1: delay(n) >= base_delay * 2^n, capped at max_delay.

        Args:
            attempt: The current attempt number (0-indexed)

        Returns:
            The delay in seconds before the next retry
        """
        delay = self._config.base_delay_seconds * (2 ** attempt)
        return min(delay, self._config.max_delay_seconds)

    def is_retryable_error(self, error_code) -> bool:
        """
        Check if an error code indicates a retryable (transient) error.

        Args:
            error_code: The error code to check (can be string or RDAPErrorCode enum)

        Returns:
            True if the error is transient and should be retried
        """
        # Normalize error_code to string for comparison
        if hasattr(error_code, 'value'):
            # It's an enum, get its value
            error_code_str = error_code.value
        else:
            error_code_str = str(error_code)
        
        # Check against configured retryable errors
        if error_code_str in self._config.retryable_errors:
            return True
        # Also check against known transient error codes
        return error_code_str in self.TRANSIENT_ERROR_CODES

    def is_definitive_taken(self, response: RDAPResponse) -> bool:
        """
        Check if a response indicates a definitive "taken" status.

        Requirement 5.3: No retry on definitive "taken" signal.

        Args:
            response: The RDAP response to check

        Returns:
            True if the domain is definitively taken (should not retry)
        """
        return response.status == self.DEFINITIVE_TAKEN_STATUS

    def should_retry(self, response: RDAPResponse) -> bool:
        """
        Determine if a response warrants a retry.

        Args:
            response: The RDAP response to evaluate

        Returns:
            True if the operation should be retried
        """
        # Never retry if domain is definitively taken
        if self.is_definitive_taken(response):
            return False

        # Retry if there's an error with a retryable error code
        if response.error is not None:
            return self.is_retryable_error(response.error.code)

        # Don't retry successful responses or NOT_FOUND
        return False

    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        is_retryable: Optional[Callable[[Exception], bool]] = None,
    ) -> RetryResult[T]:
        """
        Execute an operation with retry logic and exponential backoff.

        Requirement 5.1: Retry with exponentially increasing wait times.
        Requirement 5.2: Max retries exhausted returns failure.
        Requirement 5.4: Configurable retry count and wait times.

        Args:
            operation: The async operation to execute
            is_retryable: Optional function to determine if an exception is retryable.
                         If not provided, all exceptions are considered retryable.

        Returns:
            RetryResult containing success status, result, attempts, and last error
        """
        last_error: Optional[Exception] = None
        attempts = 0

        # Total attempts = 1 initial + max_retries
        max_attempts = self._config.max_retries + 1

        while attempts < max_attempts:
            try:
                result = await operation()
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts + 1,
                    last_error=None,
                )
            except Exception as e:
                last_error = e
                attempts += 1

                # Check if we should retry this exception
                should_retry = is_retryable(e) if is_retryable else True

                if not should_retry or attempts >= max_attempts:
                    break

                # Calculate and apply delay before next attempt
                delay = self._calculate_delay(attempts - 1)
                await asyncio.sleep(delay)

        return RetryResult(
            success=False,
            result=None,
            attempts=attempts,
            last_error=last_error,
        )

    async def execute_rdap_with_retry(
        self,
        operation: Callable[[], Awaitable[RDAPResponse]],
    ) -> tuple[RDAPResponse, int]:
        """
        Execute an RDAP operation with retry logic specific to RDAP responses.

        This method handles RDAP-specific retry logic:
        - Retries on transient errors (timeout, 503, 429)
        - Does NOT retry on definitive "taken" (FOUND status)
        - Does NOT retry on successful NOT_FOUND

        Args:
            operation: The async RDAP operation to execute

        Returns:
            Tuple of (final RDAPResponse, number of attempts)
        """
        attempts = 0
        max_attempts = self._config.max_retries + 1
        last_response: Optional[RDAPResponse] = None

        while attempts < max_attempts:
            try:
                response = await operation()
                last_response = response
                attempts += 1

                # Check if we should retry based on the response
                if not self.should_retry(response):
                    return response, attempts

                # Don't retry if we've exhausted attempts
                if attempts >= max_attempts:
                    break

                # Calculate and apply delay before next attempt
                delay = self._calculate_delay(attempts - 1)
                await asyncio.sleep(delay)

            except Exception:
                # On exception, treat as error and potentially retry
                attempts += 1
                if attempts >= max_attempts:
                    # Return an error response if we have no last_response
                    if last_response is None:
                        from .enums import RDAPErrorCode, RDAPStatus
                        from .rdap_client import RDAPError, RDAPResponse

                        last_response = RDAPResponse(
                            status=RDAPStatus.ERROR,
                            http_status_code=0,
                            raw_response=None,
                            parsed_fields=None,
                            error=RDAPError(
                                code=RDAPErrorCode.NETWORK_ERROR,
                                message="Max retries exhausted",
                            ),
                            response_time_ms=0.0,
                        )
                    break

                delay = self._calculate_delay(attempts - 1)
                await asyncio.sleep(delay)

        # Return the last response (or error response)
        assert last_response is not None
        return last_response, attempts
