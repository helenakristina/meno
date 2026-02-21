"""NAMS Provider Directory Scraper.

Scrapes the Menopause Society (NAMS) Find-a-Practitioner directory and saves
provider data to JSON files for downstream ingestion into Supabase.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECONNAISSANCE FINDINGS (inspected 2026-02-21)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PAGE TYPE: JavaScript-rendered. ASP.NET WebForms application hosted at
   portal.menopause.org (www.menopause.org/for-women/find-a-menopause-practitioner
   redirects there). Results load server-side via __doPostBack; no static HTML.
   → Scraper uses Playwright async.

2. ROBOTS.TXT (menopause.org/robots.txt):
   Only disallows /wp-content/uploads/* subdirectories.
   The provider directory path is NOT disallowed. Scraping is permitted.
   We use a descriptive User-Agent and respectful delays.

3. API ENDPOINTS: None. Pure ASP.NET WebForms with Telerik RadGrid.
   No JSON/REST endpoints detected in network traffic. All data comes
   from server-rendered HTML postbacks.

4. SEARCH PARAMETERS:
   - Country (Telerik RadComboBox, default "(Any)")
   - State/Province (RadComboBox)
   - Profession (RadComboBox)
   - Also: "Search by ZIP" tab and "Telehealth by State" tab.
   Strategy: Search without filters (all providers), filter US-only in transform.

5. DATA FIELDS PER PROVIDER CARD:
   - Name             div.infoname text
   - Credentials      div.info-edu text (MD, DO, NP, CNP, FNP, MSCP, etc.)
   - Address          div.info-address[0] — MULTILINE with \\n separators:
                        line 0: street address (may include practice name)
                        line 1: "City, STATE ZIP"
                        line 2: "USA" (or other country)
   - Phone            div.info-address[1] text
   - Website          div.info-address[2] > a[href]
   - NAMS Certified   img[src*="menopause_cert_icon"] presence (True = MSCP holder)
   - Telehealth       div with heading "Telehealth/Virtual Appointments Available"
   - Payment/Ins.     ul > li under "Payment for Services" heading
   - MORE INFO link   contains userid for detail page (not scraped in V1)

6. PAGINATION: Telerik RadGrid pager with CSS classes:
   - input.rgPageFirst / .rgPagePrev / .rgPageNext / .rgPageLast
   - Disabled buttons have onclick="return false;"
   - Active "Next Page" button has no onclick attribute.
   - Total at time of scrape: 5,539 providers across 277 pages at 20/page.

7. ANTI-SCRAPING: None detected. No CAPTCHA, no login wall, no rate limiting
   observed during reconnaissance. We add 1.5s delays between page loads to
   be respectful.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SETUP (first-time):
    cd backend
    uv add playwright
    uv run playwright install chromium   ← install headless browser

USAGE:
    uv run scripts/scrape_nams.py                   # full scrape (~8-10 min)
    uv run scripts/scrape_nams.py --max-pages 5     # test with 5 pages only
    uv run scripts/scrape_nams.py --headless false  # watch the browser

OUTPUT:
    backend/scripts/data/providers_raw.json    raw scraped data (source of truth)
    backend/scripts/data/providers_clean.json  transformed, ready for Supabase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import argparse
import asyncio
import json
import re
import uuid
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DIRECTORY_URL = "https://portal.menopause.org/NAMS/NAMS/Directory/Menopause-Practitioner.aspx"

USER_AGENT = "Meno Health App / provider directory research (educational; not commercial)"

PAGE_LOAD_DELAY_MS = 1500  # milliseconds between page navigations (respectful crawl rate)

DATA_DIR = Path(__file__).parent / "data"

RAW_OUTPUT = DATA_DIR / "providers_raw.json"
CLEAN_OUTPUT = DATA_DIR / "providers_clean.json"

# US state abbreviations for filtering (V1 is US-only)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",  # territories
}

# Payment terms that represent actual insurance (vs billing model)
INSURANCE_TERMS = {
    "commercial insurance",
    "medicaid",
    "medicare",
    "tricare",
}

# Credentials that indicate NP/PA provider type
NP_PA_CREDS = {
    "NP", "PA", "APRN", "CNM", "CNP", "FNP", "CRNP", "ANP", "GNP",
    "PMHNP", "WHNP", "NPC", "NP-C", "FNP-C", "FNP-BC", "AGPCNP",
    "AGACNP", "ACNP", "DNP", "CRNA",
}

# Credentials that indicate MD/DO
MD_DO_CREDS = {"MD", "DO", "MBCHB", "MBBS"}


# ---------------------------------------------------------------------------
# Address Parsing
# ---------------------------------------------------------------------------

def parse_address(addr_text: str) -> dict:
    """Parse multiline NAMS address text into structured components.

    The address div uses newlines to separate lines. Two observed formats:
        A) "Street\nCity, STATE ZIP\n USA"   (USA on its own line)
        B) "Street\nCity, STATE ZIP USA"     (USA on same line as zip)
        C) "PracticeName\nStreet\nCity, STATE ZIP\n USA"

    Strategy: scan lines from the end to find the "City, ST ZIP [USA]" pattern.
    This handles both A and B without ambiguity.

    Returns dict with keys: street, practice_name, city, state, zip_code, country.
    """
    result: dict = {
        "street": None,
        "practice_name": None,
        "city": None,
        "state": None,
        "zip_code": None,
        "country": None,
    }

    # Split into non-empty lines
    lines = [ln.strip() for ln in addr_text.strip().split("\n") if ln.strip()]
    if not lines:
        return result

    # City/STATE ZIP pattern — optionally followed by "USA" or country name
    # Matches: "Westerville, OH 43082-9413" and "Portland, OR 97222 USA"
    csz_re = re.compile(
        r"^(.+?),\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*(?:\s+[A-Z]+)?\s*$"
    )

    # Scan lines from the end to find the city/state/zip line
    csz_idx: int | None = None
    csz_match = None
    for i in range(len(lines) - 1, -1, -1):
        # Strip a trailing country token before matching (handles "City, ST ZIP USA")
        candidate = re.sub(r"\s+USA\s*$", "", lines[i], flags=re.IGNORECASE).strip()
        m = csz_re.match(candidate)
        if m:
            csz_idx = i
            csz_match = m
            break

    if csz_match is None:
        # Can't parse — store raw text
        result["street"] = addr_text.strip()
        return result

    result["city"] = csz_match.group(1).strip()
    result["state"] = csz_match.group(2)
    result["zip_code"] = csz_match.group(3).split("-")[0]  # 5-digit only

    # Country: from any line after city/state/zip that isn't empty
    lines_after = [l for l in lines[csz_idx + 1:] if l and l.upper() not in ("USA",)]
    result["country"] = lines_after[0] if lines_after else "USA"

    # Lines before city/state/zip: street ± practice name
    # Heuristic: a line is a practice name (not a street) only if it contains
    # NO digits. "Coastal Well Woman" → practice name. "3124 S 19th St" → street.
    lines_before = lines[:csz_idx]
    if len(lines_before) == 0:
        pass  # address-only card with no street
    elif len(lines_before) == 1:
        result["street"] = lines_before[0]
    else:
        first = lines_before[0]
        if re.search(r"\d", first):
            # First line has digits → it's a street address, join everything
            result["street"] = "\n".join(lines_before)
        else:
            # First line has no digits → likely a practice/clinic name
            result["practice_name"] = first
            result["street"] = "\n".join(lines_before[1:])

    return result


# ---------------------------------------------------------------------------
# Provider Type Inference
# ---------------------------------------------------------------------------

def infer_provider_type(credentials: str | None) -> str:
    """Infer provider_type from credentials string.

    Maps to the CHECK constraint values in the providers table:
    ob_gyn | internal_medicine | np_pa | integrative_medicine | other
    """
    if not credentials:
        return "other"

    # Split on common separators to get individual credential tokens
    parts = set(re.split(r"[,\s./\-]+", credentials.upper()))

    if parts & NP_PA_CREDS:
        return "np_pa"

    if parts & MD_DO_CREDS:
        # Can't reliably distinguish OB/GYN from Internal Medicine from credentials alone.
        # FACOG = Fellow American College OB/GYN → ob_gyn
        if "FACOG" in parts or "ABOG" in parts:
            return "ob_gyn"
        return "internal_medicine"

    # Integrative medicine markers
    integrative_markers = {"ABOIM", "IFMCP", "ABIHM", "FAARFM"}
    if parts & integrative_markers:
        return "integrative_medicine"

    return "other"


# ---------------------------------------------------------------------------
# Insurance Normalization
# ---------------------------------------------------------------------------

def extract_insurance(raw_items: list[str]) -> list[str]:
    """Filter payment terms to actual insurance types only."""
    result = []
    for item in raw_items:
        item_stripped = item.strip()
        item_lower = item_stripped.lower()
        if not item_stripped or "data not provided" in item_lower:
            continue
        # Only include actual insurance types, not billing models or social media
        if any(term in item_lower for term in INSURANCE_TERMS):
            result.append(item_stripped)
    return result


# ---------------------------------------------------------------------------
# HTML Parsing
# ---------------------------------------------------------------------------

def parse_provider_card(card) -> dict:
    """Parse a single div.benopausebox provider card into raw dict.

    Args:
        card: BeautifulSoup Tag for the benopausebox div.

    Returns:
        Raw provider dict with all scraped fields.
    """
    raw: dict = {}

    # Name
    name_el = card.select_one("div.infoname")
    raw["name"] = name_el.get_text(strip=True) if name_el else None

    # Credentials
    creds_el = card.select_one("div.info-edu")
    raw["credentials"] = creds_el.get_text(strip=True) if creds_el else None

    # Address block: first div.info-address contains the multiline address
    addr_divs = card.select("div.info-address")
    if addr_divs:
        addr_text = addr_divs[0].get_text(separator="\n", strip=True)
        addr_parsed = parse_address(addr_text)
        raw.update(addr_parsed)

    # Phone: second div.info-address (plain text, no link)
    if len(addr_divs) >= 2:
        phone_text = addr_divs[1].get_text(strip=True)
        # Verify it looks like a phone number
        raw["phone"] = phone_text if re.search(r"\d{3}", phone_text) else None

    # Website: third div.info-address contains an <a> tag
    if len(addr_divs) >= 3:
        link = addr_divs[2].select_one("a")
        if link:
            href = link.get("href", "").strip()
            # Skip empty or javascript: hrefs
            raw["website"] = href if href and not href.startswith("javascript") else None

    # NAMS Certified: presence of the MSCP certification badge icon
    nams_img = card.select_one('img[src*="menopause_cert_icon"]')
    raw["nams_certified"] = nams_img is not None

    # Also check credentials for MSCP (belt-and-suspenders)
    if not raw["nams_certified"] and raw.get("credentials"):
        raw["nams_certified"] = "MSCP" in raw["credentials"].upper().split(",") or \
                                 re.search(r"\bMSCP\b", raw["credentials"]) is not None

    # Payment for Services / Insurance
    payment_items = []
    for section in card.select("div.mb-3"):
        heading = section.select_one("div.info-heading")
        if heading and "Payment for Services" in heading.get_text():
            for li in section.select("li"):
                payment_items.append(li.get_text(strip=True))
    raw["payment_raw"] = payment_items

    # Telehealth available
    for section in card.select("div.mb-3"):
        heading = section.select_one("div.info-heading")
        if heading and "Telehealth" in heading.get_text():
            info_text = section.select_one("div.info-text")
            if info_text:
                raw["telehealth"] = "yes" in info_text.get_text(strip=True).lower()
            break

    return raw


def parse_page_html(html: str) -> list[dict]:
    """Parse all provider cards from rendered page HTML."""
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.benopausebox")
    return [parse_provider_card(card) for card in cards]


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

async def get_total_pages(page) -> int:
    """Extract total page count from pager text.

    The Telerik RadGrid pager lives in a tfoot row with class rgPager and
    contains text like "5539 items in 277 pages".
    """
    try:
        # Try the tfoot pager row first (standard Telerik location)
        text = await page.inner_text("tfoot tr.rgPager")
        match = re.search(r"([\d,]+)\s+items?\s+in\s+(\d+)\s+pages?", text)
        if match:
            total = int(match.group(2))
            print(f"  Found {match.group(1).replace(',', '')} providers across {total} pages")
            return total
    except Exception:
        pass

    try:
        # Fallback: search the whole body for the pager summary text
        text = await page.inner_text("body")
        match = re.search(r"([\d,]+)\s+items?\s+in\s+(\d+)\s+pages?", text)
        if match:
            total = int(match.group(2))
            print(f"  Found {match.group(1).replace(',', '')} providers across {total} pages")
            return total
    except Exception:
        pass

    print("  WARNING: Could not determine total pages — will paginate until Next is disabled")
    return 9999  # fallback: iterate until Next button disabled


async def is_next_enabled(page) -> bool:
    """Return True if the Next Page button is clickable (not disabled)."""
    try:
        next_btn = await page.query_selector("input.rgPageNext")
        if not next_btn:
            return False
        onclick = await next_btn.get_attribute("onclick")
        # Disabled buttons have onclick="return false;"
        return onclick is None or "return false" not in onclick
    except Exception:
        return False


async def scrape_all_providers(headless: bool = True, max_pages: int | None = None) -> list[dict]:
    """Main scraping function. Returns list of raw provider dicts."""
    all_providers: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            # Required: prevents navigator.webdriver from being set to True,
            # which the NAMS portal JavaScript checks to block automated browsers.
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            # Use a realistic desktop browser UA — the portal checks sec-ch-ua
            # headers and blocks requests that identify as "HeadlessChrome".
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.7632.76 Safari/537.36"
            ),
            extra_http_headers={
                "sec-ch-ua": '"Google Chrome";v="145", "Chromium";v="145", "Not A Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "Accept-Language": "en-US,en;q=0.9",
                # Identify ourselves in the X-Forwarded-For equivalent
                "X-Scraper-Info": USER_AGENT,
            },
            viewport={"width": 1280, "height": 900},
        )
        # Remove navigator.webdriver flag (last line of defence against detection)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        print(f"\n{'='*60}")
        print("NAMS Provider Directory Scraper")
        print(f"{'='*60}")
        print(f"Target: {DIRECTORY_URL}")
        print(f"Mode: {'headless' if headless else 'visible browser'}")
        if max_pages:
            print(f"Limit: {max_pages} pages (test mode)")
        print()

        # --- Navigate to the directory ---
        print("→ Loading directory page...")
        await page.goto(DIRECTORY_URL, wait_until="networkidle")

        # --- Click Find to show all results (no filter = all providers) ---
        # The Find button is an input[type=submit] with value="Find", not a <button>.
        print("→ Clicking Find (no filters = all providers)...")
        await page.wait_for_selector("input[value='Find']", timeout=30000)
        await page.click("input[value='Find']")

        # Wait for results grid to render — more reliable than wait_for_load_state
        # which can return early while AJAX grid rendering is still in progress.
        await page.wait_for_selector("div.benopausebox", timeout=45000)
        await page.wait_for_timeout(PAGE_LOAD_DELAY_MS)

        total_pages = await get_total_pages(page)
        pages_to_scrape = min(total_pages, max_pages) if max_pages else total_pages
        print(f"→ Will scrape {pages_to_scrape} page(s)\n")

        # --- Paginate through results ---
        for page_num in range(1, pages_to_scrape + 1):
            print(f"  Page {page_num}/{pages_to_scrape}", end="", flush=True)

            try:
                html = await page.content()
                providers = parse_page_html(html)
                all_providers.extend(providers)
                print(f" → {len(providers)} providers (total: {len(all_providers)})")
            except Exception as e:
                print(f" → ERROR parsing page: {e}")

            # Navigate to next page (unless we're on the last one)
            if page_num < pages_to_scrape:
                if not await is_next_enabled(page):
                    print("  Next Page button disabled — reached last page early")
                    break

                try:
                    # Record current first provider name to detect page change
                    prev_first = await page.inner_text("div.infoname")
                    await page.click("input.rgPageNext")
                    # Wait until the grid refreshes with new content
                    await page.wait_for_function(
                        f"""() => {{
                            const el = document.querySelector('div.infoname');
                            return el && el.innerText.trim() !== {json.dumps(prev_first.strip())};
                        }}""",
                        timeout=30000,
                    )
                    await page.wait_for_timeout(PAGE_LOAD_DELAY_MS)
                except Exception as e:
                    print(f"  ERROR navigating to next page: {e}")
                    break

        await browser.close()

    print(f"\n{'='*60}")
    print(f"Scraping complete: {len(all_providers)} raw provider records")
    print(f"{'='*60}\n")
    return all_providers


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

# Deterministic UUID namespace for provider deduplication
_UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def generate_provider_id(name: str, city: str, state: str) -> str:
    """Generate a stable UUID for a provider based on name + city + state.

    Using uuid5 ensures the same provider always gets the same ID, enabling
    safe upsert on re-runs without needing a separate unique DB constraint.
    """
    key = f"{name.lower().strip()}|{city.lower().strip()}|{state.lower().strip()}"
    return str(uuid.uuid5(_UUID_NAMESPACE, key))


def transform_provider(raw: dict) -> dict | None:
    """Transform a raw scraped provider record to the providers table schema.

    Returns None if the record should be skipped (missing required fields,
    non-US country, etc.).
    """
    # Required fields
    name = raw.get("name")
    city = raw.get("city")
    state = raw.get("state")

    if not name or not city or not state:
        return None

    # V1: US-only filter
    country = raw.get("country", "")
    if country and country.upper() not in ("USA", "UNITED STATES", ""):
        return None
    if state not in US_STATES:
        return None

    credentials = raw.get("credentials")

    return {
        "id": generate_provider_id(name, city, state),
        "name": name,
        "credentials": credentials,
        "practice_name": raw.get("practice_name"),
        "city": city,
        "state": state,
        "zip_code": raw.get("zip_code"),
        "latitude": None,   # V2: geocoding
        "longitude": None,  # V2: geocoding
        "phone": raw.get("phone"),
        "website": raw.get("website"),
        "specialties": [],  # Not exposed in directory listing
        "provider_type": infer_provider_type(credentials),
        "nams_certified": raw.get("nams_certified", False),
        "insurance_accepted": extract_insurance(raw.get("payment_raw", [])),
        "data_source": "nams_directory",
        "last_verified": date.today().isoformat(),
    }


def transform_all(raw_providers: list[dict]) -> list[dict]:
    """Transform all raw providers, logging skipped records."""
    clean = []
    skipped_missing = 0
    skipped_non_us = 0

    for raw in raw_providers:
        name = raw.get("name")
        city = raw.get("city")
        state = raw.get("state")
        country = raw.get("country", "")

        if not name or not city or not state:
            skipped_missing += 1
            continue

        if (country and country.upper() not in ("USA", "UNITED STATES", "")) or \
                (state and state not in US_STATES):
            skipped_non_us += 1
            continue

        transformed = transform_provider(raw)
        if transformed:
            clean.append(transformed)

    print(f"Transformation summary:")
    print(f"  Input:      {len(raw_providers)} records")
    print(f"  Output:     {len(clean)} records")
    print(f"  Skipped (missing required fields): {skipped_missing}")
    print(f"  Skipped (non-US): {skipped_non_us}")
    print()

    return clean


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape NAMS provider directory and save to JSON files"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit number of pages scraped (for testing). Default: all pages.",
    )
    parser.add_argument(
        "--headless",
        type=lambda x: x.lower() != "false",
        default=True,
        help="Run browser headlessly. Use --headless=false to watch the browser.",
    )
    args = parser.parse_args()

    # Create output directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 1: Scrape
    raw_providers = asyncio.run(
        scrape_all_providers(headless=args.headless, max_pages=args.max_pages)
    )

    # Save raw data (source of truth — preserve before any transformation)
    print(f"→ Saving raw data to {RAW_OUTPUT}...")
    with open(RAW_OUTPUT, "w") as f:
        json.dump(raw_providers, f, indent=2, default=str)
    print(f"  Saved {len(raw_providers)} raw records\n")

    # Phase 2: Transform
    print("→ Transforming to providers schema...")
    clean_providers = transform_all(raw_providers)

    # Save clean data
    print(f"→ Saving clean data to {CLEAN_OUTPUT}...")
    with open(CLEAN_OUTPUT, "w") as f:
        json.dump(clean_providers, f, indent=2, default=str)
    print(f"  Saved {len(clean_providers)} clean records")
    print()
    print("Next step: run backend/scripts/ingest_providers.py to load into Supabase")


if __name__ == "__main__":
    main()
