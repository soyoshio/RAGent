"""Unit tests for validators module."""

import pytest

from ragents.utils.validators import nonempty_str


class TestNonemptyStr:
    """Tests for nonempty_str validator."""

    def test_valid_string(self):
        """Non-empty string passes through."""
        result = nonempty_str("hello")
        assert result == "hello"

    def test_strips_whitespace(self):
        """Leading/trailing whitespace is stripped."""
        result = nonempty_str("  hello  ")
        assert result == "hello"

    def test_empty_string_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError) as exc:
            nonempty_str("")
        assert "String must be non-empty" in str(exc.value)

    def test_whitespace_only_raises(self):
        """Whitespace-only string raises ValueError."""
        with pytest.raises(ValueError) as exc:
            nonempty_str("   ")
        assert "String must be non-empty" in str(exc.value)

    def test_tab_newline_raises(self):
        """Tab/newline only string raises ValueError."""
        with pytest.raises(ValueError):
            nonempty_str("\t\n")

    def test_single_char(self):
        """Single character is valid."""
        result = nonempty_str("x")
        assert result == "x"
