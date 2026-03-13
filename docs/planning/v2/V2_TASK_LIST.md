# V2 Implementation Task List

**Timeline:** 8-13 weeks full-time
**Status:** Ready to start
**Last Updated:** March 2, 2026

---

## Phase 1: Refactor & Foundation (Weeks 1-2)

This must be done first. Everything in V2 depends on it.

### 1.1: Create Repository Layer

**Purpose:** Abstract database access, decouple from Supabase, enable testing

#### Task 1.1.1: Create User Repository

- **File:** `backend/app/repositories/user_repository.py`
- **What it does:**
  - `get_context(user_id)` → returns journey_stage, age
  - `get_profile(user_id)` → returns full user profile
  - `update_profile(user_id, data)` → updates user profile
- **Tests:** Create `backend/tests/repositories/test_user_repository.py`
- **Effort:** 3 hours
- **Checklist:**
  - [x] UserRepository class created
  - [x] Methods take AsyncClient as dependency
  - [x] User Supabase queries moved from chat route
  - [x] Tests pass (mock Supabase)
  - [x] Chat route updated to use repository

#### Task 1.1.2: Create Symptoms Repository

- **File:** `backend/app/repositories/symptoms_repository.py`
- **What it does:**
  - `get_summary(user_id)` → cached symptom summary
  - `validate_ids(ids)` → validate symptom IDs exist
  - `get_logs(user_id, start_date, end_date)` → fetch logs
  - `create_log(user_id, data)` → create new log
- **Tests:** Create `backend/tests/repositories/test_symptoms_repository.py`
- **Effort:** 3 hours
- **Checklist:**
  - [x] SymptomsRepository class created
  - [x] Move `_fetch_symptom_summary()` from chat route
  - [x] Move validation logic from symptoms.py
  - [x] Move log fetching logic from symptoms route
  - [x] Tests pass
  - [x] Routes updated to use repository

#### Task 1.1.3: Create Conversation Repository

- **File:** `backend/app/repositories/conversation_repository.py`
- **What it does:**
  - `load(conversation_id, user_id)` → fetch messages
  - `save(conversation_id, user_id, messages)` → upsert conversation
  - `delete(conversation_id, user_id)` → delete conversation
- **Tests:** Create `backend/tests/repositories/test_conversation_repository.py`
- **Effort:** 2 hours
- **Checklist:**
  - [x] ConversationRepository class created
  - [x] Move `_load_conversation()` from chat route
  - [x] Move `_save_conversation()` from chat route
  - [x] Tests pass
  - [x] Chat route updated to use repository

#### Task 1.1.4: Claude Code creates plan for refactoring rest of routes to use repositories for data fetches.

1. Phase 1 (ProvidersRepository): Start immediately? (HIGH PRIORITY)
2. Phase 2 (Stats extension): Start after Phase 1? (RECOMMENDED)
3. Phase 3 (Export extension): Include in scope or defer? (OPTIONAL)

### 1.2: Refactor LLM Service with Dependency Injection

**Purpose:** Enable testing, enable provider switching (OpenAI → Claude)

#### Task 1.2.1: Create LLM Provider Abstraction

- **File:** `backend/app/services/llm_base.py`
- **What it does:**
  - `LLMProvider` base class
  - `chat_completion(system_prompt, user_prompt, max_tokens, temperature)` → str
- **Effort:** 1 hour
- **Checklist:**
  - [x] Base class created
  - [x] Abstract method defined

#### Task 1.2.2: Create OpenAI Provider Implementation

- **File:** `backend/app/services/openai_provider.py`
- **What it does:**
  - Implement `LLMProvider` using OpenAI API
  - Accept AsyncOpenAI client in `__init__`
- **Effort:** 1 hour
- **Checklist:**
  - [x] OpenAIProvider class created
  - [x] Takes `client` in constructor
  - [x] Implements `chat_completion()`
  - [x] Tests pass

#### Task 1.2.3: Refactor `llm.py` to Use Dependency Injection

- **File:** `backend/app/services/llm.py` (modify existing)
- **What it does:**
  - `LLMService` class instead of functions
  - Takes `LLMProvider` in constructor
  - Keep `generate_symptom_summary()`, `generate_provider_questions()`, `generate_calling_script()` as methods
