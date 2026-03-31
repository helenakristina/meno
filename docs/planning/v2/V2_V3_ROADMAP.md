# V2 & V3 Roadmap

**Last Updated:** March 2, 2026
**Status:** Planning phase (refactor starting after code review)

---

## Overview

Meno has two major phases ahead. **V2 focuses on one flagship feature (Appointment Prep) + core enhancements.** V3 builds out the advanced analytics and infrastructure.

### Timeline Estimate

- **Refactor (Foundation):** 2-3 weeks
- **V2 Development:** 10-12 weeks
- **V2 Launch & Stabilization:** 2-4 weeks
- **Total to V2 Launch:** 4-5 months (part-time)

---

## V2: Flagship + Core Enhancements

**Focus:** Solve the core appointment problem. Build on solid foundation (post-refactor).

**Launch Date Target:** July 2026

### V2.1: Appointment Prep Flow ⭐ (FLAGSHIP)

**The Problem It Solves:**
Women arrive at menopause appointments unprepared, often having forgotten key concerns or been dismissed before. They have months of symptom data but no way to present it effectively. Appointment Prep transforms logged data into a provider-ready appointment kit.

**User Flow (5 Steps):**

1. **Set the Context**
   - What kind of appointment? (New provider / established)
   - What's your primary goal? (Understand where I am / discuss HRT / evaluate current treatment / address specific symptom)
   - Been dismissed by providers before? (Yes, multiple times / once or twice / no)
   - These answers shape tone and content throughout

2. **Surface the Data Story**
   - Pull last 60-90 days of symptom logs
   - LLM generates narrative summary (not a data dump)
   - Show: frequency, co-occurrence, trend direction, notable changes
   - User can review, edit, and mark what's important

3. **Prioritize Concerns**
   - Drag-to-rank interface: top symptoms + free-text concerns
   - User orders by what matters most
   - **Most critical UX moment** — providers address what's raised first

4. **Anticipate the Conversation**
   - LLM generates scenario cards: "If provider says X, research supports Y"
   - Not scripts — preparation for common dismissal moments
   - Scenarios selected based on goal (e.g., HRT discussion → breast cancer risk scenarios)

5. **Generate Outputs**
   - **Provider Summary:** One-page clinical overview (PDF, can share or hand over)
   - **Personal Cheat Sheet:** Prioritized concerns + key questions (PDF or mobile view for quick reference)

**LLM's Role:**

- Calculate frequency/co-occurrence (Python)
- Identify trends (Python)
- Write narrative summary (LLM)
- Select relevant dismissal scenarios (LLM)
- Generate provider summary prose (LLM)
- Write opening statement draft (LLM)

**Design Principles:**

- **Opinionated, not neutral** — Users should lead with what matters, know their data, prepare for dismissals
- **Editable at every step** — LLM output is a draft. Users control final output
- **Not a replacement** — Explicitly frames as preparation, includes medical disclaimer

**Privacy:**

- Cheat sheet may have candid language (dismissal experiences, personal priorities)
- Provider summary contains only clinical data
- Same anonymization policy as existing: no names, no exact DOB, no location

**Effort:** 40-60 hours
**Value:** VERY HIGH (unique feature, core to mission)
**Tests:** New integration tests for LLM flow, PDF generation tests

---

### V2.1 Polish: Appointment Prep PDF Quality and Formatting

**Goal:** Improve the visual quality, formatting, and professional presentation of generated PDFs (Personal Cheatsheet and Provider Summary).

**Current State:** PDFs are functional and contain correct data, but formatting could be more polished for professional presentation to healthcare providers.

**Files Involved:**

- `backend/app/services/pdf.py` — PDF generation logic
- `backend/app/services/llm.py` — Content generation for PDFs
- Frontend: Step 5 component that displays generated PDFs

**Areas for Improvement:**

1. **Visual Design and Branding**
   - Add Meno logo/header to PDFs
   - Use consistent color scheme (teal accent colors from app design)
   - Improve typography hierarchy (font sizes, weights, spacing)
   - Add page numbers and footer with date/user info
   - Ensure PDFs look professional enough to hand to a healthcare provider
   - Effort: 2-3 hours

2. **Content Structure and Readability**
   - Organize information with clear sections and subsections
   - Use bullet points, tables, and whitespace effectively
   - Ensure no orphaned text or awkward page breaks
   - Add table of contents for multi-page documents
   - Effort: 1-2 hours

3. **Data Presentation**
   - Symptom frequency data (charts vs. tables vs. narrative)
   - Co-occurrence patterns (how to display relationships clearly)
   - Prioritized concerns (ranked list with reasoning)
   - Practice scenarios (formatted for easy reading)
   - Effort: 1.5-2 hours

