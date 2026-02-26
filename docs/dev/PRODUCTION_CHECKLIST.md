# Production Readiness Checklist for Meno

**Status:** V1 Complete - Pre-Production Review Phase  
**Last Updated:** February 2026  
**Target:** Deployment after legal review + job transition + monetization plan

---

## PRODUCTION BLOCKERS (Must Fix Before Any Real Users)

### Legal & Liability

- [ ] **Lawyer Review Complete**
  - [ ] LEGAL_PREP.md reviewed by attorney
  - [ ] Guardrails audit (GUARDRAILS_AUDIT.md) reviewed by attorney
  - [ ] Legal opinion on liability exposure documented
  - [ ] Insurance requirements identified
  - [ ] Attorney-approved terms of service drafted
  - [ ] Attorney-approved privacy policy drafted

- [ ] **Disclaimers Finalized**
  - [ ] Medical disclaimer text approved by lawyer
  - [ ] Disclaimer shown on onboarding (required acknowledgment)
  - [ ] Disclaimer shown on every Ask Meno response
  - [ ] Disclaimer on PDF export footer
  - [ ] Disclaimer tested in all code paths
  - [ ] "NOT MEDICAL ADVICE" visual indicator added to Ask Meno UI

### Data Governance

- [ ] **API Training Data Decision Made**
  - [ ] [ ] Option A: Opt out of OpenAI training before launch
    - [ ] `settings.OPENAI_API_KEY_NO_TRAINING` configured
    - [ ] All OpenAI calls use opt-out flag
    - [ ] Documented in code + CLAUDE.md
  - [ ] [ ] Option B: Migrate to Claude API
    - [ ] Claude API key obtained and configured
    - [ ] LLM wrapper updated to support Claude
    - [ ] Cost model calculated (embeddings + chat)
    - [ ] Decision documented in CLAUDE.md

- [ ] **Embeddings Provider Decided**
  - [ ] [ ] Continue with OpenAI text-embedding-3-small (default)
  - [ ] [ ] Switch to sentence-transformers (self-hosted, no training data)
  - [ ] [ ] Decision documented + implemented

### Authentication & Access Control

- [ ] **Auth Tested End-to-End**
  - [ ] Magic link flow works (email → code → session)
  - [ ] Passkey flow works (if enabled)
  - [ ] Auth token refresh works
  - [ ] Logout clears session
  - [ ] Invalid token returns 401
  - [ ] Expired token returns 401

- [ ] **RLS Policies Verified**
  - [ ] Each user can only see own data (symptom_logs, conversations, exports)
  - [ ] RLS policies tested with unit tests
  - [ ] Attempted access to other user's data returns 403
  - [ ] Provider directory is public (no RLS, as intended)

### Deployment Infrastructure

- [ ] **Vercel Frontend Configured**
  - [ ] Auto-deploy from main branch works
  - [ ] Environment variables set (PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY)
  - [ ] VITE_API_BASE_URL points to production backend
  - [ ] Build passes (npm run build succeeds)
  - [ ] Preview environment tested

- [ ] **Railway Backend Configured**
  - [ ] Auto-deploy from main branch works
  - [ ] Environment variables set (SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, etc.)
  - [ ] APP_ENV=production set
  - [ ] ALLOWED_ORIGINS set to production domain
  - [ ] Health check endpoint responds

- [ ] **Supabase Production Database**
  - [ ] Database backups enabled (automated daily)
  - [ ] RLS policies enabled and tested
  - [ ] Row limits per user enforced (or will monitor)
  - [ ] Unused indexes cleaned up (performance)
  - [ ] Slow query logging enabled

---

## PORTFOLIO / CODE QUALITY (POC Validation)

### Error Handling & Logging

- [ ] **All API Endpoints Have Error Handling**
  - [ ] HTTP exceptions raised with correct status codes (400, 401, 404, 500)
  - [ ] Errors logged with context but NO sensitive data
  - [ ] User-facing error messages are helpful, not technical
  - [ ] Request IDs logged for tracing
  - [ ] Sensitive data (passwords, health info) never logged

- [ ] **Graceful Degradation**
  - [ ] RAG failure → endpoint still responds (without sources)
  - [ ] OpenAI failure → 500 with user-friendly message
  - [ ] DB failure → 500 with user-friendly message
  - [ ] Missing user profile → defaults applied (graceful fallback)

### Medical Advice Boundary

- [ ] **Guardrails Tested**
  - [ ] Diagnosis attempt → redirects without diagnosing ✅ (tested)
  - [ ] Treatment recommendation attempt → shares evidence without recommending ✅ (tested)
  - [ ] Prompt injection attempt → hard-stops ✅ (tested)
  - [ ] Out-of-scope question → redirects gracefully ✅ (tested)
  - [ ] In-scope question → answers fully ✅ (tested)

