"""
Resilience module: Error handling, timeouts, retries, and rate limiting.

Provides production-grade resilience patterns:
- Token bucket rate limiting for API calls
- Exponential backoff retry logic
- Configurable timeout handling
- Graceful error recovery
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    burst_multiplier: float = 1.5  # Allow short bursts above limit


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for API calls.

    Allows smooth rate limiting with burst capacity.
    Tracks both request count and token usage.
    """

    def __init__(self, config: RateLimitConfig):
        self.config = config

        # Request bucket
        self._request_tokens = config.requests_per_minute * config.burst_multiplier
        self._request_capacity = config.requests_per_minute * config.burst_multiplier
        self._request_refill_rate = config.requests_per_minute / 60.0  # per second

        # Token bucket (for LLM token limits)
        self._token_tokens = config.tokens_per_minute * config.burst_multiplier
        self._token_capacity = config.tokens_per_minute * config.burst_multiplier
        self._token_refill_rate = config.tokens_per_minute / 60.0

        self._last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 1000) -> float:
        """
        Acquire permission to make a request.

        Args:
            estimated_tokens: Estimated token usage for this request

        Returns:
            Wait time in seconds (0 if immediately available)
        """
        async with self._lock:
            self._refill()

            # Check if we have capacity
            if self._request_tokens >= 1 and self._token_tokens >= estimated_tokens:
                self._request_tokens -= 1
                self._token_tokens -= estimated_tokens
                return 0.0

            # Calculate wait time
            request_wait = 0.0 if self._request_tokens >= 1 else (1 - self._request_tokens) / self._request_refill_rate
            token_wait = 0.0 if self._token_tokens >= estimated_tokens else (estimated_tokens - self._token_tokens) / self._token_refill_rate

            return max(request_wait, token_wait)

    async def wait_and_acquire(self, estimated_tokens: int = 1000) -> None:
        """Wait until we can acquire, then acquire."""
        while True:
            wait_time = await self.acquire(estimated_tokens)
            if wait_time == 0:
                return
            logger.debug(f"Rate limited, waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill
        self._last_refill = now

        self._request_tokens = min(
            self._request_capacity,
            self._request_tokens + elapsed * self._request_refill_rate
        )
        self._token_tokens = min(
            self._token_capacity,
            self._token_tokens + elapsed * self._token_refill_rate
        )

    def record_actual_usage(self, actual_tokens: int, estimated_tokens: int = 1000) -> None:
        """
        Record actual token usage after a call.

        Adjusts the token bucket if we overestimated or underestimated.
        """
        difference = estimated_tokens - actual_tokens
        self._token_tokens = min(
            self._token_capacity,
            self._token_tokens + difference
        )

    def get_status(self) -> dict:
        """Get current rate limiter status."""
        self._refill()
        return {
            "request_tokens_available": self._request_tokens,
            "request_capacity": self._request_capacity,
            "token_tokens_available": self._token_tokens,
            "token_capacity": self._token_capacity,
        }


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retryable_exceptions: tuple = (
        TimeoutError,
        ConnectionError,
    )


class RetryError(Exception):
    """Raised when all retries are exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None, attempts: int = 0):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


async def retry_with_backoff(
    func: Callable[..., Any],
    config: RetryConfig | None = None,
    *args,
    **kwargs,
) -> Any:
    """
    Execute a function with exponential backoff retry.

    Args:
        func: Async function to execute
        config: Retry configuration
        *args, **kwargs: Arguments to pass to the function

    Returns:
        Result of the function

    Raises:
        RetryError: If all retries are exhausted
    """
    import random

    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except config.retryable_exceptions as e:
            last_exception = e
            if attempt == config.max_retries:
                break

            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** attempt),
                config.max_delay
            )

            # Add jitter
            if config.jitter:
                delay *= (0.5 + random.random())

            logger.warning(
                f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)

        except Exception as e:
            # Non-retryable exception
            raise

    raise RetryError(
        f"All {config.max_retries + 1} attempts failed",
        last_exception=last_exception,
        attempts=config.max_retries + 1,
    )


def with_retry(config: RetryConfig | None = None):
    """
    Decorator to add retry behavior to an async function.

    Usage:
        @with_retry(RetryConfig(max_retries=3))
        async def call_api():
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await retry_with_backoff(func, config, *args, **kwargs)
        return wrapper
    return decorator


@dataclass
class TimeoutConfig:
    """Configuration for timeout handling."""
    tool_timeout: float = 10.0  # seconds
    llm_timeout: float = 30.0  # seconds
    total_timeout: float = 120.0  # seconds for entire operation


class TimeoutError(Exception):
    """Raised when an operation times out."""

    def __init__(self, message: str, operation: str = "", timeout: float = 0):
        super().__init__(message)
        self.operation = operation
        self.timeout = timeout


async def with_timeout(
    coro,
    timeout: float,
    operation_name: str = "operation",
) -> Any:
    """
    Execute a coroutine with a timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        operation_name: Name for error messages

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"{operation_name} timed out after {timeout}s",
            operation=operation_name,
            timeout=timeout,
        )


@dataclass
class FallbackResult:
    """Result when using fallback behavior."""
    data: Any
    fallback_used: bool = False
    original_error: str | None = None
    fallback_message: str | None = None


async def with_fallback(
    primary: Callable[..., Any],
    fallback: Callable[..., Any] | Any,
    *args,
    error_message: str = "Primary operation failed",
    **kwargs,
) -> FallbackResult:
    """
    Execute primary function with fallback on failure.

    Args:
        primary: Primary async function to try
        fallback: Fallback function or static value
        *args, **kwargs: Arguments for the functions
        error_message: Message template for fallback

    Returns:
        FallbackResult with data and status
    """
    try:
        result = await primary(*args, **kwargs)
        return FallbackResult(data=result, fallback_used=False)

    except Exception as e:
        logger.warning(f"{error_message}: {e}. Using fallback.")

        # Execute fallback
        if callable(fallback):
            try:
                fallback_data = await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            except Exception as fallback_error:
                # Even fallback failed
                return FallbackResult(
                    data=None,
                    fallback_used=True,
                    original_error=str(e),
                    fallback_message=f"Fallback also failed: {fallback_error}",
                )
        else:
            fallback_data = fallback

        return FallbackResult(
            data=fallback_data,
            fallback_used=True,
            original_error=str(e),
            fallback_message=error_message,
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # failures before opening
    recovery_timeout: float = 30.0  # seconds before trying again
    half_open_requests: int = 1  # requests to allow when half-open


class CircuitBreakerState:
    """Possible states for circuit breaker."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Rejecting all requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for failing fast.

    When failures exceed threshold, stop trying and fail immediately.
    Periodically test if the service has recovered.
    """

    def __init__(self, config: CircuitBreakerConfig, name: str = "default"):
        self.config = config
        self.name = name
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_successes = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitBreakerState.OPEN:
                if time.time() - self._last_failure_time >= self.config.recovery_timeout:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_successes = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN",
                        breaker_name=self.name,
                    )

        try:
            result = await func(*args, **kwargs)

            async with self._lock:
                if self._state == CircuitBreakerState.HALF_OPEN:
                    self._half_open_successes += 1
                    if self._half_open_successes >= self.config.half_open_requests:
                        self._state = CircuitBreakerState.CLOSED
                        self._failure_count = 0
                        logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
                elif self._state == CircuitBreakerState.CLOSED:
                    self._failure_count = 0

            return result

        except Exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitBreakerState.OPEN
                    logger.warning(
                        f"Circuit breaker '{self.name}' transitioning to OPEN "
                        f"after {self._failure_count} failures"
                    )

            raise

    def get_status(self) -> dict:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str, breaker_name: str = ""):
        super().__init__(message)
        self.breaker_name = breaker_name


# Convenience: Global rate limiter instance
_global_rate_limiter: TokenBucketRateLimiter | None = None


def get_rate_limiter(config: RateLimitConfig | None = None) -> TokenBucketRateLimiter:
    """Get or create the global rate limiter."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = TokenBucketRateLimiter(config or RateLimitConfig())
    return _global_rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter."""
    global _global_rate_limiter
    _global_rate_limiter = None
