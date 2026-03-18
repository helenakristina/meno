"""Date and time utilities for business logic.

This module contains date calculations, age computation, and time-related
business logic used across repositories, services, and analysis features.

Examples:
- User age calculation (repository, services, cycle analysis)
- Cycle date calculations (period tracking)
- Timeline analysis (symptom trends, patterns)

Keep business logic here, not scattered across repositories or services.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def calculate_age(date_of_birth: str) -> int:
    """Calculate age in years from ISO date string.

    Args:
        date_of_birth: ISO format date string (YYYY-MM-DD).

    Returns:
        Age in years at current date.

    Raises:
        ValueError: If date format is invalid or date is in future.

    Example:
        >>> calculate_age("1974-03-15")
        50
    """
    try:
        dob = date.fromisoformat(date_of_birth)
    except ValueError as e:
        raise ValueError(
            f"Invalid date format '{date_of_birth}'. Expected YYYY-MM-DD."
        ) from e

    today = date.today()

    if dob > today:
        raise ValueError(f"Date of birth cannot be in the future: {date_of_birth}")

    # Calculate age, accounting for whether birthday has passed this year
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    logger.debug("Calculated age for DOB %s: %d years", date_of_birth, age)
    return age


def get_date_range(days_back: int) -> tuple[date, date]:
    """Get date range from N days ago to today.

    Args:
        days_back: Number of days to go back (must be 1-365).

    Returns:
        Tuple of (start_date, end_date) as date objects.

    Raises:
        ValueError: If days_back is invalid.

    Example:
        >>> start, end = get_date_range(60)
        # Returns (2026-01-09, 2026-03-10) on 2026-03-10
    """
    if not isinstance(days_back, int) or days_back < 1 or days_back > 365:
        raise ValueError(f"days_back must be 1-365, got {days_back}")

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    logger.debug("Date range for past %d days: %s to %s", days_back, start_date, end_date)
    return start_date, end_date


def is_valid_iso_date(date_string: str) -> bool:
    """Check if string is valid ISO format date (YYYY-MM-DD).

    Args:
        date_string: String to validate.

    Returns:
        True if valid ISO date format.

    Example:
        >>> is_valid_iso_date("2026-03-10")
        True
        >>> is_valid_iso_date("2026-13-01")
        False
    """
    try:
        date.fromisoformat(date_string)
        return True
    except (ValueError, TypeError):
        return False


def iso_date_to_display(iso_date: str) -> str:
    """Convert ISO date string to human-readable format.

    Args:
        iso_date: ISO format date string (YYYY-MM-DD).

    Returns:
        Formatted date string (e.g., "March 10, 2026").

    Raises:
        ValueError: If date format is invalid.

    Example:
        >>> iso_date_to_display("2026-03-10")
        "March 10, 2026"
    """
    try:
        d = date.fromisoformat(iso_date)
        return d.strftime("%B %d, %Y")
    except ValueError as e:
        raise ValueError(f"Invalid date format: {iso_date}") from e


def validate_date_of_birth(dob: date) -> None:
    """Validate date of birth for onboarding: must be past and user must be 18+.

    Args:
        dob: Date of birth as a date object.

    Raises:
        ValueError: If dob is today/future or user is under 18.

    Example:
        >>> validate_date_of_birth(date(1985, 6, 15))  # no exception
        >>> validate_date_of_birth(date(2010, 1, 1))  # raises ValueError (under 18)
    """
    today = date.today()
    if dob >= today:
        raise ValueError("date_of_birth must be in the past")
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age < 18:
        raise ValueError("User must be at least 18 years old")


def days_since(iso_date: str) -> int:
    """Calculate days since a given ISO date.

    Args:
        iso_date: ISO format date string (YYYY-MM-DD).

    Returns:
        Number of days since that date (negative if date is in future).

    Raises:
        ValueError: If date format is invalid.

    Example:
        >>> days_since("2026-03-01")  # Called on 2026-03-10
        9
    """
    try:
        past_date = date.fromisoformat(iso_date)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {iso_date}") from e

    today = date.today()
    delta = today - past_date
    return delta.days


def calculate_cycle_length(current_start: date, previous_start: date) -> int:
    """Calculate cycle length in days between two period start dates.

    Args:
        current_start: Start date of the current period.
        previous_start: Start date of the previous period.

    Returns:
        Number of days between the two period start dates.

    Raises:
        ValueError: If current_start is not after previous_start.

    Example:
        >>> calculate_cycle_length(date(2026, 3, 1), date(2026, 1, 29))
        31
    """
    if current_start <= previous_start:
        raise ValueError("current_start must be after previous_start")
    return (current_start - previous_start).days


def calculate_cycle_variability(cycle_lengths: list[int]) -> float:
    """Calculate standard deviation of cycle lengths.

    High variability is a key perimenopause indicator. Returns 0.0 if fewer
    than 2 cycle lengths are provided (not enough data for variability).

    Args:
        cycle_lengths: List of cycle lengths in days.

    Returns:
        Standard deviation of cycle lengths, or 0.0 if insufficient data.

    Example:
        >>> calculate_cycle_variability([28, 32, 26, 30])
        2.23...
    """
    if len(cycle_lengths) < 2:
        return 0.0
    mean = sum(cycle_lengths) / len(cycle_lengths)
    variance = sum((x - mean) ** 2 for x in cycle_lengths) / len(cycle_lengths)
    return variance ** 0.5


def months_since_date(past_date: date) -> int:
    """Calculate full calendar months elapsed since a given date.

    Args:
        past_date: The date to count months from.

    Returns:
        Number of full months since past_date (0 if less than a month ago).

    Example:
        >>> months_since_date(date(2025, 3, 16))  # Called on 2026-03-16
        12
    """
    today = date.today()
    return (today.year - past_date.year) * 12 + (today.month - past_date.month)