- [ ] **Guardrail Integration Tests Added**
  - [ ] `backend/tests/api/routes/test_chat_guardrails.py` created
  - [ ] Tests can be run with `pytest --integration` or similar
  - [ ] All 5+ test cases pass
  - [ ] Tests documented for future maintainers

- [ ] **System Prompts Reviewed for Clarity**
  - [ ] Ask Meno system prompt (4 layers) is in sync with DESIGN.md
  - [ ] All LLM calls use proper system prompts
  - [ ] No "system prompt injection" vulnerabilities in prompt assembly

### Data Privacy

- [ ] **Anonymization Before LLM**
  - [ ] User names never sent to LLM ✅
  - [ ] Email addresses never sent to LLM ✅
  - [ ] Exact dates of birth never sent to LLM (only age) ✅
  - [ ] Location data not sent to LLM ✅
  - [ ] Raw free-text logs stripped before LLM (only summaries sent) ✅
  - [ ] Code review confirms anonymization in ask_meno endpoint

- [ ] **RLS Policies Enforced**
  - [ ] Every user data table has RLS enabled
  - [ ] RLS policies tested (unit tests verify scoping)
  - [ ] No query bypasses RLS
  - [ ] No sensitive data exposed in error messages

- [ ] **Logging Doesn't Expose PII**
  - [ ] Symptom logs not in application logs ✅
  - [ ] User context (age, journey stage) not logged ✅
  - [ ] API responses logged only at summary level (not full body) ✅
  - [ ] Code review confirms no PII in logs

### Test Coverage

- [ ] **Guardrails Coverage**
  - [ ] Medical advice boundary has integration tests
  - [ ] Prompt injection tests exist
  - [ ] All boundary test cases pass

- [ ] **Service Layer Coverage**
  - [ ] Frequency stats calculation tested
  - [ ] Co-occurrence calculation tested
  - [ ] Anonymization logic tested
  - [ ] Citation extraction tested
  - [ ] Target: >70% coverage on critical paths

- [ ] **API Endpoint Coverage**
  - [ ] Happy path tests for all endpoints
  - [ ] Auth required tests (401 for missing token)
  - [ ] Error case tests (400 for bad input, 404 for not found)
  - [ ] RLS enforcement tests (user can only access own data)

- [ ] **Integration Test Suite Passes**
  - [ ] `pytest backend/tests/` passes
  - [ ] All 178+ tests pass locally
  - [ ] Coverage report generated

### Code Documentation

- [ ] **CLAUDE.md Updated**
  - [ ] "DEV-ONLY POC" notice at top
  - [ ] Links to LEGAL_PREP.md and GUARDRAILS_AUDIT.md
  - [ ] Explains what changes for production (LLM provider switch, embeddings cost, API keys)
  - [ ] Architecture sections still accurate

- [ ] **DESIGN.md In Sync**
  - [ ] Feature specs match implementation
  - [ ] Data models match schema
  - [ ] API endpoints match routes
  - [ ] Known differences from spec documented (if any)

- [ ] **README Updated**
  - [ ] How to run locally documented
  - [ ] How to set up .env documented
  - [ ] How to run tests documented
  - [ ] Links to CLAUDE.md and DESIGN.md

- [ ] **Critical Decision Points Documented**
  - [ ] Why we anonymize before LLM (and how)
  - [ ] Why we don't send conversation history to LLM
  - [ ] Why RLS is at DB level, not just app level
  - [ ] Why guardrails testing matters
  - [ ] LLM provider strategy (dev vs. production)

---

## PRODUCTION CHANGES (When Monetizing in ~6 Months)

### LLM Provider Migration

- [ ] **Claude API Wrapper Ready**
  - [ ] `backend/app/services/llm.py` has both OpenAI and Claude implementations
  - [ ] Environment variable `LLM_PROVIDER` controls which is used
  - [ ] Switching providers requires only env var change (no code changes)

- [ ] **LLM Provider Switched**
  - [ ] [ ] Before prod: All production calls to Claude (migration path ready)
  - [ ] [ ] Confirmed: Anthropic API key obtained, stored securely
  - [ ] [ ] Tested: All prompts work with Claude Sonnet 4
  - [ ] [ ] Documented: Claude API costs estimated + documented

### Embeddings Migration

- [ ] **Embeddings Provider Updated**
  - [ ] [ ] Decision: Stay on OpenAI or switch to Claude
  - [ ] [ ] If OpenAI: Free tier → Paid tier configured
  - [ ] [ ] If Claude: Use Claude embeddings or self-hosted
  - [ ] [ ] Cost per request logged (debugging + cost tracking)

- [ ] **Cost Tracking Added**
  - [ ] Embeddings cost per query estimated + logged
  - [ ] Chat completion cost per query estimated + logged
  - [ ] Daily/monthly cost reports available
  - [ ] Budget alerts configured

### Deployment & Monitoring

