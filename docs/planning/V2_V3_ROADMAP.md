# V2 & V3 Roadmap

**Last Updated:** March 10, 2026

---

## V2: Core Feature Complete & Polish Phase

**Status:** In Progress

### V2.0: Core Features (Foundation)

**Completed:**
- ✅ Database schema and migrations
- ✅ Authentication (Supabase)
- ✅ Symptom logging API
- ✅ Domain exception pattern
- ✅ Date utilities and shared business logic
- ✅ Retry & resilience patterns for external APIs
- ✅ Appointment prep workflow (Steps 1-5)
- ✅ Export functionality (PDF + CSV)
- ✅ LLMProvider interface with response_format support
- ✅ RAG document storage and retrieval framework

**Current Focus:**
- Repository Pydantic model pattern (documentation + new code standard)
- Completion of all CRUD repositories

### V2.1: Post-Launch Polish

**Repository Pydantic Model Refactor**

**Goal:** Convert all repositories to return typed Pydantic models instead of raw dicts.

**Status:** In progress (V2 new code uses models, legacy code to be refactored)

**Pattern:**
- Each repository method returns a Pydantic model (UserContext, AppointmentContext, etc.)
- Models are defined in app/models/ and imported by repositories
- Services receive typed objects with autocomplete and type checking

**Benefits:**
- Type safety across all layers
- IDE autocomplete and type checking
- Self-documenting code (model = schema)
- Catches bugs early (type mismatches)
- Claude Code generates correct implementations

**Implementation:**
- [x] Document pattern in CLAUDE.md and V2CODE_EXAMPLES.md
- [ ] Create Pydantic models for key entities:
  - [ ] UserContext (journey_stage, age)
  - [ ] AppointmentContext (appointment_type, goal, dismissed_before, urgent_symptom)
  - [ ] SymptomLog (id, date, symptoms, notes)
  - [ ] SymptomsFrequency (symptom_id, name, count, percentage)
  - [ ] SymptomPair (symptom_1, symptom_2, cooccurrence_rate, category)
- [ ] Update existing repositories to return models:
  - [ ] UserRepository.get_context() → UserContext
  - [ ] SymptomsRepository.get_logs() → list[SymptomLog]
  - [ ] AppointmentRepository.get_context() → AppointmentContext
  - [ ] (others as needed)
- [ ] Update services to use typed models
- [ ] Verify no breaking changes (return types change but behavior same)

**Estimated effort:** 2-3 days (straightforward refactor, high-value)
**Blocked by:** None
**Priority:** Medium (code quality, enables better type checking)

**New Code Requirement:** All new repositories MUST return Pydantic models, not dicts.

---

**PII-Safe Logging Refactor**

**Goal:** Audit and refactor all existing logging to use safe patterns. Health app logs must never contain personal or medical data.

**Status:** In progress (V2 new code uses safe logging utilities, legacy code to be refactored)

**Critical Issue:** Current logging in LLM providers and some services logs prompt content, symptom descriptions, and user-generated data. This violates HIPAA and GDPR.

**Pattern:**
- Use `hash_user_id()` for user IDs (never plaintext)
- Use `safe_len()` for data sizes (never log content)
- Never log symptom descriptions, medical data, prompts, or user-generated content
- Use `safe_summary()` for operation logging
- See `app/utils/logging.py` for utilities

**Implementation:**
- [x] Create logging utilities (`app/utils/logging.py`)
- [x] Document patterns in CLAUDE.md
- [ ] Audit existing code for dangerous logging patterns:
  - [ ] LLM providers (currently logs prompt content — DANGEROUS)
  - [ ] Services (may log user data)
  - [ ] Routes (check response logging)
  - [ ] Repositories (check query logging)
- [ ] Update all dangerous logging calls
- [ ] Add tests to catch PII in logs (grep for plaintext user IDs, symptom terms, etc.)

**Estimated effort:** 3-5 hours
**Blocked by:** None
**Priority:** HIGH (legal/ethical compliance, HIPAA/GDPR)
**Timing:** Weeks 16-17 (right after V2 launch)

**New Code Requirement:** All new code MUST use safe logging utilities (enforced in code review).

**Legal/Ethical Notes:**
- Logging PII violates HIPAA (US), GDPR (EU), and state health privacy laws
- Even "debug" logs can be accessed via log aggregation, monitoring systems, or backups
- Treat all logs as potentially readable by others

---

**Dependency Injection: ABC Refactor**