4. **Accessibility in PDFs**
   - Ensure PDF is properly tagged (headings, lists, tables)
   - Add alt text to charts/images if included
   - Ensure text contrast meets WCAG standards
   - Test screen reader compatibility
   - Effort: 1 hour

5. **Provider-Specific Polish (Provider Summary)**
   - Clinical tone and appropriate language
   - Key metrics highlighted for easy scanning
   - Summary at top (appointment goal, urgent symptom, key concerns)
   - Symptom data presented in clinically relevant way
   - Practice scenarios formatted as reference material
   - Effort: 1.5-2 hours

6. **Personal Cheatsheet Polish**
   - User-friendly tone (less clinical than provider summary)
   - Key talking points highlighted
   - Practice scenarios formatted as "things to say"
   - FAQ or tips section
   - Effort: 1-1.5 hours

7. **Technical Improvements**
   - Handle edge cases (very long symptom descriptions, special characters)
   - Ensure consistent font embedding (no missing fonts when shared)
   - Test PDF generation with various data sizes (1 symptom vs. 100 symptoms)
   - Add error handling if PDF generation fails
   - Effort: 1 hour

8. **Testing and Validation**
   - Manual PDF review across different data scenarios
   - Print test (ensure PDFs look good printed, not just on screen)
   - Mobile view test (readable on phone, not just desktop)
   - Provider feedback (show to actual healthcare providers if possible)
   - Effort: 1-2 hours (ongoing)

**Definition of Done:**

- [ ] PDFs have professional header with Meno branding
- [ ] Typography is clear and well-organized (headings, body, emphasis)
- [ ] Color scheme matches app design (teal accents)
- [ ] No awkward page breaks or orphaned text
- [ ] Provider Summary is clinically appropriate and easy to scan
- [ ] Personal Cheatsheet is user-friendly and actionable
- [ ] All data displays correctly across various input sizes
- [ ] PDFs are tagged for accessibility
- [ ] Manual testing on print and mobile views passes
- [ ] At least one healthcare provider has reviewed and approved format

**Estimated Total Effort:** 10-14 hours

**Priority:** Medium (improves user experience and professional impression, but not blocking V2 launch)

**Timeline:** V2.1 (1-2 weeks after V2 launch)

**Dependencies:** None — can be done independently after V2 ships

**Notes:**

- This is high-visibility to users (PDFs are the final output of Appointment Prep)
- Consider using a PDF library with better formatting support (ReportLab, WeasyPrint, or similar)
- May require backend changes to improve PDF generation quality
- Coordinate with UX/design team on visual direction if available
- Consider creating PDF templates/styles that can be reused

**Related Issues:**

- Part 4: Error Handling (ensure PDF generation errors are handled gracefully)
- Part 13: Multi-Step Flows (PDF generation is Step 5 output)

---

### V2.2: Ask Meno Enhancements

**Conversation History**

- User opt-in for persistent conversations
- Token budget management (show user how many tokens used)
- Delete conversation history option
- Each conversation is independent (current approach), but can reference previous chats if user wants

**Dynamic Starter Prompts**

- Suggest questions based on recent symptoms
- "People with your symptom pattern often ask..."
- Personalized to user's journey stage and symptom profile

**Hybrid RAG Search**

- Semantic search (what we have now)
- Add keyword search fallback
- Combine both for better retrieval
- Especially helps with medical jargon variations

**Knowledge Base Updates**

