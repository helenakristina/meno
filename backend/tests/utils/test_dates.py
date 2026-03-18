"""Tests for date utilities."""

import pytest
from datetime import date, timedelta
from app.utils.dates import (
    calculate_age,
    calculate_cycle_length,
    calculate_cycle_variability,
    get_date_range,
    is_valid_iso_date,
    iso_date_to_display,
    days_since,
    months_since_date,
)


class TestCalculateAge:
    """Test age calculation."""

    def test_calculate_age_known_value(self):
        """Test age calculation with known value."""
        # Someone born in 1974 should be around 50-52 years old in 2026
        age = calculate_age("1974-03-10")
        assert isinstance(age, int)
        assert 50 <= age <= 52

    def test_calculate_age_recent_birthday(self):
        """Test age when birthday recently occurred."""
        # Use a recent birthday (early in year)
        age = calculate_age("1975-01-01")
        assert isinstance(age, int)
        assert age >= 50

    def test_calculate_age_upcoming_birthday(self):
        """Test age when birthday is coming up."""
        # Use a future birthday (late in year)
        age = calculate_age("1975-12-31")
        assert isinstance(age, int)
        assert age >= 49

    def test_calculate_age_invalid_format_slash(self):
        """Test that invalid date format with slashes raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            calculate_age("1974/03/10")

    def test_calculate_age_invalid_format_spaces(self):
        """Test that invalid date format with spaces raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            calculate_age("1974 03 10")

    def test_calculate_age_future_date_raises_error(self):
        """Test that future date raises ValueError."""
        future_date = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValueError, match="cannot be in the future"):
            calculate_age(future_date)

    def test_calculate_age_invalid_month(self):
        """Test that invalid month raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            calculate_age("1974-13-01")

    def test_calculate_age_invalid_day(self):
        """Test that invalid day raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            calculate_age("1974-02-30")

    def test_calculate_age_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            calculate_age("")

    def test_calculate_age_none_type(self):
        """Test that None type raises error."""
        with pytest.raises((ValueError, AttributeError, TypeError)):
            calculate_age(None)  # type: ignore


class TestGetDateRange:
    """Test date range calculation."""

    def test_get_date_range_60_days(self):
        """Test getting date range for past 60 days."""
        start, end = get_date_range(60)
        assert isinstance(start, date)
        assert isinstance(end, date)
        assert end == date.today()
        assert (end - start).days == 60

    def test_get_date_range_1_day(self):
        """Test getting date range for past 1 day."""
        start, end = get_date_range(1)
        assert (end - start).days == 1

    def test_get_date_range_365_days(self):
        """Test getting date range for past 365 days."""
        start, end = get_date_range(365)
        assert (end - start).days == 365

    def test_get_date_range_30_days(self):
        """Test getting date range for past 30 days."""
        start, end = get_date_range(30)
        assert (end - start).days == 30

    def test_get_date_range_invalid_zero_raises_error(self):
        """Test that 0 days raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-365"):
            get_date_range(0)

    def test_get_date_range_invalid_too_large_raises_error(self):
        """Test that >365 days raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-365"):
            get_date_range(366)

    def test_get_date_range_invalid_negative_raises_error(self):
        """Test that negative days raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-365"):
            get_date_range(-1)

    def test_get_date_range_invalid_float_raises_error(self):
        """Test that float raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-365"):
            get_date_range(60.5)  # type: ignore

    def test_get_date_range_invalid_string_raises_error(self):
        """Test that string raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-365"):
            get_date_range("60")  # type: ignore


class TestIsValidIsoDate:
    """Test ISO date validation."""

    def test_valid_iso_date(self):
        """Test valid ISO date."""
        assert is_valid_iso_date("2026-03-10") is True

    def test_valid_iso_date_january(self):
        """Test valid January date."""
        assert is_valid_iso_date("2026-01-01") is True

    def test_valid_iso_date_december(self):
        """Test valid December date."""
        assert is_valid_iso_date("2026-12-31") is True

    def test_valid_leap_year_date(self):
        """Test valid leap year date."""
        assert is_valid_iso_date("2024-02-29") is True

    def test_invalid_leap_year_date(self):
        """Test invalid leap year date."""
        assert is_valid_iso_date("2025-02-29") is False

    def test_invalid_month_13(self):
        """Test invalid month 13."""
        assert is_valid_iso_date("2026-13-01") is False

    def test_invalid_day_32(self):
        """Test invalid day 32."""
        assert is_valid_iso_date("2026-03-32") is False

    def test_invalid_format_slashes(self):
        """Test invalid format with slashes."""
        assert is_valid_iso_date("2026/03/10") is False

    def test_invalid_format_spaces(self):
        """Test invalid format with spaces."""
        assert is_valid_iso_date("2026 03 10") is False

    def test_invalid_non_string_int(self):
        """Test invalid non-string input (int)."""
        assert is_valid_iso_date(123) is False

    def test_invalid_non_string_none(self):
        """Test invalid non-string input (None)."""
        assert is_valid_iso_date(None) is False

    def test_invalid_empty_string(self):
        """Test invalid empty string."""
        assert is_valid_iso_date("") is False

    def test_invalid_partial_date(self):
        """Test invalid partial date."""
        assert is_valid_iso_date("2026-03") is False


class TestIsoDateToDisplay:
    """Test date formatting."""

    def test_format_date(self):
        """Test date formatting."""
        result = iso_date_to_display("2026-03-10")
        assert result == "March 10, 2026"

    def test_format_date_january(self):
        """Test formatting January date."""
        result = iso_date_to_display("2026-01-01")
        assert result == "January 01, 2026"

    def test_format_date_december(self):
        """Test formatting December date."""
        result = iso_date_to_display("2026-12-31")
        assert result == "December 31, 2026"

    def test_format_date_single_digit_day(self):
        """Test formatting with single digit day."""
        result = iso_date_to_display("2026-03-05")
        assert result == "March 05, 2026"

    def test_format_date_leap_year(self):
        """Test formatting leap year date."""
        result = iso_date_to_display("2024-02-29")
        assert result == "February 29, 2024"

    def test_invalid_date_raises_error(self):
        """Test that invalid date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            iso_date_to_display("2026-13-01")

    def test_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            iso_date_to_display("2026/03/10")

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            iso_date_to_display("")


