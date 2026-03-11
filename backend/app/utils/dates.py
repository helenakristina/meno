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
