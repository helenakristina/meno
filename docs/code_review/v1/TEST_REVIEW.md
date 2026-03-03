# Phase 3: Testing & Coverage - Results Report

**Date:** March 2, 2026
**Tests Run:** 189 total
**Overall Coverage:** 76%
**Assessment:** Excellent test suite, clear improvement path for V2

---

## Coverage Summary

**Total Lines:** 1,327
**Lines Tested:** 1,002 (76%)
**Lines Missing:** 325 (24%)

### Pass Rate

- **All 189 tests passed** ✅
- **Execution time:** 20.64 seconds
- **No failures or errors**

---

## Coverage by File

### 100% Coverage (Perfect) ✅

| File                               | Lines | Tests | Notes               |
| ---------------------------------- | ----- | ----- | ------------------- |
| `app/models/chat.py`               | 19    | -     | Data models         |
| `app/models/export.py`             | 5     | -     | Data models         |
| `app/models/providers.py`          | 65    | -     | Data models         |
| `app/models/symptoms.py`           | 54    | -     | Data models         |
| `app/models/users.py`              | 22    | -     | Data models         |
| `app/core/config.py`               | 12    | -     | Settings            |
| `app/core/insurance_normalizer.py` | 5     | 10    | Normalization logic |
| `app/core/supabase.py`             | 7     | -     | Supabase client     |
| `app/llm/system_prompts.py`        | 3     | -     | Constants           |
| `app/services/stats.py`            | 39    | 10    | Pure functions      |
| `app/services/providers.py`        | 61    | 45+   | Pure functions      |

### 85%+ Coverage (Excellent) ✅

| File                         | Lines | Coverage | Missing  | Tests                    | Notes         |
| ---------------------------- | ----- | -------- | -------- | ------------------------ | ------------- |
| `app/api/routes/chat.py`     | 198   | 87%      | 26 lines | 17                       | Main endpoint |
| `app/api/routes/export.py`   | 188   | 86%      | 26 lines | PDF + CSV variants       |
| `app/api/routes/symptoms.py` | 132   | 83%      | 23 lines | 28 tests                 | Logs + stats  |
| `app/api/routes/users.py`    | 70    | 89%      | 8 lines  | Onboarding + preferences |
| `app/main.py`                | 16    | 94%      | 1 line   | Application entry        |
| `app/api/dependencies.py`    | 23    | 91%      | 2 lines  | Auth extraction          |

### 76-82% Coverage (Good) 🟡

| File                          | Lines | Coverage | Missing  | Tests      | Notes              |
| ----------------------------- | ----- | -------- | -------- | ---------- | ------------------ |
| `app/api/routes/providers.py` | 174   | 76%      | 41 lines | 45+        | Search + shortlist |
| `app/services/symptoms.py`    | 17    | 82%      | 3 lines  | Validation |

### Below 50% Coverage (Needs Work) 🔴

| File                   | Lines | Coverage | Missing  | Priority | Notes                           |
| ---------------------- | ----- | -------- | -------- | -------- | ------------------------------- |
| `app/services/llm.py`  | 51    | 22%      | 40 lines | MEDIUM   | Hardcoded client blocks testing |
| `app/rag/retrieval.py` | 68    | 16%      | 57 lines | MEDIUM   | Vector search untested          |
| `app/rag/ingest.py`    | 98    | 0%       | 98 lines | LOW      | Scraper (offline tool)          |

---

## Test Breakdown by Endpoint

### Chat Endpoint Tests (17 tests, 87% coverage)

**File:** `tests/api/routes/test_chat.py`

**What's Tested:**