- **Tests:** Expand `backend/tests/services/test_llm.py`
- **Effort:** 3 hours
- **Checklist:**
  - [x] LLMService class created
  - [x] Methods refactored to use `self.provider`
  - [x] Remove hardcoded `_client()` function
  - [x] Consolidate duplicate code (3 functions doing similar things)
  - [x] Tests updated to inject mock provider
  - [x] Coverage increases from 22% to 70%+

#### Task 1.2.4: Update Dependency Injection in Routes

- **File:** `backend/app/api/dependencies.py` or `backend/app/main.py`
- **What it does:**
  - Create provider based on settings
  - Inject LLMService into routes
- **Effort:** 2 hours
- **Checklist:**
  - [x] Create `get_llm_service()` dependency
  - [x] Routes use dependency injection
  - [x] Settings updated (LLM_PROVIDER env var)
  - [x] Tests pass
  - [x] Can switch providers via env var

### 1.3: Extract Citation Service

**Purpose:** Reusable citation logic, testable in isolation

#### Task 1.3.1: Create CitationService

- **File:** `backend/app/services/citations.py`
- **What it does:**
  - `sanitize_and_renumber(text, max_sources)` → (cleaned_text, removed_indices)
  - `extract(text, chunks)` → list[Citation]
- **Tests:** Create `backend/tests/services/test_citations.py`
- **Effort:** 2 hours
- **Checklist:**
  - [x] CitationService class created
  - [x] Move `_sanitize_and_renumber_citations()` from chat route
  - [x] Move `_extract_citations()` from chat route
  - [x] Tests pass (lots of regex edge cases to cover)
  - [x] Chat route updated to use service

#### Task 1.3.2: Add Tests for Citation Edge Cases

- **File:** `backend/tests/services/test_citations.py`
- **What it does:**
  - Test phantom citation removal
  - Test renumbering
  - Test extraction with various formats
- **Effort:** 2 hours
- **Checklist:**
  - [x] Happy path tests
  - [x] Edge cases (no citations, all phantoms, mixed formats)
  - [x] 95%+ coverage on CitationService

### 1.4: Verify Refactoring Doesn't Break Anything

#### Task 1.4.1: Run Full Test Suite

- **Command:** `pytest --cov=app -v`
- **Expected:** All 189 existing tests pass + new tests pass
- **Effort:** 1 hour (troubleshooting if failures)
- **Checklist:**
  - [x] All existing tests pass
  - [x] New tests pass
  - [x] Coverage maintained or improved
  - [x] No regressions in chat, symptoms, providers endpoints

#### Task 1.4.2: Manual Testing

- **What it does:**
  - Test chat endpoint manually (logs a message, gets response)
  - Test symptom logging
  - Test provider search
  - Verify nothing broken
- **Effort:** 1 hour
- **Checklist:**
  - [x] Chat works
  - [x] Symptoms work
  - [x] Providers work
  - [x] All existing features unchanged

#### Task 1.4.3: Commit Refactored Code

- **Commit message:** "refactor: add repositories, DI for LLM, extract CitationService"
- **Effort:** 15 min
- **Checklist:**
  - [x] Code committed
  - [x] Tests passing
  - [x] Ready for V2 features

---

## Phase 1.5 Code review and refactor front end

- **Artifacts**
  - docs/code_review/v1/frontend/ASK_MENO.md
  - docs/code_review/v1/frontend/TYPE_SAFETY_SUMMARY.md
  - docs/code_review/v1/frontend/FRONTEND_CODE_REVIEW_START.md
  - docs/dev/frontend/V2CODE_EXAMPLES.md

## Phase 2: Appointment Prep (Weeks 3-8)

This is the flagship V2 feature. Build it great.

### 2.1: Data Model & Database Schema

#### Task 2.1.1: Design Appointment Prep Data Model

- **What to define:**
  - AppointmentContext (appointment_type, goal, dismissed_before)
  - AppointmentPrep (context, narrative, concerns, scenarios, outputs)
  - ProviderSummary (content, generated_at)
  - PersonalCheatSheet (content, generated_at)
- **Files:** `backend/app/models/appointment.py`
- **Effort:** 1 hour
- **Checklist:**
  - [x] Models created in Pydantic
  - [x] Type hints complete
  - [x] Docstrings explain each field

#### Task 2.1.2: Create Database Tables

