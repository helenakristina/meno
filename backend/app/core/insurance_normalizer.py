# Canonical mapping from raw scraped values to user-facing display names.
# Applied at two points: scraper transform step and API response layer.
# Add new mappings here as additional data sources are ingested.

INSURANCE_NAME_MAP: dict[str, str] = {
    "Commercial Insurance": "Private Insurance",
}


def normalize_insurance_name(name: str) -> str:
    """Normalize a raw insurance name to its user-facing display name.

    Returns the original value if no mapping exists.
    Case-sensitive match — scraped values are consistent from NAMS.
    """
    return INSURANCE_NAME_MAP.get(name, name)


def normalize_insurance_list(names: list[str]) -> list[str]:
    """Apply normalize_insurance_name to every item in a list."""
    return [normalize_insurance_name(n) for n in names]
