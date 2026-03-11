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