- **Migration file:** `backend/app/migrations/add_appointment_prep_tables.sql`
- **Tables:**
  - `appointment_prep_contexts` — store user selections (appointment type, goal, etc.)
  - `appointment_prep_outputs` — store generated summaries (PDFs as text or links)
- **Effort:** 1 hour
- **Checklist:**
  - [x] Migration file created
  - [x] RLS policies added (users only see their own)
  - [x] Migration tested locally

#### Task 2.1.3: Create AppointmentRepository

- **File:** `backend/app/repositories/appointment_repository.py`
- **What it does:**
  - `save_context(user_id, context)` → saves user selections
  - `save_outputs(user_id, provider_summary, cheat_sheet)` → saves generated docs
  - `get_latest(user_id)` → fetches most recent prep
- **Tests:** Create `backend/tests/repositories/test_appointment_repository.py`
- **Effort:** 2 hours
- **Checklist:**
  - [x] Repository class created
  - [x] CRUD operations work
  - [x] Tests pass

### 2.2: Build Step-by-Step Flow

#### Task 2.2.1: Step 1 — Context Questions API

- **Endpoint:** `POST /api/appointment-prep/context`
- **Input:** appointment_type, goal, dismissed_before
- **Output:** Confirmation + preview of next step
- **File:** `backend/app/api/routes/appointment.py`
- **Effort:** 2 hours
- **Checklist:**
  - [x] Endpoint created
  - [x] Validates inputs (enum values for type/goal/dismissed)
  - [x] Saves context to database
  - [x] Tests pass

#### Task 2.2.2: Step 2 — Data Story API

- **Endpoint:** `POST /api/appointment-prep/narrative`
- **Input:** appointment_prep_id, days_back (default 60)
- **Output:** LLM-generated narrative summary
- **What it does:**
  - Fetch symptom logs from last N days
  - Calculate frequency/cooccurrence stats
  - Call LLMService to write narrative
  - Save narrative
  - Return for user to review/edit
- **File:** `backend/app/api/routes/appointment.py`
- **Effort:** 4 hours
- **Checklist:**
  - [x] Endpoint created
  - [x] Calls SymptomsRepository to get logs
  - [x] Calls stats service to calculate patterns
  - [x] Calls LLMService to write narrative
  - [x] Handles edge cases (no logs, no patterns)
  - [x] Tests pass

#### Task 2.2.3: Step 3 — Prioritize Concerns API

- **Endpoint:** `PUT /api/appointment-prep/{id}/prioritize`
- **Input:** ordered list of symptom IDs + any custom concerns
- **Output:** Saves prioritization
- **File:** `backend/app/api/routes/appointment.py`
- **Effort:** 2 hours
- **Checklist:**
  - [x] Endpoint accepts ordered list
  - [x] Saves order to database
  - [x] Returns ordered concerns
  - [x] Tests pass

#### Task 2.2.4: Step 4 — Scenario Generation API

- **Endpoint:** `POST /api/appointment-prep/{id}/scenarios`
- **Input:** (uses context + symptom profile from database)
- **Output:** Array of scenario cards with suggestions
- **What it does:**
  - Select relevant dismissal scenarios based on goal + symptoms
  - Call LLMService to generate responses
  - Return scenarios for user review
- **File:** `backend/app/api/routes/appointment.py`
- **Effort:** 4 hours
- **Checklist:**
  - [x] Endpoint created
  - [x] Selects scenarios based on appointment goal
  - [x] Calls LLMService for each scenario
  - [x] Handles edge cases (no matching scenarios)
  - [x] Tests pass

#### Task 2.2.5: Step 5 — Generate Output PDFs

- **Endpoint:** `POST /api/appointment-prep/{id}/generate`
- **Output:** Two PDFs (provider summary + personal cheat sheet)
- **What it does:**
  - Assemble provider summary (clinical data only)
  - Assemble cheat sheet (priorities + conversation anchors)
  - Generate PDFs
  - Return download links
- **File:** `backend/app/api/routes/appointment.py`
- **Effort:** 5 hours (PDF generation is fiddly)
- **Checklist:**
  - [x] Endpoint created
  - [x] Provider summary PDF generated (clean clinical styling)
  - [x] Cheat sheet PDF generated (printable, mobile-friendly)
  - [x] PDFs stored (S3 or Supabase storage)
  - [x] Tests pass

### 2.3: Frontend for Appointment Prep