- [ ] **Monitoring & Alerting**
  - [ ] Error rate alerts (>5% failures)
  - [ ] Latency alerts (API response time >2s)
  - [ ] OpenAI API failure alerts
  - [ ] Database error alerts
  - [ ] RAG retrieval failure alerts

- [ ] **Usage Limits Configured**
  - [ ] Rate limiting: max X requests per user per hour
  - [ ] Max tokens per query (hard limit to prevent runaway costs)
  - [ ] Max conversation size (prevent unbounded growth)

- [ ] **Uptime Monitoring**
  - [ ] Health check endpoint responds
  - [ ] Database connectivity verified
  - [ ] OpenAI API connectivity verified
  - [ ] Supabase services verified

### Data Retention & Cleanup

- [ ] **Data Retention Policy Implemented**
  - [ ] Account deactivation → 30-day soft delete, then hard delete
  - [ ] Exports older than X days auto-deleted (if policy exists)
  - [ ] Logs older than X days retained (or archived)
  - [ ] Documented in privacy policy

- [ ] **Backup & Recovery**
  - [ ] Database backups run daily
  - [ ] Backup retention policy: keep 30 days
  - [ ] Tested: restore from backup works
  - [ ] Disaster recovery plan documented

---

## Deployment Checklist (Day Before Launch)

### Code & Config

- [ ] Git main branch is clean (all PRs merged, tests passing)
- [ ] Environment variables set in production (Vercel + Railway dashboards)
- [ ] Database migrations applied (if any)
- [ ] Secrets (API keys) are configured, not committed
- [ ] .env files are in .gitignore and never committed

### Testing

- [ ] Full test suite passes: `pytest backend/tests/`
- [ ] Frontend build succeeds: `npm run build`
- [ ] Guardrails tests pass (integration tests)
- [ ] Smoke test of production endpoints:
  - [ ] Auth endpoint works (login, logout)
  - [ ] Symptom logging endpoint works (POST)
  - [ ] Dashboard data loads
  - [ ] Ask Meno endpoint responds
  - [ ] Export endpoint works

### Documentation

- [ ] Status page updated: "Meno is live"
- [ ] Privacy policy published and linked from app
- [ ] Terms of service published and linked from app
- [ ] FAQ / Help page created
- [ ] Contact email for support published

### Monitoring

- [ ] Sentry (or error tracking) configured and monitoring
- [ ] Database backups verified (at least one successful backup)
- [ ] Health check endpoint responds
- [ ] Logging configured and flowing

### Comms

- [ ] Email announcement drafted (beta release)
- [ ] Social media post drafted (if applicable)
- [ ] Internal team notified
- [ ] Support process documented (who handles questions)

---

## Deferred to V2 (Won't Block Production)

These are features designed but not built, planned for after V1 launch:

- [ ] Period tracking (uterus flag, cycle analysis, inferred stage)
- [ ] Medication tracking
- [ ] Lab result logging
- [ ] Map view for providers
- [ ] Conversation history (with token budget)
- [ ] Hybrid RAG search (semantic + keyword)
- [ ] Appointment Prep Flow (multi-step, interactive)
- [ ] Mobile app
- [ ] International providers
- [ ] Magic link → Passkeys upgrade

---

## Notes & Known Gaps

### What We Know Works

✅ Authentication (Supabase Auth, magic link)  
✅ Symptom logging (card system, free text, multiple logs per day)  
✅ Dashboard (frequency, co-occurrence, date filtering)  
✅ Ask Meno (RAG + system prompt guardrails, tested)  
✅ Export (PDF with AI summary, CSV raw data)  
✅ Provider directory (search, filter, calling script)  
✅ Service layer (clean separation, testable)  
✅ API client wrapper (consistent error handling)  
✅ RLS enforcement (tested, working)  
✅ Guardrails (tested against boundary cases)  

### What We're Validating

⏳ Legal review (awaiting attorney feedback)  
⏳ Monetization plan (awaiting job + API cost decision)  
⏳ Security audit (on hold until legal review)  
⏳ User testing (awaiting launch clearance)  

### What Could Break

🔴 OpenAI API goes down → graceful degradation implemented, will surface to users  
🔴 RAG database slow → may impact Ask Meno latency, monitoring needed  
🔴 Supabase RLS misconfiguration → would be caught by tests  
🔴 LLM ignores system prompt → extremely unlikely, guardrails tested  

---

## How to Use This Checklist

1. **Before legal review:** Share LEGAL_PREP.md + GUARDRAILS_AUDIT.md with your attorney
2. **After legal review:** Update "Legal & Liability" section with attorney feedback
3. **Before monetization:** Make the API provider decisions (OpenAI opt-out or Claude)
4. **Before soft launch:** Work through "Code Quality" and "Deployment" sections
5. **Before hard launch:** Complete "Deployment Checklist"

---

_Last updated: February 2026 | Version 1.0_
