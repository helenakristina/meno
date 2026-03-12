# Appointment Prep Multi-Step Flow: Code Review

**Date:** March 11, 2026
**Reviewer:** Claude Code (comprehensive analysis)
**Status:** Review only -- no code changes made

---

## 1. Implementation Overview

The Appointment Prep flow is a 5-step wizard that helps users prepare for healthcare appointments by:

1. **Step 1 (Context):** Questionnaire capturing appointment type, goal, dismissal history, and optional urgent symptom
2. **Step 2 (Narrative):** AI-generated symptom narrative (editable by user)
3. **Step 3 (Prioritize):** Drag-and-drop concern prioritization with keyboard alternatives
4. **Step 4 (Scenarios):** AI-generated practice conversation scenarios (read-only)
5. **Step 5 (Generate):** Document generation with download links

### Files Reviewed

| # | File | Lines | Purpose |
|---|------|-------|---------|
| 1 | `+page.svelte` | 201 | Orchestrator / state machine |
| 2 | `+page.server.ts` | 24 | Server-side form init for Step 1 |
| 3 | `Step1Context.svelte` | 180 | Step 1: Context questionnaire |
| 4 | `Step2Narrative.svelte` | 103 | Step 2: AI narrative (editable) |
| 5 | `Step3Prioritize.svelte` | 205 | Step 3: Drag-and-drop priorities |
| 6 | `Step4Scenarios.svelte` | 103 | Step 4: AI practice scenarios |
| 7 | `Step5Generate.svelte` | 141 | Step 5: Document generation |
| 8 | `$lib/types/appointment.ts` | 119 | Types, enums, label maps, defaults |
| 9 | `$lib/schemas/appointment.ts` | 21 | Zod validation schemas |
| 10 | `$lib/types/api.ts` | 355 | API endpoint type mappings |
| 11 | `__tests__/appointment-prep.test.ts` | 421 | Unit tests |
| 12 | `history/+page.svelte` | 152 | History page for past preps |

**No dedicated stores exist.** All state lives in the page component's `$state` object -- appropriate for a page-scoped wizard flow.

---

## 2. Architecture Pattern

```
+page.svelte (Orchestrator)
  |-- Owns AppointmentPrepState ($state)
  |-- Renders active step via {#if state.currentStep === N}
  |-- Manages progress bar, error banner, loading overlay
  |-- Provides callbacks: onNext, onError, onStartOver
  |
  |-- Step1Context.svelte
  |     Uses Superforms + Zod for form validation
  |     Parent handles API call + step advance
  |
  |-- Step2Narrative.svelte
  |     Self-loads via $effect on mount
  |     Manages own loading/error state
  |
  |-- Step3Prioritize.svelte
  |     Drag-and-drop + keyboard reordering
  |     No API call (client-side only)
  |
  |-- Step4Scenarios.svelte
  |     Self-loads via $effect on mount
  |     Manages own loading/error state
  |
  |-- Step5Generate.svelte
       User-triggered API call
       Two-phase UI (pre/post generation)
```

**Key architectural decision:** No store, no context API. State is a single `$state` object in the page component, passed down via props and callbacks. This is clean and appropriate for a linear wizard.

---

## 3. Pattern Consistency Matrix

| Pattern | Step 1 | Step 2 | Step 3 | Step 4 | Step 5 |
|---------|--------|--------|--------|--------|--------|
| API call location | Parent | Self | N/A | Self | Self |
| Loading state | Parent | Self | N/A | Self | Self |
| Error reporting | Parent only | Dual (local + parent) | Parent only | Dual (local + parent) | Self only |
| Data loading trigger | N/A | `$effect` | N/A | `$effect` | User click |
| Validation | Superforms + Zod | Inline (empty check) | Inline (length check) | None | None |
| Form library | Superforms | None | None | None | None |

The inconsistency in API call ownership and error reporting is the most significant pattern divergence.

---

## 4. Strengths

### S1. Clean Component Decomposition
Orchestrator handles state and routing; steps handle UI. Single source of truth for all accumulated data. `startOver()` cleanly resets the entire state object.

### S2. Svelte 5 Fully Compliant
All files use `$state`, `$derived`, `$props()`, `onclick={}`. No legacy Svelte 4 syntax anywhere.

### S3. Good Accessibility Foundation
- Progress bar: `role="progressbar"` with `aria-valuenow/min/max`
- Error banner: `role="alert"`
- Loading: `role="status"`, `aria-live="polite"`, `aria-busy="true"`
- Step 3: Keyboard alternatives to drag-and-drop (up/down buttons)
- Step 3: `aria-label` on all buttons includes concern text
- Step 1: `<fieldset>` and `<legend>` for semantic radio groups
- Step 5: `aria-hidden="true"` on decorative checkmark

### S4. Type Safety Infrastructure
- Enums for appointment types, goals, dismissal states
- Label maps decouple display strings from enum values
- `AppointmentPrepState` uses literal union `1 | 2 | 3 | 4 | 5` for step
- Centralized API endpoint type definitions