#### Task 2.3.1: Create Appointment Prep Route & Layout

- **Files:**
  - `frontend/src/routes/(app)/appointment-prep/+page.svelte`
  - `frontend/src/routes/(app)/appointment-prep/+layout.svelte`
- **What it shows:** Step indicator, progress, current step
- **Effort:** 2 hours
- **Checklist:**
  - [x] Route created
  - [x] Step indicator (1/5, 2/5, etc.)
  - [x] Progress visualization
  - [x] Responsive on mobile

#### Task 2.3.2: Build Step 1 Component (Context Questions)

- **File:** `frontend/src/routes/(app)/appointment-prep/Step1.svelte`
- **What it shows:**
  - Radio button: appointment type
  - Radio button: goal
  - Radio button: dismissed before
  - Next button
- **Effort:** 2 hours
- **Checklist:**
  - [x] Component created
  - [x] Form validation
  - [x] Calls API
  - [x] Shows loading/error states
  - [x] Navigates to step 2

#### Task 2.3.3: Build Step 2 Component (Review Narrative)

- **File:** `frontend/src/routes/(app)/appointment-prep/Step2.svelte`
- **What it shows:**
  - Generated narrative
  - Edit button (text is editable)
  - Save changes
  - Next button
- **Effort:** 2 hours
- **Checklist:**
  - [x] Component created
  - [x] Shows generated narrative
  - [x] User can edit text
  - [x] Save button persists changes
  - [x] Next button moves to step 3

#### Task 2.3.4: Build Step 3 Component (Prioritize Concerns)

- **File:** `frontend/src/routes/(app)/appointment-prep/Step3.svelte`
- **What it shows:**
  - Drag-and-drop list of symptoms
  - Add custom concern input
  - Next button
- **Effort:** 3 hours (drag-drop is fiddly)
- **Checklist:**
  - [x] Component created
  - [x] Symptoms listed
  - [x] Drag-to-reorder works
  - [x] Add custom concern works
  - [x] Calls API to save order
  - [x] Next button moves to step 4

#### Task 2.3.5: Build Step 4 Component (Review Scenarios)

- **File:** `frontend/src/routes/(app)/appointment-prep/Step4.svelte`
- **What it shows:**
  - Array of scenario cards
  - Each card: "If provider says X, you might respond with Y"
  - User can edit responses
  - Next button
- **Effort:** 2 hours
- **Checklist:**
  - [x] Component created
  - [x] Scenarios displayed as cards
  - [x] User can edit responses
  - [x] Responsive layout
  - [x] Next button moves to step 5

#### Task 2.3.6: Build Step 5 Component (Generate & Download)

- **File:** `frontend/src/routes/(app)/appointment-prep/Step5.svelte`
- **What it shows:**
  - "Generate PDFs" button
  - Download links for both PDFs
  - Success message
  - Option to start new prep or go back
- **Effort:** 2 hours
- **Checklist:**
  - [x] Component created
  - [x] Generate button triggers API call
  - [x] Loading state while generating
  - [x] Download links appear
  - [x] Error handling
  - [x] Can generate multiple times

#### Task 2.3.7: Test Appointment Prep Flow End-to-End

- **What it tests:**
  - User can complete all 5 steps
  - PDFs are generated correctly
  - User can edit at each step
  - Responsive on mobile
- **Effort:** 3 hours
- **Checklist:**
  - [x] Manual testing of full flow
  - [x] Mobile responsiveness verified
  - [x] Error cases tested (no logs, API failure, etc.)
  - [x] PDFs look okay

### 2.4: Appointment Prep Tests

#### Task 2.4.1: Write Route Tests

- **File:** `backend/tests/api/routes/test_appointment.py`
- **What to test:**
  - All 5 endpoints (context, narrative, prioritize, scenarios, generate)
  - Happy paths
  - Error cases (missing user, API failure, etc.)
  - Auth enforcement
- **Effort:** 4 hours
- **Checklist:**
  - [ ] All endpoints have tests
  - [ ] Happy path + error cases
  - [ ] 80%+ coverage
  - [ ] Tests pass

#### Task 2.4.2: Write Service/Repository Tests

- **File:** `backend/tests/repositories/test_appointment_repository.py`
- **What to test:**
  - Save/load context
  - Save/load outputs
- **Effort:** 1 hour
- **Checklist:**
  - [x] Repository tests pass
  - [x] Coverage good

