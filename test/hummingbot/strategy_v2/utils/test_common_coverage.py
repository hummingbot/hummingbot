"""
Coverage tests for strategy_v2/utils/common.py.
Targets line 74: parse_comma_separated_list with a non-empty comma-separated string.
"""

from hummingbot.strategy_v2.utils.common import parse_comma_separated_list


def test_parse_comma_separated_list_non_empty_string():
    """Covers line 74: string with commas is split and converted to floats."""
    result = parse_comma_separated_list("0.01,0.02,0.03")
    assert result == [0.01, 0.02, 0.03]


def test_parse_comma_separated_list_single_value_string():
    """Single value string (no comma) also goes through the split path."""
    result = parse_comma_separated_list("0.05")
    assert result == [0.05]


def test_parse_comma_separated_list_with_spaces():
    """Strips whitespace around values (line 74 uses x.strip())."""
    result = parse_comma_separated_list("0.1 , 0.2 , 0.3")
    assert result == [0.1, 0.2, 0.3]


def test_parse_comma_separated_list_none_returns_empty():
    assert parse_comma_separated_list(None) == []


def test_parse_comma_separated_list_empty_string_returns_empty():
    assert parse_comma_separated_list("") == []


def test_parse_comma_separated_list_scalar_int():
    assert parse_comma_separated_list(5) == [5.0]


def test_parse_comma_separated_list_scalar_float():
    assert parse_comma_separated_list(0.01) == [0.01]


def test_parse_comma_separated_list_already_list():
    result = parse_comma_separated_list([1.0, 2.0])
    assert result == [1.0, 2.0]