### S5. Responsive Design
- Consistent `max-w-2xl` centering across all steps
- `px-4 sm:px-6 lg:px-8` responsive padding
- `flex-col sm:flex-row` for button groups in Step 5
- Overflow handling on scrollable content

### S6. DRY Configuration
- `DEFAULT_CONCERNS` per goal eliminates hardcoded values
- `STEP_TITLES` centralizes step naming
- Enum iteration via `Object.values()` for radio groups

### S7. User-Friendly AI Integration
- AI disclaimer on Step 2 ("AI-generated -- review and edit")
- Editable narrative allows user agency
- Retry buttons on error states

---

## 5. Weaknesses and Concerns

### Critical (Must Fix)

**W1. Tests reference non-existent enum values.**
The test file references `AppointmentGoal.understand_where_i_am`, `AppointmentGoal.discuss_starting_hrt`, and `AppointmentGoal.address_specific_symptom`. The actual enum only has `assess_status`, `explore_hrt`, `optimize_current_treatment`, and `urgent_symptom`. These tests will fail to compile or throw runtime errors. The enum values were likely renamed and the tests not updated.

**W2. `urgent_symptom` missing from API type definition.**
The `+page.svelte` handler sends `urgent_symptom` in the POST body, but the API type definition for `/api/appointment-prep/context` does not include it. The field is sent but not type-checked.

### High (Should Fix)

**W3. No state persistence across page reloads.**
If the user refreshes at Step 3, all state is lost. They restart at Step 1. For a flow that includes LLM calls (potentially 30+ seconds of work), this is a significant UX risk. Consider `sessionStorage` or server-side persistence.

**W4. Double error reporting in Steps 2 and 4.**
When API calls fail, both a local `loadError` state AND the parent's `onError()` callback are triggered. This shows two error indicators simultaneously: the parent's error banner and the step's local error div.

**W5. Touch targets below 44px in Step 3.**
Up/down reorder buttons and remove buttons use `h-8 w-8` (32x32px), below the project's own 44px minimum standard. Per CLAUDE.md: "All interactive elements minimum 44x44px (`min-h-11`)."

**W6. Schema doesn't enforce conditional `urgent_symptom` requirement.**
When `goal === 'urgent_symptom'`, the urgent symptom text should be required, but the Zod schema makes it always optional. Conditional validation only exists in the UI (`canSubmit` check).

### Medium

**W7. Dead code in `+page.server.ts`.**
The `actions` export defines a server action `context` that validates the form, but Step 1 submits via `apiClient.post()` from the client. The action is never used.

**W8. Missing `aria-describedby` and `aria-required` in Step 1.**
Error messages exist with `id` attributes but radio inputs don't reference them via `aria-describedby`. Second and third error messages lack `id` entirely. Required fields lack `aria-required="true"`.

**W9. `$effect` used where `onMount` is more appropriate.**
Steps 2 and 4 use `$effect(() => { loadData(); })` to trigger API calls on mount. `$effect` fires on every reactive dependency change, not just mount. Currently safe because no reactive dependencies are read, but fragile if someone adds one later. `onMount` is semantically correct here. (The history page correctly uses `onMount`.)

**W10. Fragile `as` type assertions for dynamic API paths.**
Every API call with a dynamic ID (Steps 2, 3, 4, 5) requires a cast like:
```typescript
`/api/appointment-prep/${id}/narrative` as '/api/appointment-prep/{id}/narrative'
```
If the API type definition path changes, these assertions silently pass with incorrect types. Consider a path builder utility.

**W11. No confirmation before "Start over" in Step 5.**
If a user accidentally clicks "Start over," they lose all work without warning.

**W12. `prioritizeSchema` defined but never used.**
The schema exists and validates `concerns.min(1)`, but Step 3 does inline validation only (`concerns.length === 0`). Duplicated validation logic.

**W13. `STEP_TITLES` key type too broad.**
Uses `Record<number, string>` instead of `Record<1|2|3|4|5, string>`, allowing `STEP_TITLES[99]` without a type error.

**W14. History page loading/error states lack ARIA attributes.**
Loading is plain text "Loading..." with no spinner, no `role="status"`, no `aria-live`. Error state lacks `role="alert"`. Other components in the flow use proper attributes.

### Low

**W15. Magic number `7rem` in height calculation.**
`style="height: calc(100vh - 7rem)"` breaks silently if the app shell header height changes.

**W16. Unusual `$derived(() => ...)` pattern in Step 1.**
`canSubmit` is defined as `$derived(() => { ... })` returning a function that must be called as `canSubmit()`. Standard `$derived` returns a value. This works but may confuse maintainers.

**W17. No character limit on narrative textarea.**
A user could clear to a single character or paste enormous text. Neither is handled.

**W18. No maximum concern count in Step 3.**
Users can add unlimited concerns, potentially overwhelming the API.

**W19. Step 4 scenarios are read-only.**
Unlike Step 2 (editable) and Step 3 (reorderable), Step 4 offers no user agency. Consider allowing dismissal or flagging.