---

## Phase 3: Ask Meno + Basic Tracking (Weeks 9-11)

Build on top of refactored foundation.

### 3.1: Ask Meno Enhancements

#### Task 3.1.1: Add Conversation History

- **Endpoint:** `GET /api/chat/conversations` — list all conversations
- **Endpoint:** `DELETE /api/chat/conversations/{id}` — delete conversation
- **What it does:**
  - Frontend shows list of past conversations
  - User can click to resume or delete
  - Conversation title = first 50 chars of first message
- **Effort:** 3 hours
- **Checklist:**
  - [x] List endpoint created
  - [x] Delete endpoint created
  - [x] Tests pass
  - [x] Frontend shows list
  - [x] User can resume conversation

#### Task 3.1.2: Implement Hybrid RAG Search

- **File:** `backend/app/rag/retrieval.py` (modify existing)
- **What it does:**
  - Semantic search (existing)
  - Add keyword search (new)
  - Combine results
  - Return top 5 chunks
- **Effort:** 3 hours
- **Checklist:**
  - [x] Keyword search implemented
  - [x] Results combined
  - [x] Top 5 returned
  - [x] Tests pass
  - [x] Improves retrieval quality

#### Task 3.1.3: Add Dynamic Starter Prompts

- **Endpoint:** `GET /api/chat/suggested-prompts` — get personalized suggestions
- **What it does:**
  - Based on user's recent symptoms
  - Based on user's journey stage
  - Suggest 3-5 starter questions
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Endpoint created
  - [ ] Uses SymptomsRepository to get recent logs
  - [ ] Generates suggestions
  - [ ] Tests pass
  - [ ] Frontend displays suggestions

### 3.2: Basic Period Tracking

#### Task 3.2.1: Update User Profile Schema

- **Migration:** Add to users table:
  - `has_uterus` (boolean)
  - `hormonal_contraception_type` (enum: none/pills/iud/implant/patch/other)
  - `has_ablation` (boolean)
- **Effort:** 1 hour
- **Checklist:**
  - [ ] Migration created
  - [ ] RLS still works
  - [ ] Models updated

#### Task 3.2.2: Create Period Log Table

- **Migration:** `period_logs` table
  - `user_id`, `start_date`, `end_date`, `flow_level`, `notes`
  - `created_at`, `updated_at`
- **RLS:** Users only see own logs
- **Effort:** 1 hour
- **Checklist:**
  - [ ] Migration created
  - [ ] RLS policies added
  - [ ] Indexes on user_id, date

#### Task 3.2.3: Create Period Repository

- **File:** `backend/app/repositories/period_repository.py`
- **What it does:**
  - `create_log(user_id, start, end, flow, notes)`
  - `get_logs(user_id, start_date, end_date)`
  - `calculate_cycle_length(user_id)` — from last 3 cycles, average
  - `get_latest_cycle_phase(user_id)` — where we are in cycle
- **Tests:** `backend/tests/repositories/test_period_repository.py`
- **Effort:** 3 hours
- **Checklist:**
  - [ ] Repository created
  - [ ] All methods work
  - [ ] Tests pass
  - [ ] Cycle calculation is correct

#### Task 3.2.4: Create Period Logging Endpoint

- **Endpoint:** `POST /api/period-logs` — create log
- **Endpoint:** `GET /api/period-logs` — get logs with date range
- **Endpoint:** `PUT /api/period-logs/{id}` — update log
- **Endpoint:** `DELETE /api/period-logs/{id}` — delete log
- **File:** `backend/app/api/routes/period.py`
- **Tests:** `backend/tests/api/routes/test_period.py`
- **Effort:** 3 hours
- **Checklist:**
  - [ ] All CRUD endpoints created
  - [ ] Validation (dates, flow level)
  - [ ] Auth enforcement
  - [ ] Tests pass

#### Task 3.2.5: Build Period Logging UI

- **Files:**
  - `frontend/src/routes/(app)/period/+page.svelte` — log entry form
  - `frontend/src/routes/(app)/period/history/+page.svelte` — view past logs
  - `frontend/src/components/PeriodLogForm.svelte` — reusable form
- **What it shows:**
  - Calendar to select start/end dates
  - Flow level dropdown
  - Notes text area
  - Save button
  - List of past logs
