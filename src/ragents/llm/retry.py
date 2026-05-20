"""Exponential backoff retry + circuit breaker."""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Callable, TypeVar

from ragents.errors import RAGentError
from ragents.utils.logger import logger

T = TypeVar("T")


class CircuitBreakerOpenError(RAGentError):
    """Circuit breaker is open — fast-fail."""

    error_code: str = "CIRCUIT_BREAKER_OPEN"
    retryable: bool = False


class CircuitBreaker:
    """Simple circuit breaker with closed/open/half-open states.

    States:
        closed: Normal operation; failures increment counter.
        open: Fast-fail all requests for recovery_timeout seconds.
        half-open: After timeout, allow one probe request.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute func with circuit breaker protection."""
        if self.state == "open":
            if self.last_failure_time is None:
                self.state = "half_open"
            elif time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open (last failure: "
                    f"{self.last_failure_time:.1f})"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Reset on success."""
        self.failure_count = max(0, self.failure_count - 1)
        self.state = "closed"

    def _on_failure(self) -> None:
        """Increment counter and possibly trip."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for exponential backoff retry with jitter.

    Formula: delay = min(base * (2 ** attempt) + random jitter, max_delay)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_attempts - 1:
                        logger.error(
                            "retry_exhausted",
                            func=func.__name__,
                            attempts=max_attempts,
                            error=str(e),
                        )
                        raise

                    # Check if error is explicitly not retryable
                    if isinstance(e, RAGentError) and not e.retryable:
                        raise

                    delay = min(
                        base_delay * (2 ** attempt) + random.random(),
                        max_delay,
                    )
                    logger.warning(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        delay=delay,
                        error=str(e),
                    )
                    time.sleep(delay)

            # Should never reach here
            raise RuntimeError("Unexpected: retry loop exited without result")

        return wrapper

    return decorator