**Goal:** Audit and refactor all repositories and services to use Abstract Base Class (ABC) consistently. Current code may use ABC, interfaces mixed with concrete classes, or incomplete inheritance patterns.

**Status:** In progress (V2 new code uses ABC, legacy code to be refactored)

**Pattern:**
- All dependencies defined as ABC in `[service_name]_base.py`
- Concrete implementations inherit from ABC explicitly
- All abstract methods implemented (marked with `@abstractmethod`)
- Injected via FastAPI Depends() in routes

**Implementation:**
- [x] Document ABC pattern in CLAUDE.md and V2CODE_EXAMPLES.md
- [ ] Audit existing repositories for ABC usage:
  - [ ] UserRepository — define ABC, verify inheritance
  - [ ] SymptomsRepository — define ABC, verify inheritance
  - [ ] AppointmentRepository — define ABC, verify inheritance
  - [ ] ExportRepository — define ABC, verify inheritance
  - [ ] (others as discovered)
- [ ] Audit existing services for ABC usage:
  - [ ] LLMService — verify ABC pattern
  - [ ] LLMProvider — verify ABC pattern (now done: Protocol → ABC)
  - [ ] CitationService — verify ABC pattern
  - [ ] (others as discovered)
- [ ] Update all non-ABC interfaces to ABC
- [ ] Verify all abstract methods have `@abstractmethod` decorator
- [ ] Verify no Protocol usage (should all be ABC)

**Estimated effort:** 2-3 hours
**Blocked by:** None
**Priority:** Low (code consistency, not blocking features)
**Timing:** Weeks 17-18 (can defer if time-constrained)

**New Code Requirement:** All new repositories and services MUST use ABC (enforced in code review).

**Why ABC Over Protocol:**
- Explicit inheritance contract catches missing implementations at type-check time
- isinstance() checks work (useful for debugging)
- Clear intent: "this is a required interface"
- Consistent with Meno codebase pattern

---

**Future: Authentication Migration to Magic Links + Passkeys**

**Goal:** Migrate from username/password to magic links and optional passkey enrollment.

**Status:** Planned for post-launch (after legal review with health tech attorney).

**Why this matters:**
- Username/password has known security/UX issues (forgotten passwords, reuse across sites)
- Magic links (email-based) are more secure and frictionless for health apps
- Passkeys (biometric) provide optional enhanced security
- Supabase has native support for both

**Current state:**
- Username/password authentication
- E2E tests use `.env.test` with credentials (see docs/dev/frontend/V2CODE_EXAMPLES.md Part 7.2)

**Migration plan:**
1. Legal review: Confirm compliance with HIPAA/privacy requirements (TBD - depends on deployment timeline)
2. Design: Plan user flow for magic link signup/login
3. Backend: Update Supabase auth configuration
4. Frontend: Update login pages and E2E tests
5. Deployment: Gradual rollout (existing users can still use passwords, new users get magic links)
6. Cleanup: Deprecate/remove password auth after user migration period

**E2E Test Changes Required:**

When migrating, update `beforeEach` in tests:

```typescript
// CURRENT (username/password)
test.beforeEach(async ({ page }) => {
  const username = process.env.TEST_USERNAME || 'testuser@example.com';
  const password = process.env.TEST_PASSWORD || 'test_password_123';

  await page.fill('input[type="email"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('/dashboard');
});

// FUTURE (magic links - session seeding)
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(async () => {
    const { supabase } = await import('$lib/supabase/client');
    await supabase.auth.setSession({
      access_token: process.env.TEST_ACCESS_TOKEN!,
      refresh_token: process.env.TEST_REFRESH_TOKEN!,
    });
  });
  await page.goto('/dashboard');
});
```

**Estimated effort:** 5-8 hours
**Blocked by:** Legal review, deployment planning
**Priority:** Medium (improves security/UX, not blocking V2 launch)
**Timeline:** Post-V2 launch, after attorney consultation

**Documentation to update:**
- [ ] Frontend E2E test docs (Part 7 of V2CODE_EXAMPLES.md)
- [ ] Login flow documentation
- [ ] User onboarding guides
- [ ] API documentation (if auth endpoints change)

---

**Streaming & Performance (V2.1 Later)**

- Response streaming for narrative generation (Step 2) — currently 10-15s wait
- Response streaming for scenario generation (Step 4) — currently 10-20s wait
- True structured JSON output validation (not just hints)
- Pagination for symptom logs and chat history

---

**Testing & Quality (Ongoing)**

- Increase backend test coverage to 80%+
- Add end-to-end tests for critical user flows
- Performance testing and optimization
- Load testing for production readiness