- **Effort:** 4 hours
- **Checklist:**
  - [ ] Form component created
  - [ ] History page created
  - [ ] Responsive design
  - [ ] Validation working
  - [ ] Save/update/delete works

#### Task 3.2.6: Update User Profile to Show Period Info

- **File:** Modify existing user profile/onboarding
- **What it adds:**
  - Uterus status (for period tracking)
  - Contraception type
  - Ablation status
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Onboarding updated
  - [ ] Profile edit updated
  - [ ] Data persists

### 3.3: Basic Medication Tracking

#### Task 3.3.1: Create Medication Log Table

- **Migration:** `medication_logs` table
  - `user_id`, `name`, `type` (enum: hrt/mht/other), `dose`, `start_date`, `end_date` (nullable), `notes`
  - `created_at`, `updated_at`
- **RLS:** Users only see own logs
- **Effort:** 1 hour
- **Checklist:**
  - [ ] Migration created
  - [ ] RLS policies added
  - [ ] Indexes on user_id, date

#### Task 3.3.2: Create Medication Repository

- **File:** `backend/app/repositories/medication_repository.py`
- **What it does:**
  - `create_log(user_id, name, type, dose, start_date, notes)`
  - `get_logs(user_id, start_date, end_date)`
  - `end_medication(medication_id)` — set end_date
  - `get_active(user_id)` — currently active medications
- **Tests:** `backend/tests/repositories/test_medication_repository.py`
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Repository created
  - [ ] Methods work
  - [ ] Tests pass

#### Task 3.3.3: Create Medication Logging Endpoint

- **Endpoint:** `POST /api/medications` — create log
- **Endpoint:** `GET /api/medications` — get logs with date range
- **Endpoint:** `PUT /api/medications/{id}` — update/end medication
- **Endpoint:** `DELETE /api/medications/{id}` — delete log
- **File:** `backend/app/api/routes/medications.py`
- **Tests:** `backend/tests/api/routes/test_medications.py`
- **Effort:** 3 hours
- **Checklist:**
  - [ ] All CRUD endpoints created
  - [ ] Validation (type enum, dates)
  - [ ] Auth enforcement
  - [ ] Tests pass

#### Task 3.3.4: Build Medication Logging UI

- **Files:**
  - `frontend/src/routes/(app)/medications/+page.svelte` — log entry form
  - `frontend/src/routes/(app)/medications/active/+page.svelte` — current meds
  - `frontend/src/components/MedicationLogForm.svelte` — reusable form
- **What it shows:**
  - Medication name input
  - Type dropdown (HRT, MHT, Other)
  - Dose input
  - Start/end date pickers
  - Notes
  - Current active medications
  - Option to mark as ended
- **Effort:** 4 hours
- **Checklist:**
  - [ ] Form component created
  - [ ] Active meds view created
  - [ ] Responsive design
  - [ ] Validation working
  - [ ] Save/update/delete works

#### Task 3.3.5: Integrate Medications with Timeline

- **What it does:**
  - Show medications in symptom timeline (when user created log)
  - User can see "started HRT on March 1" alongside symptoms
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Symptoms timeline updated
  - [ ] Medications appear in timeline
  - [ ] Visual distinction (different color/icon)

### 3.4: Testing & Integration

#### Task 3.4.1: Integration Tests

- **What to test:**
  - Ask Meno with conversation history
  - Ask Meno with hybrid search
  - Period logging + Appointment Prep (period info in narrative)
  - Medication logging + Appointment Prep (meds info in narrative)
- **Effort:** 3 hours
- **Checklist:**
  - [ ] Integration tests pass
  - [ ] No regressions

#### Task 3.4.2: Manual End-to-End Testing

- **What to test:**
  - Create period log
  - Create medication log
  - Log symptoms
  - Ask Meno question
  - Start Appointment Prep (uses all data)
  - Generate PDFs (include period/meds info)
- **Effort:** 3 hours
- **Checklist:**
  - [ ] Full flow works
  - [ ] Data is consistent
  - [ ] PDFs include period/med info
  - [ ] Mobile responsive

---

## Phase 4: Polish & Launch (Weeks 12-13)

Get ready for production.

### 4.1: Testing & Quality

#### Task 4.1.1: Run Full Test Suite

