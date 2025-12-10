"""Tests for case conversion utilities."""

import pytest
from ribasim_tools.case_conversions import pascal_to_snake_case, snake_to_pascal_case


class TestSnakeToPascalCase:
    """Tests for snake_to_pascal_case function."""

    def test_simple_conversion(self):
        """Test simple snake_case to PascalCase conversion."""
        assert snake_to_pascal_case("hello_world") == "HelloWorld"

    def test_single_word(self):
        """Test single word conversion."""
        assert snake_to_pascal_case("hello") == "Hello"

    def test_multiple_underscores(self):
        """Test conversion with multiple underscores."""
        assert snake_to_pascal_case("this_is_a_test") == "ThisIsATest"

    def test_empty_string(self):
        """Test empty string conversion."""
        assert snake_to_pascal_case("") == ""


class TestPascalToSnakeCase:
    """Tests for pascal_to_snake_case function."""

    def test_simple_conversion(self):
        """Test simple PascalCase to snake_case conversion."""
        assert pascal_to_snake_case("HelloWorld") == "hello_world"

    def test_single_word(self):
        """Test single word conversion."""
        assert pascal_to_snake_case("Hello") == "hello"

    def test_multiple_words(self):
        """Test conversion with multiple words."""
        assert pascal_to_snake_case("ThisIsATest") == "this_is_a_test"

    def test_lowercase_word(self):
        """Test conversion starting with lowercase."""
        assert pascal_to_snake_case("helloWorld") == "hello_world"

    def test_empty_string(self):
        """Test empty string conversion."""
        assert pascal_to_snake_case("") == ""