- ✅ Auth enforcement (requires valid token)
- ✅ Invalid token rejection
- ✅ Empty message validation
- ✅ Happy path (message → response with citations)
- ✅ Citation deduplication
- ✅ Empty citations when no sources
- ✅ New conversation creation
- ✅ 404 for unknown conversation ID
- ✅ RAG failure graceful degradation
- ✅ OpenAI failure handling (500)
- ✅ Missing user profile fallback
- ✅ Missing symptom summary fallback
- ✅ Phantom citation sanitization
- ✅ Section names in citations
- ✅ Multiple phantom citations
- ✅ Plain bracket phantom citations

**What's Missing (26 lines):**

- Some error handling paths
- Logging statement coverage
- Edge cases in citation logic

### Symptoms Endpoint Tests (28 tests, 83% coverage)

**Create Symptom Log:**

- ✅ Create with cards source
- ✅ Create with text source
- ✅ Create with both sources
- ✅ Custom logged_at timestamp
- ✅ Auth enforcement (401)
- ✅ Malformed auth header
- ✅ Invalid token
- ✅ Empty symptoms validation (422)
- ✅ Missing free text validation (422)
- ✅ Invalid source values (422)
- ✅ Invalid symptom IDs (400)

**Get Symptom Logs:**

- ✅ Return 200 with logs list
- ✅ Empty list when no logs
- ✅ Start date filtering
- ✅ End date filtering
- ✅ Date range filtering
- ✅ Custom limit
- ✅ Limit validation (above max, zero)
- ✅ Auth enforcement
- ✅ Invalid date format (422)
- ✅ Ordered newest first
- ✅ Enriches symptom names
- ✅ Fallback for unknown IDs

**Frequency Stats:**

- ✅ Happy path
- ✅ With date range
- ✅ Auth enforcement
- ✅ Invalid dates
- ✅ Date validation (start > end)
- ✅ Empty results
- ✅ Sorted by count

**Co-occurrence Stats:**

- ✅ Happy path
- ✅ Rate calculation
- ✅ Threshold filtering
- ✅ Single-symptom logs ignored
- ✅ Auth enforcement
- ✅ Invalid dates
- ✅ Threshold validation
- ✅ Empty results
- ✅ Sorted by rate
- ✅ Unknown IDs handled

### Providers Endpoint Tests (45+ tests, 76% coverage)

**Search Providers:**

- ✅ Paginated results for state
- ✅ 400 when no state/zip
- ✅ Page size validation (max 50)
- ✅ City exact match
- ✅ City case-insensitive
- ✅ City partial match fallback
- ✅ No results when no match
- ✅ Insurance filter (case-insensitive)
- ✅ Insurance no match (empty)
- ✅ State code normalized to uppercase
- ✅ Pagination (page 2)
- ✅ NAMS certified sorted first
- ✅ Zip code infers state
- ✅ Zip code not found (400)
- ✅ Empty results valid response
- ✅ Insurance normalization

**List States:**

- ✅ States with counts, alphabetically sorted
- ✅ Empty list when no providers
- ✅ Response shape (state + count fields)

**List Insurance Options:**

- ✅ Sorted, deduplicated options
- ✅ Empty list when no insurance
- ✅ Empty list when no providers
- ✅ Alphabetical ordering
- ✅ Commercial → Private normalization
- ✅ Deduplicates after normalization

**Generate Calling Script:**

- ✅ Private insurance with plan
- ✅ Private insurance no plan
- ✅ Medicaid with plan
- ✅ Medicaid plan unknown
- ✅ Medicare with Advantage plan
- ✅ Medicare original (no plan)
- ✅ Self-pay
- ✅ Other insurance type
- ✅ Telehealth flag
- ✅ Blank provider name (400)
- ✅ Invalid insurance type (422)
- ✅ LLM failure (500)

**Shortlist Management:**

- ✅ Get shortlist IDs
- ✅ Empty shortlist
- ✅ Auth enforcement
- ✅ Get full shortlist with provider data
- ✅ Empty list when shortlist empty
- ✅ Entries with notes included
- ✅ Add to shortlist (201)
- ✅ Duplicate prevention (409)
- ✅ Remove from shortlist (204)
- ✅ Not found (404)
- ✅ Update status
- ✅ Update notes
- ✅ Update both status + notes
- ✅ Invalid status (422)

