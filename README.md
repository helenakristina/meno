## Running backend

`uv run uvicorn app.main:app --reload`


git commit -m 'feat: provider directory (search, calling assistant, insurance persistence)

Backend:
- GET /api/providers/search with state/city/zip, provider type, insurance,
  and NAMS filters; paginated with offset/limit
- GET /api/providers/states and /api/providers/insurance-options for
  dynamic filter population
- POST /api/providers/calling-script — LLM-generated personalized calling
  scripts with insurance-type-aware prompt logic (private, Medicare,
  Medicaid MCO, self-pay); no PII sent to LLM
- GET/PATCH /api/users/insurance-preference — persists insurance type and
  plan name to user profile
- Service layer: filtering in Python, prompt assembly as pure function
- 146 tests, all passing

Frontend:
- /providers page with state/city search, filter panel (provider type,
  insurance combobox, NAMS toggle), paginated results, URL param sync
- ProviderCard with NAMS certified badge, tap-to-call, insurance tags
  ("Commercial Insurance" normalized to "Private Insurance")
- CallingScriptModal — three-state flow (form → loading → script),
  insurance type segmented control, Medicaid MCO helper text and
  "I'm not sure" fallback, clipboard copy, tap-to-call from result
- Insurance preference pre-fills on modal open, saves silently on generate
- Skeleton loading states throughout

Database:
- users.insurance_type and users.insurance_plan_name columns
  (migration: add_insurance_to_users.sql)
  '