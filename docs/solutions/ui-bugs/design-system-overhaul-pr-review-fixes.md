---
title: "Design system overhaul: 12 PR review fixes (TODOs 072–083)"
category: ui-bugs
date: 2026-03-25
tags:
  [
    design-system,
    wcag,
    accessibility,
    security,
    tailwind,
    shadcn,
    css-tokens,
    xss,
    api-client,
  ]
pr: "10"
branch: feat/frontend-design-system-overhaul
---

# Design System Overhaul: PR Review Fixes

After the 29-file design token migration (PR #10), code review agents identified 12 issues.
Documented here for future reference — especially the non-obvious ones.

---

## 1. shadcn `accent` collision with custom coral scale

**Problem:** `bg-accent` (shadcn semantic, blue-gray hover) and `bg-accent-100`…`bg-accent-900`
(Meno coral/orange scale) shared the same `accent` prefix. A developer reading `hover:bg-accent`
in `button.svelte` and `bg-accent-400` in `PeriodCalendar.svelte` would assume they're related —
they're in completely different hue families.

**Fix:** Rename the custom coral scale to `coral-*` everywhere.

In `layout.css`:

```css
/* Before */
--color-accent-50: #fff7ed;
--color-accent-400: #fb923c;

/* After */
--color-coral-50: #fff7ed;
--color-coral-400: #fb923c;
```

Update usages in: `PeriodCalendar.svelte`, `PeriodLogModal.svelte`, `CallingScriptModal.svelte`,
`providers/+page.svelte`. Do NOT rename bare `bg-accent` / `hover:bg-accent` — those are shadcn tokens.

**Prevention:** When adding a custom color scale alongside shadcn, always use a name that cannot
be confused with shadcn's semantic token names (`accent`, `muted`, `card`, `popover`, etc.).

---

## 2. WCAG AA contrast: primary-600 fails on white (~3.1:1, needs 4.5:1)

**Problem:** `primary-600` (`#0d9478`) on white achieves ~3.1:1. WCAG AA requires 4.5:1 for normal
text. The near-navy `--primary` it replaced would have passed.

**Fix:** Use `primary-800` (`#115e50`, ~7.0:1) for all text uses.

```svelte
<!-- Before -->
<span class="text-primary-600">Active</span>
<a class="text-primary-600 hover:text-primary-800">Citation</a>

<!-- After -->
<span class="text-primary-800">Active</span>
<a class="text-primary-800 hover:text-primary-900">Citation</a>
```

Reserve `primary-500/600` for background fills (buttons, chips, progress bars) where the
white-on-teal contrast is evaluated differently.

**Rule:** After any primary color change, verify contrast with Chrome DevTools accessibility
audit before merging. `primary-800` is the safe floor for text on white.

---

## 3. Hardcoded hex in `<style>` blocks defeats the token system

**Problem:** `ask/+page.svelte` style block had `color: #0d9478` (primary-600) hardcoded.
Necessary for `:global()` styles injected via `{@html}`, but hex bypasses tokens entirely.

**Fix:** Use CSS custom properties instead:

```css
/* Before */
.citation-ref {
  color: #0d9478;
}

/* After */
.citation-ref {
  color: var(--color-primary-800);
}
```

**Prevention:** Even in `<style>` blocks, always use `var(--color-*)`. The `@theme inline` block
in `layout.css` exposes all tokens as CSS custom properties available everywhere.

---

## 4. `role="menu"` without keyboard navigation (ARIA violation)

**Problem:** Profile dropdown used `role="menu"` + `role="menuitem"` but had no `ArrowDown/Up`,
`Escape`, `Home/End` keyboard handling. This is a WCAG 4.1.2 violation — worse than no role,
because screen readers announce a broken widget.

**Fix:** Remove the roles entirely. Plain `<a>` and `<button>` in a `<div>` are keyboard-reachable
via Tab with no ARIA needed. Add proper ARIA menu behavior only when you implement full keyboard nav.

**Prevention:** Don't add ARIA roles speculatively. `role="menu"` requires the full keyboard
interaction pattern per ARIA Authoring Practices. If you can't ship the keyboard behavior,
don't ship the role.

---

## 5. Dead CSS token groups (sidebar, chart, bg-\*)

**Problem:** `layout.css` contained ~44 lines of shadcn scaffold boilerplate (`--sidebar-*`,
`--chart-1..5`, `--color-bg-page/card/subtle/overlay`) with zero references in any component.

**Fix:** Delete them. Verify first:

```bash
grep -r "sidebar\|chart-[1-5]\|bg-bg-" frontend/src --include="*.svelte" --include="*.ts"
```

**Prevention:** When adding shadcn components, audit the generated CSS and remove token groups
for features you aren't using (sidebar, chart, etc.).

---

## 6. Raw `fetch` with hardcoded `localhost:8000` in onboarding

**Problem:** `onboarding/+page.svelte` had `const API_BASE = 'http://localhost:8000'` and a
manual `fetch()` call. Silently fails on staging/production. CLAUDE.md is explicit: always
use `apiClient`.

**Fix:**

```typescript
// Before
const response = await fetch(`${API_BASE}/api/users/onboarding`, { ... });

// After
import { apiClient } from '$lib/api/client';
const data = await apiClient.post('/api/users/onboarding', { ... });
```

Also add the endpoint to `$lib/types/api.ts` `ApiEndpoints` for compile-time safety.

**Prevention:** `grep -r "localhost" frontend/src` in CI would catch this class of bug.

---

## 7. DOMPurify for marked output (`{@html}`)

**Problem:** `renderMarkdown()` piped through `marked` then a custom sanitizer. `marked`
explicitly does not sanitize and recommends DOMPurify. LLM output can contain adversarial
content via prompt injection.

**Fix:**

```bash
npm install dompurify @types/dompurify
```

```typescript
import DOMPurify from "dompurify";

const DOMPURIFY_CONFIG = {
  ALLOWED_TAGS: [
    "p",
    "a",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "code",
    "pre",
    "sup",
    "br",
    "h1",
    "h2",
    "h3",
    "blockquote",
  ],
  ALLOWED_ATTR: ["href", "class", "target", "rel", "data-citation-id"],
} as Record<string, unknown>; // types/dompurify ESM compat workaround

export function renderMarkdown(content: string): string {
  const raw = marked.parse(content) as string;
  return DOMPurify.sanitize(raw, DOMPURIFY_CONFIG);
}
```

Apply in `renderMarkdown`, not at the call site — all callers benefit automatically.
`data-citation-id` must be in `ALLOWED_ATTR` or citation links break.

---

## 8. ChatRequest.message needs max_length

**Problem:** No length constraint = unbounded LLM input cost + prompt injection amplification.

**Fix:**

```python
message: str = Field(description="The user's question", min_length=1, max_length=2000)
```

Pydantic returns 422 automatically. Pair with a test:

```python
def test_chat_request_rejects_message_over_2000_chars():
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 2001, ...)
```

---

## 9. components.json CSS path

**Problem:** `components.json` had `"css": "src/app.css"` (file doesn't exist) and
`"baseColor": "slate"`. Future `shadcn-svelte add <component>` would silently break
design token injection and generate cool-gray defaults.

**Fix:**

```json
{
  "css": "src/routes/layout.css",
  "baseColor": "stone"
}
```

---

## Files Changed

| File                                             | Change                                          |
| ------------------------------------------------ | ----------------------------------------------- |
| `layout.css`                                     | Coral rename, dead token removal (44 lines)     |
| `+layout.svelte` (app)                           | WCAG text colors, ARIA role removal             |
| `ask/+page.svelte`                               | WCAG text colors, hex → CSS vars in style block |
| `PeriodCalendar/LogModal.svelte`                 | accent → coral                                  |
| `CallingScriptModal/providers`                   | accent → coral                                  |
| `SkeletonLoader/LoadingSpinner/ProviderSkeleton` | slate → neutral                                 |
| `onboarding/+page.svelte`                        | raw fetch → apiClient                           |
| `markdown.ts`                                    | DOMPurify added                                 |
| `chat.py`                                        | max_length=2000, min_length=1                   |
| `components.json`                                | CSS path + baseColor                            |
| `ErrorBanner.svelte`                             | New shared component                            |
| `+layout.svelte` (root)                          | Inter font loading via Google Fonts             |