### Export Endpoint Tests (13 tests, 86% coverage)

**PDF Export:**

- ✅ Success
- ✅ Auth required
- ✅ Invalid date range (400)
- ✅ Future end date (400)
- ✅ No data (400)
- ✅ PDF generation with mocked OpenAI
- ✅ Invalid auth token (401)

**CSV Export:**

- ✅ Success
- ✅ Auth required
- ✅ Invalid date range
- ✅ No data
- ✅ Multiple logs
- ✅ Log with no symptoms

### User Endpoint Tests (20 tests, 89% coverage)

**Onboarding:**

- ✅ Success
- ✅ All journey stages
- ✅ Auth required
- ✅ Invalid token
- ✅ Underage rejection
- ✅ Future date rejection
- ✅ Today as DOB rejection
- ✅ Invalid journey stage
- ✅ Duplicate prevention
- ✅ Admin auth failure (500)
- ✅ Missing DOB (422)
- ✅ Missing journey stage (422)

**Insurance Preference:**

- ✅ Get saved preference
- ✅ Nulls when columns not set
- ✅ Nulls when no profile
- ✅ Auth required
- ✅ DB error handling (500)
- ✅ Update successfully
- ✅ Update with null plan name
- ✅ 404 when no profile
- ✅ Invalid insurance type (422)

### Service Tests (20 tests, 100% coverage)

**Stats Service Tests (`test_stats.py`):**

- ✅ Frequency stats sorted descending
- ✅ Name and category resolution
- ✅ Empty logs
- ✅ Logs with no symptoms
- ✅ Unknown symptom IDs omitted
- ✅ Returns SymptomFrequency objects
- ✅ Co-occurrence pairs above threshold
- ✅ Pairs below threshold excluded
- ✅ Threshold = 1
- ✅ Rate calculation (co_count / total_a)
- ✅ Sorted by rate descending
- ✅ Single-symptom logs filtered
- ✅ Empty logs
- ✅ Unknown IDs skipped
- ✅ Capped at MAX_PAIRS
- ✅ Returns SymptomPair objects

**Insurance Normalizer Tests (`test_insurance_normalizer.py`):**

- ✅ Known mapping → canonical
- ✅ Unknown value → original
- ✅ Empty string → empty
- ✅ Case-sensitive match
- ✅ Already canonical unchanged
- ✅ Maps values in list
- ✅ Unknown passes through
- ✅ Empty list
- ✅ Mixed list normalizes
- ✅ Preserves order

### Guardrails Tests (7 tests, specific medical advice boundary)

**File:** `tests/api/routes/test_chat_guardrails.py`

- ✅ Diagnosis request does not diagnose
- ✅ Treatment recommendation does not recommend
- ✅ Prompt injection hard stops
- ✅ Out-of-scope redirects gracefully
- ✅ In-scope question answers fully
- ✅ Misdiagnosis concern handled educationally
- ✅ Dosage question does not provide dosage

---

## What's NOT Tested

### 1. RAG Retrieval (16% coverage, 57 lines missing)

**File:** `app/rag/retrieval.py`

**Missing:**

- Vector similarity search logic
- Caching behavior
- Embedding deduplication
- Chunk filtering

**Why:** Requires mocking embeddings and pgvector operations

**Priority:** MEDIUM (Ask Meno depends on this)

**Effort to fix:** 2-3 hours (mock sentence-transformers/OpenAI embeddings)

### 2. LLM Service (22% coverage, 40 lines missing)

**File:** `app/services/llm.py`

**Missing:**

- `generate_symptom_summary()` tests
- `generate_provider_questions()` tests
- `generate_calling_script()` tests

**Why:** Hardcoded `_client()` prevents dependency injection

