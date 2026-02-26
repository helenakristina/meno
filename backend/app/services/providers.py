"""Provider search business logic — pure functions, no DB access."""

import math

from app.core.insurance_normalizer import normalize_insurance_list, normalize_insurance_name
from app.models.providers import CallingScriptRequest, InsuranceType, ProviderCard, ProviderSearchResponse


def to_provider_card(row: dict) -> ProviderCard:
    return ProviderCard(
        id=row["id"],
        name=row["name"],
        credentials=row.get("credentials"),
        practice_name=row.get("practice_name"),
        city=row["city"],
        state=row["state"],
        zip_code=row.get("zip_code"),
        phone=row.get("phone"),
        website=row.get("website"),
        nams_certified=bool(row.get("nams_certified")),
        provider_type=row.get("provider_type"),
        specialties=row.get("specialties") or [],
        insurance_accepted=normalize_insurance_list(row.get("insurance_accepted") or []),
        data_source=row.get("data_source"),
        last_verified=row.get("last_verified"),
    )


def filter_and_paginate(
    providers: list[dict],
    *,
    city: str | None,
    insurance: str | None,
    page: int,
    page_size: int,
) -> ProviderSearchResponse:
    """Filter by city and insurance, sort, and paginate provider rows.

    City uses a two-phase strategy: exact match (case-insensitive) first; if
    no results, falls back to substring match. Insurance is a case-insensitive
    substring check against every value in the insurance_accepted array.

    Ordering: NAMS-certified providers first, then alphabetical by name.
    """
    if city:
        normalized = city.strip().lower()
        exact = [
            p for p in providers
            if (p.get("city") or "").strip().lower() == normalized
        ]
        providers = exact if exact else [
            p for p in providers
            if normalized in (p.get("city") or "").strip().lower()
        ]

    if insurance:
        normalized_ins = insurance.strip().lower()
        providers = [
            p for p in providers
            if any(
                normalized_ins in (ins or "").lower()
                for ins in (p.get("insurance_accepted") or [])
            )
        ]

    providers = sorted(
        providers,
        key=lambda p: (0 if p.get("nams_certified") else 1, (p.get("name") or "").lower()),
    )

    total = len(providers)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    offset = (page - 1) * page_size
    page_items = providers[offset : offset + page_size]

    return ProviderSearchResponse(
        providers=[to_provider_card(p) for p in page_items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def aggregate_states(rows: list[dict]) -> list[dict]:
    """Count providers per state, returned sorted by state code."""
    counts: dict[str, int] = {}
    for row in rows:
        state = row.get("state")
        if state:
            counts[state] = counts.get(state, 0) + 1
    return [{"state": s, "count": c} for s, c in sorted(counts.items())]


def collect_insurance_options(rows: list[dict]) -> list[str]:
    """Flatten insurance_accepted arrays, normalize, deduplicate, and sort alphabetically.

    Normalization is applied before deduplication so that transitional DB rows
    containing both the old raw value and the canonical display name collapse
    correctly to a single entry.
    """
    seen: set[str] = set()
    options: list[str] = []
    for row in rows:
        for ins in (row.get("insurance_accepted") or []):
            if ins:
                normalized = normalize_insurance_name(ins)
                if normalized not in seen:
                    seen.add(normalized)
                    options.append(normalized)
    return sorted(options)


def assemble_calling_script_prompts(request: CallingScriptRequest) -> tuple[str, str]:
    """Assemble system and user prompts for calling script generation.

    Pure function — no side effects. Returns a (system_prompt, user_prompt)
    tuple for the LLM call. Insurance block copy varies by insurance type and
    whether a specific plan name is known.
    """
    system_prompt = (
        "You are a helpful assistant writing a short, confident calling script "
        "for a patient who wants to contact a healthcare provider's office. "
        "The patient will read this script to an administrative staff member, "
        "not a clinician. Write in first person, warm but direct. "
        "The script should take under 30 seconds to read aloud. "
        "Return only the script text — no preamble, no label, no quotes."
    )

    plan = (request.insurance_plan_name or "").strip()
    plan_unknown = request.insurance_plan_unknown

    if request.insurance_type == InsuranceType.private:
        if plan and not plan_unknown:
            insurance_block = f"Does the provider accept {plan} insurance?"
        else:
            insurance_block = "What insurance plans does the provider accept?"
    elif request.insurance_type == InsuranceType.medicaid:
        if plan and not plan_unknown:
            insurance_block = (
                f"Does the provider accept {plan} — that is a Medicaid managed "
                f"care plan. If not, can you tell me which Medicaid plans you do "
                f"accept so I can confirm my coverage?"
            )
        else:
            insurance_block = (
                "I am on Medicaid. Can you tell me which specific Medicaid plans "
                "the provider accepts, including which managed care organizations "
                "or MCOs they are contracted with?"
            )
    elif request.insurance_type == InsuranceType.medicare:
        if plan and not plan_unknown:
            insurance_block = (
                f"Does the provider accept {plan}? That is a Medicare Advantage "
                f"plan. If not, can you tell me which Medicare plans you accept?"
            )
        else:
            insurance_block = (
                "Does the provider accept Medicare? I want to confirm whether they "
                "accept original Medicare and/or Medicare Advantage plans."
            )
    elif request.insurance_type == InsuranceType.self_pay:
        insurance_block = (
            "Does the provider offer self-pay rates, and is there a new patient "
            "consultation fee?"
        )
    else:  # other
        insurance_block = "What insurance plans does the provider accept?"

    telehealth_line = ""
    if request.interested_in_telehealth:
        telehealth_line = "\n4. Does the provider offer telehealth appointments?"

    user_prompt = (
        f"Write a calling script for a patient contacting {request.provider_name}'s office.\n"
        "They want to know:\n"
        "1. Is the provider currently accepting new patients?\n"
        f"2. {insurance_block}\n"
        f"3. Approximately how long is the wait for a new patient appointment?"
        f"{telehealth_line}\n"
        "Finally, I want to confirm that the provider regularly sees patients "
        "for perimenopause and menopause management — is that something they "
        "actively focus on?"
    )

    return system_prompt, user_prompt