- Scheduled job to ingest new research
- Start with one new curated source per month
- Manual review before adding (don't auto-ingest)

**Effort:** 15-20 hours
**Value:** HIGH (improves existing feature users love)
**Tests:** Tests for new search patterns, conversation storage

---

### V2.3: Basic Period Tracking

**What's Included:**

- Add uterus/hormonal contraception/ablation flags to user profile
- Period log entry: start date, end date, flow level (light/moderate/heavy), notes
- Cycle length calculation (auto-calculated from start dates)
- No fancy analysis yet — just data collection

**What's NOT Included (Defer to V3):**

- Perimenopause stage inference from cycle data
- Cycle phase correlation with symptoms
- Trending analysis ("your cycles are getting shorter")

**Why This Scope:**

- Get the data collection right first
- Analysis comes in V3 when you have the data
- Enables Appointment Prep to reference cycle info

**Effort:** 15 hours
**Value:** HIGH (foundation for V3 analysis, useful to users now)
**Tests:** Tests for date validation, flow level validation, cycle length calculation

---

### V2.4: Basic Medication & Hormone Tracking

**What's Included:**

- Simple log entry: medication/hormone name, type (HRT/MHT/other), dose, start date
- Lab value logging: hormone panel results (optional, for power users)
- Display in timeline with symptoms (user can see when they started HRT vs symptoms)
- No analysis yet — just visualization

**What's NOT Included (Defer to V3):**

- Before/after analysis ("hot flashes reduced 60% since starting HRT")
- Correlation with symptom patterns
- Multi-variable trending

**Why This Scope:**

- Collect the data cleanly
- Visualization helps users understand their own patterns
- Analysis in V3 when you have more data

**Effort:** 10 hours
**Value:** HIGH (critical for HRT users, enables V3 analysis)
**Tests:** Tests for medication validation, date validation, timeline integration

---

### V2 Refactor (Foundation for Everything)

**Prerequisite for all V2 features.** Must be done first, then features are built on solid foundation.

**Refactoring Work:**

1. ✅ Establish domain exception pattern (EntityNotFoundError, DatabaseError, ValidationError, etc.)
   - Separates business logic from HTTP concerns
   - Repositories/services raise domain exceptions (not HTTPException)
   - Global exception handlers in main.py convert to HTTP responses
   - See `app/exceptions.py` and CLAUDE.md for pattern

2. Create repository layer (UserRepository, SymptomsRepository, ConversationRepository, etc.)
   - Use domain exceptions (not HTTPException) per pattern
   - Raises EntityNotFoundError, DatabaseError

3. Refactor LLM service with dependency injection
4. Extract CitationService from chat route
5. Add test coverage as services are refactored

**Why This Matters:**

- Domain exception pattern keeps code testable across contexts (routes, services, background jobs)
- Repositories are independent of HTTP semantics
- New features (Appointment Prep, multi-step flows) need DI for testability
- Repositories make it easy to add new data (period, meds, labs)
- Existing features (chat, symptoms) become easier to modify

**Effort:** 15 hours
**Value:** Foundational (enables all other V2 work)
**Timeline:** Do this FIRST, before any V2 features

---

### V2 Launch Checklist

Before shipping V2:

- [ ] All refactoring complete + tests passing
- [ ] Appointment Prep flow tested end-to-end
- [ ] PDF generation tested (provider summary + cheat sheet)
- [ ] Period tracking validated
- [ ] Medication tracking validated
- [ ] Ask Meno conversation history working
- [ ] Hybrid search improving results
- [ ] 80%+ test coverage on new code
- [ ] Legal review complete (medical content)
- [ ] User research/testing with 3-5 users
- [ ] Deployment plan ready
- [ ] Job hunting + income secured (for costs)

---

## V3: Advanced Analytics & Infrastructure

**Launch Date Target:** Q4 2026 or Q1 2027

**Focus:** Deep insights from collected data. Infrastructure for scale.

### V3.0: Legacy Code Refactor (Ongoing, Post-Launch)

**Goal:** Convert all repositories/services to domain exception pattern over time.

**Status:** Foundation in place (new code uses domain exceptions), legacy code to be refactored gradually.

**What's Needed:**

- [ ] Update existing repositories to raise domain exceptions instead of HTTPException
- [ ] Update existing services to handle domain exceptions properly
- [ ] Update existing routes (optional - global handlers already work)
- [ ] Add tests for exception handling

**Estimated Effort:** 1-2 days total (1-2 hours per repository)

**Priority:** Low (code quality, doesn't affect user features)

**Constraint:** All NEW code MUST follow domain exception pattern.

**Note:** This is ongoing maintenance, not blocking V2 or V3 features. Can be done incrementally as we touch existing code.

---

### V3.1: Enhanced Pattern Analysis

**Multi-Variable Reasoning:**

- Correlate cycle phase + hormone levels + medications + symptoms
- "Your hot flashes spike during the follicular phase AND are worse on days 3-7 of estrogen patch"
- Not just "X happens with Y" — understand the compound effects

**Trending Analysis:**

- "Your hot flashes have reduced 60% since starting HRT (8 weeks ago)"
- "Your sleep quality is trending upward over the last month"
- Anomaly detection: "This symptom cluster is new in the last 2 weeks"
- Timeline visualizations

**LLM-Generated Insights:**

- "Based on your patterns, consider discussing [X] with your provider"
- "Research suggests [Y] might help with your specific profile"
- Always educational, never prescriptive

**Effort:** 20-30 hours
**Value:** HIGH (science-y insights users love)
**Blockers:** Needs period tracking + medication tracking (from V2)

---

### V3.2: Appointment Prep V2

**Enhancements to Flagship Feature:**

- Include cycle phase in narrative if period tracking available
- Include medication status in scenario selection
- Reference lab values if available
- Multi-appointment tracking (compare across appointments)

**Effort:** 10 hours
**Value:** MEDIUM (incremental improvement on V2 feature)
**Blockers:** V2.3, V2.4 must be in place

---

### V3.3: Provider Directory V2

**Map View**

- Pin map with provider locations
- Filter by state, city, insurance
- Click pin → provider details
- Search radius (find providers within X miles)

**International Expansion**

- UK: NHS doctors + private providers
- Canada: By province, public + private
- Australia: By state, medicare coverage
- Data model supports international (addresses, phone formats, insurance types)

**Effort:** 15-20 hours
**Value:** MEDIUM (nice UI improvement, enables expansion)
**Timeline:** Can do in parallel with other V3 work

---

### V3.4: Technical Infrastructure

**Mobile App**

- React Native or Capacitor wrapping SvelteKit
- Access symptom logging, Ask Meno from phone
- Push notifications (optional, for appointments or new features)
- Offline mode for log entries

**Self-Hostable Option**

- Docker containers
- Setup guide for privacy-conscious users
- Community support (GitHub issues, docs)

**Knowledge Base Scheduler**

- Automated job to ingest new research
- Scheduled scraping of trusted sources
- Manual review workflow
- Notification when new sources added

**Effort:** 60-80+ hours
**Value:** MEDIUM (nice to have, not blocking core features)
**Timeline:** Lowest priority, can be deferred further

---

## Feature Comparison: V1 vs V2 vs V3

| Feature                     | V1              | V2                           | V3                                |
| --------------------------- | --------------- | ---------------------------- | --------------------------------- |
| **Symptom Tracking**        | ✅ Basic        | ✅ + Frequency/Co-occurrence | ✅ + Multi-variable trends        |
| **Ask Meno Chat**           | ✅ Conversation | ✅ + History + Hybrid search | ✅ + Personalized starter prompts |
| **Provider Directory**      | ✅ US directory | ✅ Same                      | ✅ + Map + International          |
| **PDF Export**              | ✅ Basic        | ✅ + Appointment Prep        | ✅ + Multi-appointment compare    |
| **Period Tracking**         | ❌              | ✅ Basic logging             | ✅ + Cycle phase analysis         |
| **Medication Tracking**     | ❌              | ✅ Basic logging             | ✅ + Before/after analysis        |
| **Lab Values**              | ❌              | ❌                           | ✅ Optional logging + analysis    |
| **Trending Analysis**       | ❌              | ❌                           | ✅                                |
| **Mobile App**              | ❌              | ❌                           | ✅                                |
| **Self-Hostable**           | ❌              | ❌                           | ✅                                |
| **International Providers** | ❌              | ❌                           | ✅                                |

---

## Why This Sequencing?

### V2 Focuses on the Appointment Problem

- **Appointment Prep** is the flagship — solves the core mission
- **Basic tracking** (period, meds) sets foundation for V3 analysis
- **Ask Meno improvements** enhance existing loved feature
- **Refactor** enables all of this to be built cleanly

### V3 Focuses on Insights & Scale

- With V2 data (period + meds), V3 can do meaningful analysis
- Multi-variable analysis requires data from V2 features
- Map view and international are nice but not blocking
- Mobile + self-hosting are infrastructure, not blocking core features

### This Reduces V2 Scope

- **V2: ~120 hours** (3-4 weeks full-time, achievable)
- **Not trying to do:** Mobile, international, fancy analysis, self-hosting
- **Staying focused:** Appointment Prep + basic tracking + solid foundation

---

## Development Strategy

### Phase 1: Refactor (Weeks 1-2)

- Repositories
- DI on LLM
- Extract CitationService
- New test coverage
- Deploy refactored V1 (no feature changes)

### Phase 2: Appointment Prep (Weeks 3-8)

- Build 5-step flow
- LLM integration
- PDF generation
- Testing
- Ship as V2 feature

### Phase 3: Basic Tracking + Ask Meno (Weeks 9-12)

- Period log entry
- Medication log entry
- Conversation history
- Hybrid search
- Integration with Appointment Prep

### Phase 4: Polish & Launch (Weeks 13-15)

- Legal review
- User testing
- Deployment
- Documentation
- V2 launch! 🚀

---

## Success Metrics for Each Release

### V2 Success

- Users can prepare for appointments in <15 minutes
- 80%+ of users find Appointment Prep useful in feedback
- Period/medication logging has >50% adoption among relevant users
- No regression in existing features (symptom tracking, Ask Meno)

### V3 Success

- Users report actionable insights from trending analysis
- Multi-variable analysis improves Ask Meno response quality
- Map view increases provider search engagement
- Mobile app reaches 30%+ of daily active users

---
