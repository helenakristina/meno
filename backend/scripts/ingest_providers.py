"""Supabase ingestion script for provider directory data.

Reads the cleaned provider JSON file produced by scrape_nams.py and upserts
records into the Supabase providers table.

USAGE:
    cd backend
    uv run scripts/ingest_providers.py
    uv run scripts/ingest_providers.py --dry-run   # preview without writing
    uv run scripts/ingest_providers.py --file path/to/other.json

REQUIREMENTS:
    - SUPABASE_URL and SUPABASE_SERVICE_KEY set in backend/.env
    - providers_clean.json produced by scrape_nams.py (or another scraper)

UPSERT STRATEGY:
    Records use a deterministic UUID (uuid5) based on name + city + state.
    This makes re-runs safe: existing records are updated in-place, new ones
    are inserted. No manual deduplication or unique DB constraint required.

BATCH SIZE: 50 records per request to avoid Supabase timeouts.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load environment variables from backend/.env
_BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(_BACKEND_DIR / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

DEFAULT_INPUT = Path(__file__).parent / "data" / "providers_clean.json"

BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_env() -> None:
    """Raise if required environment variables are missing."""
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_KEY:
        missing.append("SUPABASE_SERVICE_KEY")
    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        print(f"  Set them in {_BACKEND_DIR / '.env'}")
        sys.exit(1)


def deduplicate(providers: list[dict]) -> tuple[list[dict], int]:
    """Deduplicate by (name, city, state) before inserting.

    The scraper generates deterministic UUIDs based on name+city+state, so
    duplicate records will have the same id and Supabase upsert handles them.
    This step catches any edge cases where the same provider appears twice in
    the source data with slightly different formatting.

    Returns (deduplicated_list, skipped_count).
    """
    seen: set[tuple] = set()
    unique: list[dict] = []
    skipped = 0

    for p in providers:
        key = (
            (p.get("name") or "").lower().strip(),
            (p.get("city") or "").lower().strip(),
            (p.get("state") or "").lower().strip(),
        )
        if key in seen:
            skipped += 1
        else:
            seen.add(key)
            unique.append(p)

    return unique, skipped


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest(
    providers: list[dict],
    supabase: Client,
    dry_run: bool = False,
) -> dict:
    """Upsert providers into Supabase in batches.

    Returns summary dict with counts: total, inserted, errors.
    """
    total = len(providers)
    inserted = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"{'DRY RUN — ' if dry_run else ''}Ingesting {total} providers into Supabase")
    print(f"{'='*60}")

    for batch_start in range(0, total, BATCH_SIZE):
        batch = providers[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)

        if dry_run:
            print(f"  [DRY RUN] Would upsert records {batch_start + 1}–{batch_end}")
            inserted += len(batch)
            continue

        try:
            result = (
                supabase.table("providers")
                .upsert(batch, on_conflict="id")
                .execute()
            )
            batch_inserted = len(result.data) if result.data else len(batch)
            inserted += batch_inserted
            print(f"  Upserted records {batch_start + 1}–{batch_end} ({batch_inserted} records)")
        except Exception as e:
            errors += len(batch)
            print(f"  ERROR on batch {batch_start + 1}–{batch_end}: {e}")

    return {"total": total, "inserted": inserted, "errors": errors}


# ---------------------------------------------------------------------------
# Validation Report
# ---------------------------------------------------------------------------

def print_validation_report(providers: list[dict]) -> None:
    """Print a data quality summary after ingestion."""
    print(f"\n{'='*60}")
    print("VALIDATION REPORT")
    print(f"{'='*60}")

    total = len(providers)
    print(f"\nTotal providers: {total}")

    # Breakdown by state (top 10)
    state_counts = Counter(p.get("state") for p in providers if p.get("state"))
    print("\nTop 10 states:")
    for state, count in state_counts.most_common(10):
        bar = "█" * min(30, count // max(1, total // 300))
        pct = count / total * 100
        print(f"  {state:>4}  {count:>4}  ({pct:4.1f}%)  {bar}")

    # Provider type breakdown
    type_counts = Counter(p.get("provider_type") for p in providers)
    print("\nProvider types:")
    for ptype, count in type_counts.most_common():
        print(f"  {ptype or 'None':>25}  {count:>4}  ({count/total*100:4.1f}%)")

    # NAMS certified
    nams_count = sum(1 for p in providers if p.get("nams_certified"))
    print(f"\nNAMS certified (MSCP): {nams_count} ({nams_count/total*100:.1f}%)")

    # Phone numbers
    phone_count = sum(1 for p in providers if p.get("phone"))
    print(f"Have phone number:     {phone_count} ({phone_count/total*100:.1f}%)")

    # Websites
    website_count = sum(1 for p in providers if p.get("website"))
    print(f"Have website:          {website_count} ({website_count/total*100:.1f}%)")

    # Insurance data
    insurance_count = sum(1 for p in providers if p.get("insurance_accepted"))
    print(f"Have insurance data:   {insurance_count} ({insurance_count/total*100:.1f}%)")

    # Insurance breakdown
    insurance_types: Counter = Counter()
    for p in providers:
        for ins in p.get("insurance_accepted") or []:
            insurance_types[ins] += 1
    if insurance_types:
        print("\nInsurance types accepted:")
        for ins_type, count in insurance_types.most_common():
            print(f"  {ins_type:>40}  {count:>4}")

    # Data quality issues
    issues = []
    missing_city = [p["name"] for p in providers if not p.get("city")]
    missing_zip = [p["name"] for p in providers if not p.get("zip_code")]
    if missing_city:
        issues.append(f"{len(missing_city)} records missing city")
    if missing_zip:
        issues.append(f"{len(missing_zip)} records missing zip_code")

    if issues:
        print("\nData quality issues:")
        for issue in issues:
            print(f"  ⚠  {issue}")
    else:
        print("\n✓ No data quality issues detected")

    print()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest providers_clean.json into Supabase providers table"
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to clean JSON file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be ingested without writing to Supabase",
    )
    args = parser.parse_args()

    # Validate env
    validate_env()

    # Load input file
    if not args.file.exists():
        print(f"ERROR: Input file not found: {args.file}")
        print("  Run scrape_nams.py first to generate it.")
        sys.exit(1)

    print(f"\n→ Loading providers from {args.file}...")
    with open(args.file) as f:
        providers = json.load(f)
    print(f"  Loaded {len(providers)} records")

    # Deduplicate
    providers, skipped_dupes = deduplicate(providers)
    print(f"  After deduplication: {len(providers)} records ({skipped_dupes} duplicates removed)")

    # Print validation report first (useful even in dry-run)
    print_validation_report(providers)

    if args.dry_run:
        print("DRY RUN — no data will be written to Supabase\n")

    # Connect to Supabase
    if not args.dry_run:
        print("→ Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Ingest
    summary = ingest(providers, supabase, dry_run=args.dry_run)

    # Final summary
    print(f"\n{'='*60}")
    print("INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Total records:    {summary['total']}")
    print(f"  Upserted:         {summary['inserted']}")
    print(f"  Errors:           {summary['errors']}")
    if summary["errors"] > 0:
        print(f"  ⚠  {summary['errors']} records failed — check logs above")
    else:
        print("  ✓ All records ingested successfully")
    print()


if __name__ == "__main__":
    main()