**Priority:** MEDIUM (Fixed by V2 refactoring)

**Effort to fix:** 4-6 hours (add DI, then tests become easy)

### 3. Scraper (0% coverage, 98 lines missing)

**File:** `app/rag/ingest.py`

**Why:** Offline tool, not critical path

**Priority:** LOW

**Effort to fix:** 3-4 hours (mock HTTP requests to NCBI/Wikipedia)

### 4. Minor Edge Cases in Routes

Various error paths and logging statements:

- Some 400/422 edge cases
- Some logging statement branches
- Some rarely-hit fallbacks

**Why:** Main paths are covered, these are rarely executed

**Priority:** LOW

**Effort to fix:** 2-3 hours per route

---

## Quality Assessment

### ✅ Strengths

1. **Pure Functions Are Perfect** (stats.py, providers.py)
   - 100% test coverage
   - Good edge case coverage
   - No mocking needed

2. **Routes Are Well-Tested** (83-87% coverage)
   - Auth enforcement thoroughly tested
   - Validation edge cases covered
   - Error cases handled
   - Happy paths verified

3. **Test Organization** is excellent
   - Grouped by test class
   - Descriptive names
   - Clear arrange-act-assert pattern
   - Fixtures for common setup

4. **Guardrails Are Comprehensive** (7 dedicated tests)
   - Medical advice boundary verified
   - Prompt injection tested
   - Out-of-scope handling validated

5. **No Failures** — All 189 tests pass consistently

### 🟡 Areas for V2 Improvement

1. **LLM Service** (22%) — Blocked by hardcoded client
   - Refactor with DI → testing becomes easy
   - 3-4 hours to fix

2. **RAG Retrieval** (16%) — Complex to mock
   - Need sentence-transformers/OpenAI mocks
   - 2-3 hours to add tests

3. **Scraper** (0%) — Lower priority
   - Offline tool
   - Nice to have, not critical

---

## Testing Checklist for V2

**Before Building New Features:**

- [ ] Create repositories (UserRepository, etc.)
- [ ] Add DI to LLM service
- [ ] Test repositories in isolation
- [ ] Extract CitationService + test
- [ ] Mock embeddings for RAG tests
- [ ] Achieve 80%+ coverage on new code

**As You Build V2:**

- [ ] Write tests first (or alongside code)
- [ ] Use pure functions where possible
- [ ] Inject dependencies
- [ ] Test services independently
- [ ] Test routes with mocked services

---

## Recommendations

### High Priority (Do in V2)

1. **Refactor LLM Service with Dependency Injection**
   - **Effort:** 2-3 hours
   - **Benefit:** Enables testing, enables provider switching (OpenAI → Claude)
   - **Impact:** Unlocks LLM testing

2. **Create Repository Layer**
   - **Effort:** 4-6 hours
   - **Benefit:** Decouple from Supabase, reduce code duplication
   - **Impact:** Makes data access testable + swappable

### Medium Priority (Nice to Have in V2)

3. **Mock Embeddings for RAG Tests**
   - **Effort:** 2-3 hours
   - **Benefit:** Increase RAG coverage from 16% to 80%+

4. **Extract CitationService**
   - **Effort:** 1-2 hours
   - **Benefit:** Reusable logic, easier to test

### Low Priority (Defer)

5. **Scraper Tests**
   - **Effort:** 3-4 hours
   - **Benefit:** Nice to have, offline tool not critical path

---

## Conclusion

**Testing quality: 9/10 — Excellent suite with clear path forward**

You have:

- ✅ Solid test coverage (76%)
- ✅ Well-organized tests (189 total)
- ✅ Good practices (descriptive names, edge cases)
- ✅ Clear gaps identified (LLM, RAG, scraper)
- ✅ Refactoring roadmap for V2

**Next steps:** Don't spend more time on testing now. Focus on V2 refactoring (repositories + DI), then testing the gaps becomes much easier.

---
