"""Unit tests for retry and circuit breaker module."""

from unittest.mock import MagicMock, patch

import pytest

from ragents.errors import RAGentError
from ragents.llm.retry import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    retry,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_init_defaults(self):
        """Default threshold and timeout."""
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0
        assert cb.state == "closed"
        assert cb.failure_count == 0

    def test_init_custom(self):
        """Custom threshold and timeout."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 10.0

    def test_call_success(self):
        """Successful call returns result."""
        cb = CircuitBreaker()
        result = cb.call(lambda: "hello")
        assert result == "hello"

    def test_call_success_with_args(self):
        """Successful call passes args."""
        cb = CircuitBreaker()
        result = cb.call(lambda x, y: x + y, 2, 3)
        assert result == 5

    def test_call_failure_increments(self):
        """Failure increments failure_count."""
        cb = CircuitBreaker()
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.failure_count == 1

    def test_call_success_decrements(self):
        """Success decrements failure_count."""
        cb = CircuitBreaker()
        cb.failure_count = 3
        cb.call(lambda: "ok")
        assert cb.failure_count == 2

    def test_trips_to_open(self):
        """Enough failures trip to open state."""
        cb = CircuitBreaker(failure_threshold=2)

        def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)

        assert cb.state == "open"

    def test_open_state_fast_fail(self):
        """Open state fast-fails without calling function."""
        cb = CircuitBreaker()
        cb.state = "open"
        cb.last_failure_time = 0  # Long ago

        # After timeout, should transition to half_open
        # But if we set it to recent, it should fail
        cb.last_failure_time = 9999999999  # Far future

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: "should not run")

    def test_half_open_after_timeout(self):
        """After recovery timeout, state becomes half-open."""
        cb = CircuitBreaker(recovery_timeout=0.1)
        cb.state = "open"
        cb.last_failure_time = 0  # Long ago

        # Wait for recovery
        import time
        time.sleep(0.15)

        # Call should transition to half_open and succeed
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == "closed"

    def test_success_resets_state(self):
        """Success resets to closed state."""
        cb = CircuitBreaker()
        cb.failure_count = 3
        cb.state = "half_open"
        cb.call(lambda: "ok")
        assert cb.state == "closed"

    def test_success_does_not_go_negative(self):
        """Success doesn't make failure_count negative."""
        cb = CircuitBreaker()
        cb.failure_count = 0
        cb.call(lambda: "ok")
        assert cb.failure_count == 0


class TestRetryDecorator:
    """Tests for @retry decorator."""

    def test_success_no_retry(self):
        """Successful function is called once."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = func()
        assert result == "ok"
        assert call_count == 1

    def test_retry_then_success(self):
        """Retry on failure, then succeed."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = func()
        assert result == "ok"
        assert call_count == 2

    def test_retry_exhausted(self):
        """All retries exhausted raises last error."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError) as exc:
            func()
        assert "fail" in str(exc.value)
        assert call_count == 3

    def test_retry_specific_exceptions(self):
        """Only retry specified exceptions."""
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            func()
        assert call_count == 1  # No retry for TypeError

    def test_non_retryable_ragent_error(self):
        """RAGentError with retryable=False is not retried."""
        call_count = 0

        class NonRetryableError(RAGentError):
            retryable = False

        @retry(max_attempts=3, base_delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("not retryable")

        with pytest.raises(NonRetryableError):
            func()
        assert call_count == 1

    def test_retryable_ragent_error(self):
        """RAGentError with retryable=True is retried."""
        call_count = 0

        class RetryableError(RAGentError):
            retryable = True

        @retry(max_attempts=3, base_delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("retry me")
            return "ok"

        result = func()
        assert result == "ok"
        assert call_count == 2

    def test_preserves_function_name(self):
        """Decorator preserves function metadata."""
        @retry(max_attempts=2, base_delay=0.01)
        def my_function():
            return "ok"

        assert my_function.__name__ == "my_function"

    @patch("ragents.llm.retry.time.sleep")
    def test_delay_calculation(self, mock_sleep):
        """Delay increases exponentially."""
        call_count = 0

        @retry(max_attempts=4, base_delay=1.0, max_delay=100.0)
        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            func()

        # Should have 3 delays (attempts 0, 1, 2 before final failure)
        assert mock_sleep.call_count == 3
        # First delay: ~1.0, second: ~2.0, third: ~4.0
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] >= 1.0
        assert delays[1] >= 2.0
        assert delays[2] >= 4.0

    @patch("ragents.llm.retry.time.sleep")
    def test_max_delay_cap(self, mock_sleep):
        """Delay is capped at max_delay."""
        @retry(max_attempts=5, base_delay=10.0, max_delay=15.0)
        def func():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            func()

        # All delays should be <= max_delay
        for call in mock_sleep.call_args_list:
            assert call.args[0] <= 15.0