- **Command:** `pytest --cov=app -v`
- **Target:** 80%+ coverage on all new code
- **Effort:** 2 hours (troubleshooting)
- **Checklist:**
  - [ ] All tests pass
  - [ ] Coverage 80%+
  - [ ] No warnings

#### Task 4.1.2: Performance Testing

- **What to test:**
  - Appointment Prep narrative generation time (should be <10s)
  - PDF generation time (should be <5s)
  - Ask Meno response time with large history (should be <3s)
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Narrative generation is fast
  - [ ] PDF generation is fast
  - [ ] No N+1 queries

#### Task 4.1.3: Security Review

- **What to check:**
  - All endpoints require auth
  - RLS policies correct
  - No PII in logs (hash user IDs)
  - API keys not exposed
  - Rate limiting (optional)
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Auth enforced
  - [ ] RLS verified
  - [ ] Logging reviewed
  - [ ] No secrets in code

### 4.2: Documentation

#### Task 4.2.1: Update CLAUDE.md

- **What to add:**
  - New repositories
  - New services
  - Appointment Prep architecture
  - Any new patterns
- **Effort:** 1 hour
- **Checklist:**
  - [ ] Documentation updated
  - [ ] Examples included

#### Task 4.2.2: Update DESIGN.md

- **What to add:**
  - Appointment Prep user flow
  - Data model updates (period, medications)
  - API endpoints
  - Database schema
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Documentation complete
  - [ ] Diagrams updated

#### Task 4.2.3: Create User-Facing Documentation

- **What to create:**
  - Appointment Prep guide (how to use)
  - Period tracking guide
  - Medication tracking guide
  - FAQ
- **Location:** `docs/user/` or in-app help
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Guides written
  - [ ] Screenshots included
  - [ ] Clear and jargon-free

### 4.3: Deployment Preparation

#### Task 4.3.1: Prepare for Production Deployment

- **What to do:**
  - Verify all migrations work on clean DB
  - Test deployment flow locally
  - Prepare rollback plan
  - Prepare environment variables
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Migrations tested
  - [ ] Deployment script ready
  - [ ] Env vars documented
  - [ ] Rollback plan in place

#### Task 4.3.2: Legal Review for Medical Content

- **What to review:**
  - Appointment Prep disclaimers
  - Ask Meno guardrails
  - Any new medical content
  - Privacy policy updates
- **Effort:** Depends on legal review timeline
- **Checklist:**
  - [ ] Attorney review complete
  - [ ] Disclaimers added
  - [ ] Privacy policy updated

#### Task 4.3.3: Job & Cost Planning

- **What to finalize:**
  - Job search timeline
  - OpenAI API cost estimate for V2
  - Plan for Claude migration (V2/V3)
  - Income needed to support dev
- **Effort:** 1 hour planning
- **Checklist:**
  - [ ] Cost estimates finalized
  - [ ] Job search plan set
  - [ ] Sustainability plan clear

### 4.4: Launch

#### Task 4.4.1: Deploy V2 to Production

- **Effort:** 2-3 hours (with monitoring)
- **Checklist:**
  - [ ] All tests passing
  - [ ] Backups taken
  - [ ] Monitoring active
  - [ ] Deployment successful
  - [ ] No errors in logs

#### Task 4.4.2: Announce V2

- **What to do:**
  - Email users about new features
  - Update app homepage
  - Post on social media (if applicable)
  - Gather early feedback
- **Effort:** 2 hours
- **Checklist:**
  - [ ] Announcement sent
  - [ ] Users know about Appointment Prep
  - [ ] Feedback channel open

---

## Summary: Task Counts & Estimates

### Phase 1: Refactor (Weeks 1-2)

- 14 tasks
- ~27 hours
- Result: Solid foundation for V2 features

### Phase 2: Appointment Prep (Weeks 3-8)

- 17 tasks
- ~40 hours
- Result: Flagship feature complete + tested

### Phase 3: Ask Meno + Tracking (Weeks 9-11)

- 16 tasks
- ~35 hours
- Result: Core features complete + integrated

### Phase 4: Polish & Launch (Weeks 12-13)

- 11 tasks
- ~20 hours
- Result: Production-ready V2

**Total: 58 tasks, ~122 hours (2.5 weeks full-time)**

---

## How to Track Progress

Each week:

1. Pick 5-8 tasks
2. Mark off as you complete
3. Run tests after each task
4. Commit code after each major feature

---
