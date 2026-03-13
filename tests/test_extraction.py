"""Tests for extraction utility functions: date validation, amount parsing, JSON repair."""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.extraction import validate_date, validate_amount, parse_extraction_output


# ── validate_date ──────────────────────────────────────────────

class TestValidateDate:
    """Test locale-aware date parsing."""

    def test_iso_format(self):
        assert validate_date("2025-11-17") == "2025-11-17"

    def test_european_dot_format(self):
        assert validate_date("17.11.2025") == "2025-11-17"

    def test_long_month_name(self):
        assert validate_date("November 17, 2025") == "2025-11-17"

    def test_day_month_name(self):
        assert validate_date("17 November 2025") == "2025-11-17"

    def test_unambiguous_day_first(self):
        # 25 > 12, so must be day
        assert validate_date("25/04/2025") == "2025-04-25"

    def test_unambiguous_month_first(self):
        # Second number > 12, so first must be month
        assert validate_date("04/25/2025") == "2025-04-25"

    def test_ambiguous_defaults_to_european(self):
        # Both <= 12: system defaults to dd/mm/yyyy (European)
        result = validate_date("03/04/2025")
        assert result == "2025-04-03"  # Day 3, Month 4

    def test_dash_separator_day_first(self):
        assert validate_date("25-04-2025") == "2025-04-25"

    def test_year_first_slash(self):
        assert validate_date("2025/11/17") == "2025-11-17"

    def test_returns_original_if_unparseable(self):
        result = validate_date("not a date")
        assert result == "not a date"

    def test_empty_string(self):
        result = validate_date("")
        assert result == ""


# ── validate_amount ────────────────────────────────────────────

class TestValidateAmount:
    """Test European and US amount parsing."""

    def test_simple_integer(self):
        assert validate_amount("100") == 100.0

    def test_simple_decimal(self):
        assert validate_amount("99.99") == 99.99

    def test_us_format_with_comma(self):
        assert validate_amount("1,234.56") == 1234.56

    def test_european_format(self):
        assert validate_amount("1.234,56") == 1234.56

    def test_european_decimal_only(self):
        # 3,50 → decimal (not 3 thousands and 50)
        assert validate_amount("3,50") == 3.50

    def test_thousands_comma_no_decimal(self):
        # 1,000 → exactly 3 digits after comma = thousands
        assert validate_amount("1,000") == 1000.0

    def test_dollar_sign(self):
        assert validate_amount("$1,234.56") == 1234.56

    def test_euro_sign(self):
        assert validate_amount("€1.234,56") == 1234.56

    def test_parenthetical_negative(self):
        assert validate_amount("(1,234.56)") == -1234.56

    def test_negative_with_dash(self):
        assert validate_amount("-500.00") == -500.0

    def test_space_thousands(self):
        assert validate_amount("1 234.56") == 1234.56

    def test_currency_word(self):
        assert validate_amount("EUR 1.234,56") == 1234.56

    def test_none_returns_none(self):
        assert validate_amount("abc") is None

    def test_empty_returns_none(self):
        assert validate_amount("") is None


# ── parse_extraction_output ────────────────────────────────────

class TestParseExtractionOutput:
    """Test JSON/regex extraction output parsing."""

    def test_valid_json(self):
        raw = '{"invoice_number": "INV-001", "amount": "1234.56"}'
        result = parse_extraction_output(raw, ["invoice_number", "amount"])
        assert result["invoice_number"] == "INV-001"
        assert result["amount"] == "1234.56"

    def test_json_with_trailing_text(self):
        raw = '{"name": "Test"}\nSome explanation text'
        result = parse_extraction_output(raw, ["name"])
        assert result["name"] == "Test"

    def test_missing_fields_return_none(self):
        raw = '{"invoice_number": "INV-001"}'
        result = parse_extraction_output(raw, ["invoice_number", "missing_field"])
        assert result["invoice_number"] == "INV-001"
        assert result.get("missing_field") is None

    def test_empty_input(self):
        result = parse_extraction_output("", ["field1"])
        assert result.get("field1") is None

    def test_malformed_json_with_repair(self):
        # Missing closing brace — json_repair should fix it
        raw = '{"invoice_number": "INV-001", "amount": "500"'
        result = parse_extraction_output(raw, ["invoice_number", "amount"])
        assert result.get("invoice_number") == "INV-001"