**W20. Download links open in new tab rather than triggering download.**
Consider adding `download` attribute to anchor tags.

**W21. No live region announcements for drag-and-drop operations.**
Drag-and-drop reorders produce no `aria-live` announcements.

**W22. No timeout handling or cancellation on LLM API calls.**
Steps 2 and 4 make calls that could take 10-30 seconds. Clicking "Back" during generation discards the response but doesn't cancel the request.

---

## 6. Questions for Decision

1. **Should wizard progress persist across refreshes?** (`sessionStorage`, server-side, or accept the current behavior?)

2. **Should Steps 2 and 4 use `onMount` instead of `$effect`?** This is a minor change but improves correctness and readability.

3. **Should all steps use Superforms, or should Step 1 be simplified to match the other steps?** Currently only Step 1 uses Superforms + Zod. The inconsistency adds complexity without clear benefit since the client-side `apiClient.post()` bypasses the server action anyway.

4. **Should the dynamic API path casting be addressed with a path builder?** This would eliminate the fragile `as` assertions across all steps. Example:
   ```typescript
   apiClient.get(apiPath('appointment-prep', id, 'narrative'))
   ```

5. **Is the test file actively run in CI?** If so, the non-existent enum value references (W1) are blocking. If not, should it be added to CI?

6. **Should Step 4 scenarios allow user interaction** (dismiss, flag, reorder), or is read-only acceptable?

---

## 7. Recommendation

**Verdict: Standardize with targeted fixes.**

The core architecture is sound. The orchestrator + step component pattern with callback props is clean, maintainable, and appropriate for a linear wizard. The Svelte 5 compliance is excellent throughout.

**Do not rework.** The patterns work. Focus on:

### Priority 1: Fix broken tests (W1)
Update test enum references to match actual `AppointmentGoal` values. This is likely a 15-minute fix but blocks CI.

### Priority 2: Fix API type gap (W2)
Add `urgent_symptom` to the API type definition for the context endpoint.

### Priority 3: Unify error reporting (W4)
Choose one pattern: either steps report errors to the parent (via `onError`) and the parent shows them, OR steps show errors locally. Not both. Recommend: steps show errors locally (they have better context for retry buttons), parent only shows errors for Step 1 (which it handles directly).

### Priority 4: Fix touch targets (W5)
Change `h-8 w-8` to `h-11 w-11` or `min-h-11 min-w-11` on Step 3 buttons.

### Priority 5: Consider state persistence (W3)
For V2, add `sessionStorage` persistence of `AppointmentPrepState`. On mount, check for saved state and offer to resume. This is the highest-impact UX improvement.

### Defer
- Path builder utility (W10) -- address when the API client is next refactored
- `$effect` to `onMount` (W9) -- low risk, do during any Step 2/4 changes
- Start-over confirmation (W11) -- add when doing UX polish pass
- Superforms consistency (Q3) -- defer until magic link auth migration changes form patterns

---

## 8. Comparison to Best Practices

### What This Flow Does Well (vs. typical wizard implementations)

- **Single state object** instead of scattered stores -- simpler mental model
- **Guard clauses in rendering** prevent rendering steps with missing prerequisites
- **Keyboard alternatives to drag-and-drop** -- most wizard implementations skip this
- **AI disclaimer and editability** -- responsible AI pattern
- **Centralized type definitions** -- most projects scatter these across components

### What Typical Best Practices Would Add

- **URL-based step tracking** (`/appointment-prep?step=3`) for bookmark/share/refresh support
- **Step validation before advancing** -- currently only Step 1 validates with a schema
- **Cancel/save-as-draft capability** -- especially important for flows with LLM-generated content
- **Animated transitions** between steps for visual continuity
- **Step summary/review** before final generation -- a "review all your choices" step

### Comparison to CLAUDE.md Standards

| Standard | Compliance | Notes |
|----------|-----------|-------|
| Svelte 5 runes | Full | All files use `$state`, `$derived`, `$props()` |
| `onclick` not `on:click` | Full | Correct throughout |
| Touch targets 44px | Partial | Step 3 buttons below minimum |
| `aria-describedby` on errors | Partial | Step 1 missing associations |
| `aria-required` on required fields | Missing | Step 1 radio groups |
| Responsive padding | Full | `px-4 sm:px-6 lg:px-8` throughout |
| No horizontal scroll | Full | `max-w-2xl` prevents overflow |
| API client usage | Full | All calls through `apiClient` |
| Error handling try/catch | Full | All async operations wrapped |

---

## 9. Summary

The Appointment Prep flow is a well-structured implementation with strong Svelte 5 compliance and a clean architectural decomposition. The main issues are:

1. **Broken tests** (critical, likely quick fix)
2. **API type gap** (critical, one-line fix)
3. **Inconsistent error reporting** (high, pattern decision needed)
4. **Accessibility gaps** (medium, touch targets and ARIA attributes)
5. **No state persistence** (high impact UX, but acceptable for V1)

The patterns are worth standardizing as-is, with the targeted fixes above. No architectural rework is needed.