class TestDaysSince:
    """Test days since calculation."""

    def test_days_since_past_date(self):
        """Test days since a past date."""
        past_date = (date.today() - timedelta(days=10)).isoformat()
        days = days_since(past_date)
        assert days == 10

    def test_days_since_today(self):
        """Test days since today."""
        today = date.today().isoformat()
        days = days_since(today)
        assert days == 0

    def test_days_since_yesterday(self):
        """Test days since yesterday."""
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        days = days_since(yesterday)
        assert days == 1

    def test_days_since_far_past(self):
        """Test days since far past date."""
        past_date = (date.today() - timedelta(days=365)).isoformat()
        days = days_since(past_date)
        assert days == 365

    def test_days_since_future_date_negative(self):
        """Test days since future date (negative)."""
        future_date = (date.today() + timedelta(days=5)).isoformat()
        days = days_since(future_date)
        assert days == -5

    def test_days_since_tomorrow_negative(self):
        """Test days since tomorrow (negative)."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        days = days_since(tomorrow)
        assert days == -1

    def test_days_since_invalid_date_raises_error(self):
        """Test that invalid date raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            days_since("2026-13-01")

    def test_days_since_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            days_since("2026/03/10")

    def test_days_since_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            days_since("")


class TestCalculateCycleLength:
    """Test cycle length calculation."""

    def test_calculate_cycle_length_28_day_cycle(self):
        result = calculate_cycle_length(date(2026, 2, 26), date(2026, 1, 29))
        assert result == 28

    def test_calculate_cycle_length_31_day_cycle(self):
        result = calculate_cycle_length(date(2026, 3, 1), date(2026, 1, 29))
        assert result == 31

    def test_calculate_cycle_length_long_cycle(self):
        result = calculate_cycle_length(date(2026, 3, 15), date(2026, 1, 1))
        assert result == 73

    def test_calculate_cycle_length_when_same_date_raises_error(self):
        with pytest.raises(ValueError):
            calculate_cycle_length(date(2026, 1, 15), date(2026, 1, 15))

    def test_calculate_cycle_length_when_current_before_previous_raises_error(self):
        with pytest.raises(ValueError):
            calculate_cycle_length(date(2026, 1, 1), date(2026, 3, 1))


class TestCalculateCycleVariability:
    """Test cycle variability (standard deviation) calculation."""

    def test_calculate_cycle_variability_regular_cycles(self):
        # [28, 28, 28, 28] → std dev = 0
        result = calculate_cycle_variability([28, 28, 28, 28])
        assert result == 0.0

    def test_calculate_cycle_variability_irregular_cycles(self):
        # [20, 40] → mean=30, variance=100, std=10
        result = calculate_cycle_variability([20, 40])
        assert result == pytest.approx(10.0)

    def test_calculate_cycle_variability_returns_float(self):
        result = calculate_cycle_variability([28, 32, 26, 30])
        assert isinstance(result, float)
        assert result > 0

    def test_calculate_cycle_variability_single_value_returns_zero(self):
        result = calculate_cycle_variability([28])
        assert result == 0.0

    def test_calculate_cycle_variability_empty_list_returns_zero(self):
        result = calculate_cycle_variability([])
        assert result == 0.0

    def test_calculate_cycle_variability_known_value(self):
        # [26, 28, 30, 32] → mean=29, deviations=[-3,-1,1,3] → variance=5, std≈2.236
        result = calculate_cycle_variability([26, 28, 30, 32])
        assert result == pytest.approx(2.2360679, rel=1e-4)


class TestMonthsSinceDate:
    """Test months since date calculation."""

    def test_months_since_date_one_year_ago(self):
        one_year_ago = date.today().replace(year=date.today().year - 1)
        result = months_since_date(one_year_ago)
        assert result == 12

    def test_months_since_date_same_month(self):
        first_of_month = date.today().replace(day=1)
        result = months_since_date(first_of_month)
        assert result == 0

    def test_months_since_date_one_month_ago(self):
        today = date.today()
        if today.month == 1:
            one_month_ago = today.replace(year=today.year - 1, month=12)
        else:
            one_month_ago = today.replace(month=today.month - 1)
        result = months_since_date(one_month_ago)
        assert result == 1

    def test_months_since_date_13_months(self):
        today = date.today()
        thirteen_months_ago = today.replace(
            year=today.year - 1,
            month=today.month - 1 if today.month > 1 else 12,
        )
        if today.month == 1:
            thirteen_months_ago = today.replace(year=today.year - 2, month=12)
        result = months_since_date(thirteen_months_ago)
        assert result == 13
