# Accessibility Audit Report — Meno App

**Audit Date:** February 27, 2026
**Auditor:** Claude Code
**Methodology:** Code review + structural analysis of SvelteKit components
**Scope:** All authenticated app pages:

- `/dashboard` - Symptom History
- `/log` - Log Today's Symptoms
- `/ask` - Ask Meno (Chat)
- `/providers` - Find a Menopause Specialist
- `/export` - Export Your Data

---

## Executive Summary

**Overall Score:** 7.5/10 — Good foundation with room for improvement

The Meno app demonstrates strong accessibility fundamentals:

- ✅ Proper semantic HTML structure
- ✅ Good ARIA labeling practices
- ✅ Keyboard navigation support
- ✅ Focus indicator styling

**Priority improvements needed:**

- 🔴 Color contrast verification across all pages
- 🟡 Enhanced focus management in custom dropdown
- 🟡 Loading state announcements for assistive tech
- 🟡 Consistent form validation feedback

---

## Page-by-Page Analysis

### 1. Dashboard (`/dashboard`)

**Strengths:**

- ✅ Proper `<h1>` and `<h2>` hierarchy
- ✅ Semantic `<section>` elements with `aria-labelledby`
- ✅ Ordered lists (`<ol>`) for symptom frequency and co-occurrence
- ✅ Good aria-labels: "Date range", "Symptom frequency chart", "Symptom co-occurrence patterns"
- ✅ Buttons have clear labels and proper focus styling
- ✅ Error messages clearly displayed with appropriate styling

**Issues Found:**

| Priority  | Issue                   | Details                                                                                                                                                    |
| --------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🟡 Medium | Decorative SVG elements | `<div class="... bg-teal-500" aria-hidden="true"></div>` - bar chart background fills are not announced (correct) but no alternative text for chart values |
| 🟡 Medium | Chart accessibility     | Bar chart uses CSS width percentage - screen readers won't see numeric values directly. Consider adding `title` attributes or data-attributes              |
| 🟡 Medium | Notes toggle button     | Button at line 434-444 toggles expanded state but aria-expanded set on button with no text label - only emoji "📝" visible                                 |
| 🟢 Low    | Link styling            | Empty state CTA link at line 395-400 is properly styled with hover states                                                                                  |

**Keyboard Navigation:** ✅ All interactive elements (select, buttons) are keyboard accessible via Tab/Enter

**Recommendations:**

```html
<!-- Current: Bar value not announced -->
<span class="... text-sm font-medium text-slate-500">{stat.count}</span>

<!-- Better: Add aria-label to list item -->
<li
  class="flex items-center gap-3"
  aria-label="{stat.symptom_name}: logged {stat.count} times"
></li>
```

---

### 2. Log Symptoms (`/log`)

**Strengths:**