---

**Accessibility & UX (V2.1)**

- Full WCAG 2.1 Level AA compliance audit
- Touch target and mobile responsiveness verification
- Keyboard navigation testing
- Screen reader testing
- User testing with target demographic

---

### V2.2: Advanced Features (Post-Launch)

**Cycle Tracking**

- Period tracking (date, flow, symptoms)
- Cycle analysis (cycle length, patterns, predictions)
- Hormonal symptom correlation

**Medication & Treatment**

- HRT tracking (type, dosage, side effects)
- Supplement tracking
- Treatment effectiveness patterns

**Intelligence**

- Cycle-based pattern recognition
- Treatment response analysis
- Personalized recommendations (education only, not medical advice)

---

## V3: Scale & Intelligence Phase

**Status:** Planning

### V3.0: Refactoring & Architecture (Ongoing from V2.1)

**Code Quality Initiative**
- Repository Pydantic model pattern (continuation from V2.1)
- Service layer consolidation
- API endpoint optimization
- Error handling standardization
- Test infrastructure improvements

### V3.1: Advanced Analytics

- Cohort analysis (symptoms by age, stage, treatment)
- Population health insights
- Trend detection
- Risk factor identification

### V3.2: Provider Intelligence

- Provider matching based on specialties and availability
- Insurance acceptance information
- Wait time tracking
- Provider review aggregation

### V3.3: Community & Support

- Anonymous symptom data sharing
- Peer support communities
- Provider recommendations from peers
- Educational resource curation

---

## Technical Debt & Maintenance

### High Priority
- [ ] Repository refactoring to Pydantic models (V2.1)
- [ ] Streaming response implementation (V2.1)
- [ ] Full test coverage for critical paths

### Medium Priority
- [ ] API rate limiting and throttling
- [ ] Caching strategy refinement
- [ ] Database query optimization
- [ ] Frontend performance optimization

### Low Priority (Post-Launch)
- [ ] Migration from OpenAI to Claude API (if scaling warrants)
- [ ] Advanced RAG tuning (hybrid search, re-ranking)
- [ ] Custom embedding model training
- [ ] Mobile app implementation

---

## Production Readiness

**Before any production launch:**

1. ✅ Medical advice boundary tested (GUARDRAILS_AUDIT.md)
2. ⏳ Legal review (LEGAL_PREP.md — awaiting attorney)
3. ⏳ Security audit (penetration testing, data handling review)
4. ⏳ Job + API cost plan (6 months forecast)
5. ⏳ Production deployment checklist (PRODUCTION_CHECKLIST.md)
6. ⏳ Data privacy & compliance (HIPAA/GDPR assessment)
7. ⏳ Monitoring & alerting (Sentry, logs, metrics)
8. ⏳ Incident response plan
9. ⏳ User support structure

---

## Key Decisions & Rationale

### Pydantic Models for Repositories (V2.1)
- **Decision:** All repositories return typed Pydantic models instead of raw dicts
- **Rationale:** Type safety, IDE support, self-documenting code, easier Claude Code generation
- **Impact:** No breaking changes (internal refactor), immediate code quality improvement
- **Timeline:** Refactor during V2.1 (1-2 sprints)

### Streaming Responses (V2.1)
- **Decision:** Implement response streaming for LLM-generated content
- **Rationale:** Reduce user wait time (currently 10-20s for narrative/scenarios), improve UX
- **Impact:** Frontend needs stream handling, backend chunks responses
- **Timeline:** Post-core-feature-completion (V2.1)

### LLM Provider Strategy (Ongoing)
- **Development:** OpenAI (gpt-4o-mini) for cost-effectiveness
- **Production:** Claude (claude-sonnet-4) for better reasoning and safety alignment
- **Migration:** Straightforward (swap provider wrapper + environment variables)
- **Timeline:** Decision made at production launch readiness

---

## Success Metrics

- **Code Quality:** 80%+ test coverage, 0 critical bugs
- **Performance:** API latency < 2s (p95), narrative generation < 5s (streaming)
- **Accessibility:** WCAG 2.1 Level AA compliance, 100% keyboard navigable
- **User Experience:** NPS 60+, task success rate 95%+
- **Reliability:** 99.5% uptime (excluding scheduled maintenance)

---

## Questions & Decisions Needed

1. When should we migrate from OpenAI to Claude API?
2. Should we prioritize streaming (UX) or advanced analytics (features) first?
3. What's the target for user testing — how many beta users?
4. Should cycle tracking or medication tracking come first in V2.2?