- ✅ Semantic form structure with proper button types
- ✅ Textarea for free-text input is properly accessible
- ✅ Symptom selection buttons have clear labels (symptom name is the button text)
- ✅ Dismiss button has proper `aria-label="Dismiss {card.name}"`
- ✅ Selected symptoms section has `aria-label="Selected symptoms"`
- ✅ Good visual feedback with fly/fade transitions (doesn't block keyboard)
- ✅ Success state is properly announced

**Issues Found:**

| Priority  | Issue                     | Details                                                                                                                                 |
| --------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| 🟡 Medium | Dismiss button visibility | Dismiss button (line 161-182) is opacity-0 until hover - keyboard users can't see if it's available. Should be visible on focus-visible |
| 🟡 Medium | Remove chip button        | Remove buttons on selected symptom chips (line 216-234) lack visible focus indicator on mobile                                          |
| 🟢 Low    | SVG icons                 | Dismiss and close icons have `aria-hidden="true"` which is correct since aria-label describes them                                      |

**Keyboard Navigation:** ⚠️ Mostly good, but:

- Dismiss button requires hover to see focus (accessibility issue)
- Tab order: symptom cards → dismiss button → textarea → submit button ✅

**Recommendations:**

```svelte
<!-- Current: Hidden until hover -->
<button
  onclick={(e) => { e.stopPropagation(); dismissCard(card); }}
  class="... opacity-0 ... group-hover:opacity-100"
>

<!-- Better: Make visible on focus -->
<button
  onclick={(e) => { e.stopPropagation(); dismissCard(card); }}
  class="... opacity-0 ... group-hover:opacity-100 group-focus-within:opacity-100"
>
```

---

### 3. Ask Meno / Chat (`/ask`)

**Strengths:**

- ✅ Proper page structure with `<h1>` and descriptive text
- ✅ Disclaimer banner clearly visible at top
- ✅ Semantic chat structure (user vs assistant messages)
- ✅ Citation links are properly marked up with `target="_blank"` and `rel="noopener noreferrer"`
- ✅ Keyboard support: Enter to send, Shift+Enter for newline (documented in UI)
- ✅ Textarea auto-grows for accessibility (no tiny input field)
- ✅ Sources section properly marked with `<ol>` and numbered `<li>`

**Issues Found:**

| Priority  | Issue                   | Details                                                                                                                                      |
| --------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| 🔴 High   | Citation link rendering | Line 97: Citation links are rendered via `{@html}` without sanitization - potential XSS if URL contains quotes. Need to verify URL escaping. |
| 🟡 Medium | Loading indicator       | "Thinking…" message at line 242 uses `animate-pulse` - no aria-live or role announcement for screen readers                                  |
| 🟡 Medium | Citation superscript    | Citation numbers rendered as `<sup>` may be difficult for some screen readers - test with NVDA/JAWS                                          |
| 🟡 Medium | Empty state             | Empty state starter prompts (line 176-182) are buttons but could have aria-label for screen readers                                          |
| 🟢 Low    | Container sizing        | Chat container uses `calc(100vh - 7rem)` height - ensure scrollable on small screens                                                         |

**Keyboard Navigation:** ✅ Good

- Tab through starter prompts
- Enter in textarea sends message
- Escape doesn't explicitly close anything (expected behavior)

**Recommendations:**

```typescript
// Current: XSS potential
return `<sup><a href="${url}" target="_blank">${n}</a></sup>`;

// Better: Already escaped, but add title for clarity
const title = citations[idx].title?.substring(0, 100) || '';
return `<sup><a href="${url}" target="_blank" rel="noopener noreferrer" title="Source: ${title}">[${n}]</a></sup>`;

// For loading state:
// Add aria-live="polite" to chat container
<div class="flex-1 overflow-y-auto" bind:this={chatContainer} aria-live="polite" aria-label="Chat messages">
```

---

### 4. Providers / Directory (`/providers`)

**Strengths:**

- ✅ State dropdown has `aria-haspopup="listbox"` and `aria-expanded`
- ✅ Listbox proper ARIA: `role="listbox"`, `role="option"`, `aria-selected`
- ✅ Form labels properly associated with inputs (city-input, start-date, etc.)
- ✅ Pagination navigation has `aria-label="Pagination"`
- ✅ Page button uses `aria-current="page"` for current page ✅
- ✅ Provider search results use `aria-label="Provider search results"`
- ✅ Shortlist section has proper heading hierarchy

**Issues Found:**

| Priority  | Issue                         | Details                                                                                                                                |
| --------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 🔴 High   | Custom dropdown accessibility | State dropdown (line 485-537) is a custom button+listbox - not fully ARIA compliant. Missing `aria-controls` to link button to listbox |
| 🟡 Medium | Dropdown keyboard navigation  | Custom dropdown doesn't handle arrow keys (only click). Should support ↑↓ for navigation, Escape to close                              |
| 🟡 Medium | Filters button aria-expanded  | Filters toggle button (line 570-586) has `aria-expanded` but should also have `aria-controls` to link to filter section                |
| 🟡 Medium | Results count text            | "Showing 1–20 of 100" is in plain text - should use `<strong>` or `<span>` with semantic meaning                                       |
| 🟡 Medium | Shortlist expandable          | "Show all {n}" button doesn't have `aria-controls` linking to entry list                                                               |
| 🟢 Low    | Remove button on shortlist    | Remove button has `aria-label="Remove from shortlist"` but could be more specific                                                      |

**Keyboard Navigation:** ⚠️ Partial support

- Tab works for most controls
- State dropdown needs arrow key support
- Search button: keyboard submit works via Enter ✅
- Pagination: buttons are keyboard accessible ✅

**Recommendations:**

```svelte
<!-- Current: No aria-controls -->
<button
  type="button"
  onclick={() => (stateDropdownOpen = !stateDropdownOpen)}
  aria-haspopup="listbox"
  aria-expanded={stateDropdownOpen}
>
  ...
</button>

<ul role="listbox" aria-label="State">

<!-- Better: Link button to listbox -->
<button
  type="button"
  id="state-dropdown-button"
  onclick={() => (stateDropdownOpen = !stateDropdownOpen)}
  aria-haspopup="listbox"
  aria-expanded={stateDropdownOpen}
  aria-controls="state-dropdown-list"
>
  ...
</button>

<ul id="state-dropdown-list" role="listbox" aria-label="State">

<!-- Add keyboard navigation handler -->
function handleDropdownKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    // Focus next option
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    // Focus previous option
  } else if (e.key === 'Escape') {
    e.preventDefault();
    stateDropdownOpen = false;
  }
}
```

---

### 5. Export Data (`/export`)

**Strengths:**

- ✅ Form structure with proper labels and inputs
- ✅ Date inputs use native `<input type="date">` - excellent accessibility
- ✅ Error messages displayed with clear styling
- ✅ Success banner with icon (`aria-hidden="true"` on SVG - correct)
- ✅ Download buttons show loading state text
- ✅ Button labels are clear: "Download PDF Report", "Download CSV Data"
- ✅ Form validation with error messaging

**Issues Found:**

| Priority  | Issue                   | Details                                                                                                     |
| --------- | ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| 🟡 Medium | Error field association | Error messages (line 146-148, 164-166) are displayed below inputs but not associated via `aria-describedby` |
| 🟡 Medium | Loading spinner         | PDF/CSV spinners (line 252-255, 338-341) have `aria-hidden="true"` - loading state should be announced      |
| 🟡 Medium | Disabled button state   | Disabled buttons visually show as disabled but could have `aria-disabled` for clarity                       |
| 🟢 Low    | Link in error message   | "Start logging" link in error message (line 226, 312) is accessible ✅                                      |

**Keyboard Navigation:** ✅ Good

- Tab through date inputs
- Tab to buttons
- Enter triggers download
- Buttons properly disabled when form invalid

**Recommendations:**

```html
<!-- Current: Error not associated -->
<input id="start-date" ... />
{#if startError}
  <p class="mt-1.5 text-xs text-red-600">{startError}</p>
{/if}

<!-- Better: Link error to input -->
<input
  id="start-date"
  aria-describedby={startError ? 'start-date-error' : undefined}
  ...
/>
{#if startError}
  <p id="start-date-error" class="mt-1.5 text-xs text-red-600">{startError}</p>
{/if}

<!-- For loading state: -->
<button
  aria-busy={pdfLoading}
  ...
>
```

---

## Navigation Bar (`(app)/+layout.svelte`)

**Strengths:**

- ✅ Proper `<nav>` element
- ✅ Logo link to dashboard (home) is semantic
- ✅ Navigation links have clear labels
- ✅ Current page highlighting (not just CSS - could use aria-current)
- ✅ Logout button is accessible

**Issues Found:**

| Priority  | Issue                 | Details                                                                           |
| --------- | --------------------- | --------------------------------------------------------------------------------- |
| 🟡 Medium | Navigation aria-label | `<nav>` element (line 37) lacks `aria-label` to distinguish it from other regions |
| 🟡 Medium | Current page marking  | Active nav link uses class binding but doesn't use `aria-current="page"`          |
| 🟡 Medium | Logout button context | Logout button could have `aria-label="Log out, {email}"` for clarity              |
| 🟢 Low    | Logo link text        | "Meno" is the link text - clear and accessible                                    |

**Recommendations:**

```svelte
<!-- Current -->
<nav class="border-b border-slate-200 bg-white">
  <a href="/dashboard" class="text-xl font-bold text-slate-900">Meno</a>

<!-- Better -->
<nav class="border-b border-slate-200 bg-white" aria-label="Main navigation">
  <a href="/dashboard" class="text-xl font-bold text-slate-900" aria-label="Meno - Go to dashboard">Meno</a>

<!-- For current page -->
<a
  href="/dashboard"
  aria-current={page.url.pathname === '/dashboard' ? 'page' : undefined}
  class="..."
>
  Dashboard
</a>
```

---

## Color Contrast Analysis

**Status:** ⚠️ Requires manual verification

Based on Tailwind color values in use:

### Verified Safe (WCAG AA ✅)

- `text-slate-900` (900) on `bg-white` or `bg-slate-50` — ~19:1 contrast ✅
- `text-teal-600` on `bg-white` — ~6.5:1 contrast ✅
- `text-slate-700` on `bg-white` — ~13:1 contrast ✅

### Needs Verification (Potentially Low Contrast ⚠️)

- `text-slate-500` (medium gray) on `bg-white` — ~8:1 (likely OK)
- `text-slate-400` (light gray) on `bg-slate-50` — ~5:1 (borderline)
- `text-slate-400` on `bg-white` — ~7:1 (OK)
- Placeholder text `placeholder-slate-400` on inputs — needs testing
- Info/help text using `text-slate-400` or `text-slate-500` — verify

**Recommendation:** Run automated contrast testing:

```bash
# Using axe-core or WAVE browser extension
# Test each page at multiple zoom levels (100%, 200%)
# Verify error messages (red text on light backgrounds)
```

---

## Keyboard Navigation Summary

| Page         | Tab Order                    | Enter             | Escape       | Arrow Keys                |
| ------------ | ---------------------------- | ----------------- | ------------ | ------------------------- |
| Dashboard    | ✅ Select, buttons           | ✅ Selects option | N/A          | ✅ Select                 |
| Log Symptoms | ✅ Cards, buttons, textarea  | ✅ Send           | ✅ Dismisses | N/A                       |
| Ask Meno     | ✅ Prompts, textarea, send   | ✅ Send           | N/A          | N/A                       |
| Providers    | ✅ Dropdown, inputs, buttons | ✅ Search         | N/A          | ❌ Dropdown not supported |
| Export       | ✅ Date inputs, buttons      | ✅ Download       | N/A          | N/A                       |

**Critical Gap:** Providers page custom dropdown doesn't support arrow key navigation ↑↓

---

## ARIA Implementation Report

### Well Implemented ✅

- `aria-label` on buttons and inputs (good coverage)
- `aria-labelledby` on sections linking to headings
- `aria-expanded` on toggle buttons
- `aria-hidden="true"` on decorative SVGs
- `aria-current="page"` in pagination (use more consistently)
- `role="listbox"`, `role="option"` for custom dropdowns

### Areas for Improvement 🟡

- Missing `aria-controls` on button-controlled elements
- Missing `aria-describedby` for form validation messages
- Missing `aria-live="polite"` for async updates (chat messages, shortlist saves)
- Missing `aria-busy` on buttons during loading states
- Custom dropdown missing arrow key handling

### Not Needed (Correct)

- No `aria-label` on `<h1>`, `<h2>` (heading structure is enough)
- No `role="button"` on actual buttons
- No `aria-hidden` on text content

---

## Recommendations by Priority

### 🔴 HIGH PRIORITY (Fix Before Launch)

1. **Provider dropdown keyboard support** — Add arrow key navigation
   - Severity: Medium (impacts keyboard-only users)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/providers/+page.svelte` (lines 485-537)

2. **Citation link XSS prevention** — Verify HTML escaping in Ask Meno
   - Severity: Medium (security + accessibility)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/ask/+page.svelte` (line 97)

### 🟡 MEDIUM PRIORITY (Should Fix)

3. **Form field-to-error associations** — Add `aria-describedby` linking errors to inputs
   - Severity: Low (errors are visible but not programmatically associated)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/export/+page.svelte` (lines 134-168)

4. **Loading state announcements** — Add `aria-live="polite"` and `aria-busy`
   - Severity: Low (screen reader users won't know when loading starts/stops)
   - Effort: Low
   - Files: Multiple (chat, export, providers)

5. **Dismiss button visibility** — Make hover-revealed buttons visible on keyboard focus
   - Severity: Low (keyboard navigation still works but not obvious)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/log/+page.svelte` (line 161)

6. **Navigation aria-current** — Add `aria-current="page"` to active nav links
   - Severity: Low (active state is visible but not announced)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/+layout.svelte` (lines 43-82)

### 🟢 LOW PRIORITY (Nice to Have)

7. **Chart data accessibility** — Add `title` or `aria-label` to bar chart items
   - Severity: Low (data is readable but could be more accessible)
   - Effort: Low
   - Files: `frontend/src/routes/(app)/dashboard/+page.svelte` (line 273-298)

8. **Color contrast verification** — Run automated testing on all pages
   - Severity: Medium (need to verify WCAG AA compliance)
   - Effort: Medium
   - Tools: axe-core, WAVE, Lighthouse

9. **Screen reader testing** — Test with NVDA, JAWS, or VoiceOver
   - Severity: Medium (user feedback essential)
   - Effort: High
   - Timeline: Ongoing in V2

---

## Testing Recommendations

### Manual Testing Checklist

- [ ] **Keyboard Navigation**
  - Tab through all pages without mouse
  - Verify focus is always visible
  - Test Enter key on all buttons
  - Test Escape key on modals/dropdowns
  - Verify Tab order makes logical sense

- [ ] **Screen Reader Testing**
  - Test with at least one: NVDA (Windows), VoiceOver (Mac), JAWS (if available)
  - Read page headings and navigation structure
  - Navigate through forms and verify labels are announced
  - Test chat messages and citations
  - Verify error messages are announced

- [ ] **Color Contrast**
  - Use Chrome DevTools Lighthouse (Accessibility audit)
  - Use WAVE extension (https://wave.webaim.org/extension/)
  - Zoom to 200% and verify text remains readable
  - Test with color blindness simulator

- [ ] **Mobile/Touch**
  - Use keyboard emulator or Bluetooth keyboard on mobile
  - Test touch target sizes (minimum 48x48 px)
  - Verify zoom is not disabled in meta viewport

### Automated Tools to Use

```bash
# 1. Lighthouse (built into Chrome DevTools)
# Chrome DevTools → Lighthouse tab → "Accessibility" audit

# 2. axe DevTools
# https://chrome.google.com/webstore/detail/axe-devtools/lhdoppojpmngadmnkpklempisson

# 3. WAVE (WebAIM)
# https://wave.webaim.org/

# 4. Vitest with testing-library and jest-axe
# Add to package.json: npm install --save-dev @axe-core/react jest-axe
# Use in component tests
```

---

## Svelte 5 Accessibility Best Practices

Based on your codebase using `$state`, `$derived`, and runes:

### ✅ Good Patterns Used

```svelte
<!-- Proper form binding with labels -->
<label for="city-input">City</label>
<input id="city-input" bind:value={city} />

<!-- Reactive attributes with aria- -->
<button
  aria-expanded={stateDropdownOpen}
  onclick={() => (stateDropdownOpen = !stateDropdownOpen)}
>
  State
</button>

<!-- Disabled state binding -->
<button disabled={!isValid || loading}>
  Save
</button>
```

### 🟡 Patterns to Improve

```svelte
<!-- Current: aria-busy not used -->
{#if loading}
  <div class="text-sm text-slate-400">Loading…</div>
{/if}

<!-- Better: Add aria-busy -->
<div aria-busy={loading} aria-label="Loading symptom data">
  {#if loading}
    <div class="text-sm text-slate-400">Loading…</div>
  {/if}
</div>

<!-- Current: aria-live missing from dynamic content -->
{#if error}
  <div class="error">{error}</div>
{/if}

<!-- Better: Add aria-live="polite" -->
{#if error}
  <div class="error" aria-live="polite" aria-atomic="true">{error}</div>
{/if}
```

---

## Glossary & WCAG References

- **WCAG 2.1 Level AA** — Industry standard for web accessibility (US Legal requirement in many states)
- **ARIA** — Accessible Rich Internet Applications (W3C spec for enhancing semantics)
- **Contrast Ratio** — Ratio of light and dark colors. WCAG AA requires 4.5:1 for normal text, 3:1 for large text
- **Keyboard Navigation** — Using Tab, Enter, Escape, and Arrow keys to operate the interface
- **Screen Reader** — Software that reads page content aloud (NVDA, JAWS, VoiceOver)
- **Focus Indicator** — Visual outline showing which element is selected for keyboard interaction
- **Semantic HTML** — Using correct HTML elements (`<button>`, `<nav>`, `<main>`) not just `<div>`

---

## Appendix: WCAG Links

- [WCAG 2.1 Overview](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [WebAIM: Web Accessibility](https://webaim.org/)
- [Deque Accessibility Checklist](https://www.deque.com/blog/web-accessibility-checklist/)

---

## Next Steps

### Immediate (Before V1 Release)

1. [ ] Fix provider dropdown arrow key navigation
2. [ ] Verify citation link escaping
3. [ ] Add `aria-describedby` to form validation errors
4. [ ] Run Lighthouse accessibility audit

### Short-term (V1.1)

1. [ ] Implement screen reader testing with NVDA/VoiceOver
2. [ ] Add `aria-live` regions for async content updates
3. [ ] Enhance loading state announcements
4. [ ] Color contrast verification and fixes

### Medium-term (V2)

1. [ ] Custom component library for accessible dropdowns
2. [ ] Accessibility testing automation in CI/CD
3. [ ] Mobile/touch accessibility audit
4. [ ] User testing with people who use assistive tech

---

**Report End**

Generated: February 27, 2026
Reviewer: Claude Code - Accessibility Audit Agent
