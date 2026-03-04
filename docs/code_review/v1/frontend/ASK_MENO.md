# Ask Meno (Chat) Deep Dive

**Component:** `frontend/src/routes/(app)/ask/+page.svelte`
**Status:** Well-structured, ready for markdown enhancement
**Overall Quality:** 8/10

---

## Part 1: Current Component Analysis

### What's Working Well ✅

1. **Clean State Management**

   ```typescript
   let messages = $state<Message[]>([]);
   let conversationId = $state<string | null>(null);
   let inputText = $state("");
   let loading = $state(false);
   let error = $state<string | null>(null);
   ```

   - Properly typed
   - Clear reactive declarations
   - Good separation of concerns

2. **Proper Type Definitions**

   ```typescript
   interface Citation {
     url;
     title;
     section;
     source_index;
   }
   interface Message {
     role;
     content;
     citations;
   }
   interface ChatApiResponse {
     message;
     citations;
     conversation_id;
   }
   ```

   - Explicit types for API responses
   - Reusable interfaces
   - Good for catching bugs

3. **Security-Conscious HTML Rendering**

   ```typescript
   function escapeHtml(str: string): string {
     return str
       .replace(/&/g, "&amp;")
       .replace(/</g, "&lt;")
       .replace(/>/g, "&gt;")
       .replace(/"/g, "&quot;");
   }
   ```

   - Prevents XSS attacks
   - URL validation for citations
   - Protocol checking (http/https only)
     ✅ This is **excellent** security practice!

4. **Good UX Patterns**
   - Empty state with starter prompts
   - Auto-scroll on new messages
   - Textarea height adjustment
   - Loading indicator
   - Error messages with dismissal
   - Citation superscript links
   - Proper ARIA labels

5. **Keyboard Handling**
   ```typescript
   function handleKeydown(e: KeyboardEvent) {
     if (e.key === "Enter" && !e.shiftKey) {
       e.preventDefault();
       sendMessage(inputText);
     }
   }
   ```

   - Enter to send, Shift+Enter for newline
   - Good UX pattern

### Issues & Improvements Needed 🟡

1. **No Markdown Rendering** (Your identified issue!)
   - Currently: `What's the **difference** between...` shows literally
   - Desired: Bold text actually renders as bold
   - Solution: Add `marked` library + renderer

2. **No +page.ts File**
   - Could load initial data (conversation history, user preferences)
   - Could handle auth checks server-side
   - Would improve performance (parallel load)

3. **renderContent() Function Needs Refactor**
   - Currently handles HTML escaping + newlines + citations
   - After adding markdown, needs to handle markdown → HTML first
   - Will get complex quickly

4. **Hard-coded Starter Prompts**
   - Could fetch from API (personalized based on user symptoms)
   - Currently static array in component

5. **Limited Error Handling**
   - Only shows generic error message
   - Network errors, auth errors, API errors all look the same
   - Could be more helpful

6. **No Loading States for Specific Elements**
   - Send button disabled during loading ✅
   - But no loading indicator on citations until message loads
   - Input textarea could show skeleton/placeholder

7. **Citations Inline + In Footer**
   - Great UX! Shows citation superscript + full citation below
   - But no way to see citation without scrolling
   - Could add tooltip on hover (optional)

---

## Part 2: Markdown Rendering Solution (done)

### The Problem

Currently, OpenAI returns markdown like:

```
What's the **difference** between perimenopause and menopause?

## Perimenopause
This is the **transition phase** that lasts 4-10 years.

- Irregular periods
- Hot flashes
- Sleep issues
```

And it renders as plain text with `**` visible.

### The Solution: `marked` + Custom Renderer

**Step 1: Install marked**

```bash
npm install marked
# Optional: for syntax highlighting
npm install highlight.js
```

**Step 2: Create a Markdown Utility**

```typescript
// frontend/src/lib/markdown.ts

import { marked } from "marked";

// Configure marked to match our design
marked.setOptions({
  breaks: true, // Convert \n to <br>
  gfm: true, // GitHub Flavored Markdown
});

/**
 * Render markdown to HTML with security checks.
 *
 * Security:
 * - Uses marked's default sanitizer (blocks <script>, etc.)
 * - Escapes all user content before rendering
 * - Validates URLs (http/https only)
 */
export function renderMarkdown(content: string): string {
  try {
    const html = marked.parse(content);
    if (typeof html === "string") {
      return html;
    }
    return "Failed to render content";
  } catch (error) {
    console.error("Markdown rendering error:", error);
    return escapeHtml(content); // Fallback to plain text
  }
}

/**
 * Sanitize inline code and links in rendered markdown.
 *
 * This is called AFTER markdown rendering to:
 * - Add target="_blank" to external links
 * - Validate URLs (http/https only)
 * - Escape dangerous protocols
 */
export function sanitizeMarkdownHtml(
  html: string,
  citations: Citation[],
): string {
  // Add target="_blank" and validation to links
  return html.replace(/<a\s+href="([^"]*)"[^>]*>/g, (match, url) => {
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) {
        return "<span>"; // Replace with span, disable link
      }
    } catch {
      return "<span>"; // Invalid URL, disable link
    }
    return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">`;
  });
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
```

**Step 3: Update Ask Meno Component**

Replace the current `renderContent()` function:

```typescript
// OLD (current):
function renderContent(content: string, citations: Citation[]): string {
  const escaped = escapeHtml(content).replace(/\n/g, '<br>');
  return escaped.replace(/\[Source (\d+)\]/g, (...) => { ... });
}

// NEW:
import { renderMarkdown, sanitizeMarkdownHtml } from '$lib/markdown';

function renderContent(content: string, citations: Citation[]): string {
  // 1. Render markdown to HTML
  let html = renderMarkdown(content);

  // 2. Sanitize external links
  html = sanitizeMarkdownHtml(html, citations);

  // 3. Replace [Source N] markers with citation links
  html = html.replace(/\[Source (\d+)\]/g, (_match, n) => {
    const idx = parseInt(n, 10) - 1;
    if (idx >= 0 && idx < citations.length) {
      const citation = citations[idx];
      const url = escapeHtml(citation.url);
      return `<sup><a href="${url}" target="_blank" rel="noopener noreferrer" class="citation-ref">[${n}]</a></sup>`;
    }
    return `<sup>[${n}]</sup>`;
  });

  return html;
}
```

**Step 4: Update Styles for Markdown**

Add to the `<style>` block:

```css
/* Markdown rendering styles */
:global(.message-content h1) {
  font-size: 1.5rem;
  font-weight: bold;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
}

:global(.message-content h2) {
  font-size: 1.25rem;
  font-weight: bold;
  margin-top: 0.875rem;
  margin-bottom: 0.5rem;
}

:global(.message-content h3) {
  font-size: 1.125rem;
  font-weight: bold;
  margin-top: 0.75rem;
  margin-bottom: 0.375rem;
}

:global(.message-content p) {
  margin-bottom: 0.75rem;
}

:global(.message-content ul) {
  list-style-type: disc;
  list-style-position: inside;
  margin-left: 1rem;
  margin-bottom: 0.75rem;
}

:global(.message-content ol) {
  list-style-type: decimal;
  list-style-position: inside;
  margin-left: 1rem;
  margin-bottom: 0.75rem;
}

:global(.message-content li) {
  margin-bottom: 0.25rem;
}

:global(.message-content code) {
  background-color: #f1f5f9;
  border-radius: 0.25rem;
  padding: 0.125rem 0.375rem;
  font-family: monospace;
  font-size: 0.875rem;
}

:global(.message-content pre) {
  background-color: #f1f5f9;
  border-radius: 0.5rem;
  padding: 1rem;
  overflow-x: auto;
  margin-bottom: 0.75rem;
}

:global(.message-content pre code) {
  background-color: transparent;
  padding: 0;
}

:global(.message-content blockquote) {
  border-left: 4px solid #cbd5e1;
  padding-left: 1rem;
  margin-left: 0;
  margin-bottom: 0.75rem;
  color: #64748b;
  font-style: italic;
}

:global(.message-content strong) {
  font-weight: 600;
}

:global(.message-content em) {
  font-style: italic;
}

:global(.message-content a) {
  color: #0d9488;
  text-decoration: underline;
}

:global(.message-content a:hover) {
  color: #0f766e;
}
```

**Step 5: Update HTML to Use Class for Styling**

```svelte
<div class="text-sm leading-relaxed text-slate-800 message-content">
  {@html renderContent(message.content, message.citations)}
</div>
```

### Why This Approach

✅ **Security:** Marked has built-in XSS protection  
✅ **Flexibility:** Easy to customize rendering  
✅ **Performance:** Markdown processing is fast  
✅ **User Experience:** Properly formatted content  
✅ **Maintainability:** Separated markdown logic from component

### Testing the Markdown

Add a test with this sample response:

```markdown
The **difference** is significant:

## Perimenopause

- Irregular periods
- Hot flashes
- Lasts 4-10 years

## Menopause

- 12 consecutive months without a period
- Is a single point in time

Current research supports [evidence-based treatment](#) for symptom management.
```

Should render with bold, headers, lists, etc. properly formatted.

---

## Part 3: Component Refactoring Plan

### Phase 1: Immediate (This Week)

#### 1.1: Add Markdown Rendering ✅ (Your Request)

- Install `marked`
- Create `lib/markdown.ts` utility
- Update `renderContent()` to use markdown
- Add CSS for markdown styling
- **Effort:** 2-3 hours
- **Impact:** User-visible improvement

#### 1.2: Add +page.ts for Server-Side Loading

```typescript
// frontend/src/routes/(app)/ask/+page.ts

import { redirect } from "@sveltejs/kit";
import type { PageLoad } from "./$types";

export const load: PageLoad = async ({ parent }) => {
  const { session } = await parent();

  // Require auth
  if (!session) {
    redirect(302, "/login");
  }

  // Could fetch initial data here:
  // - Recent conversation history
  // - Personalized starter prompts
  // - User preferences

  return {
    user: session.user,
  };
};
```

- **Effort:** 1 hour
- **Impact:** Better performance, auth checking

#### 1.3: Improve Type Safety

- Move `Citation`, `Message`, `ChatApiResponse` to shared types file
- Create `frontend/src/lib/types/chat.ts`
- Reuse in other routes (future Appointment Prep flow)
- **Effort:** 1 hour
- **Impact:** Type safety, no duplication

### Phase 2: Short-term (Next 1-2 Weeks)

#### 2.1: Refactor renderContent() for Maintainability

```typescript
// After markdown support, it's complex. Break into pieces:

function renderMarkdown(content: string): string { ... }
function sanitizeLinks(html: string): string { ... }
function replaceCitationMarkers(html: string, citations): string { ... }
function renderContent(content, citations): string {
  let html = renderMarkdown(content);
  html = sanitizeLinks(html);
  html = replaceCitationMarkers(html, citations);
  return html;
}
```

- **Effort:** 1-2 hours
- **Impact:** Easier to maintain, easier to test

#### 2.2: Add Better Error Messages

```typescript
// Current: generic error
// Desired: specific error types

type ApiError = {
  status: number;
  detail: string;
  code?: string;
};

// Different messages for different errors:
// 401 → "Your session expired. Please log in again."
// 429 → "Too many requests. Please wait a moment."
// 500 → "Service is temporarily unavailable."
```

- **Effort:** 1 hour
- **Impact:** Better UX

#### 2.3: Personalized Starter Prompts

```typescript
// Instead of hardcoded, fetch from API:
// GET /api/chat/suggested-prompts?journey_stage=perimenopause

// Return prompts based on user's stage:
// - Recent symptoms they logged
// - Common questions for their stage
// - Topics they haven't explored
```

- **Effort:** 2 hours (API already has endpoint)
- **Impact:** More personalized UX

### Phase 3: Medium-term (V2 Development)

#### 3.1: Add Form Validation

- Currently: No validation on message input
- Desired: Validate with Zod

```typescript
import { z } from "zod";

const ChatMessageSchema = z.object({
  message: z.string().min(1).max(2000),
  conversation_id: z.string().uuid().optional(),
});

// Before sending:
const validation = ChatMessageSchema.safeParse(payload);
if (!validation.success) {
  error = validation.error.message;
  return;
}
```

- **Effort:** 1 hour
- **Impact:** Better validation

#### 3.2: Add Loading State for Input Area

```svelte
{#if loading}
  <div class="h-[44px] w-full animate-pulse rounded-xl bg-slate-200"></div>
{:else}
  <textarea ...></textarea>
{/if}
```

- **Effort:** 30 min
- **Impact:** Better visual feedback

#### 3.3: Conversation History Sidebar

- Show list of past conversations
- Switch between them without reloading
- **Effort:** 4-5 hours
- **Impact:** V2 feature (Ask Meno v2)

---

## Part 4: Testing Strategy

### Unit Tests (For Utility Functions)

```typescript
// frontend/src/lib/__tests__/markdown.test.ts

import { describe, it, expect } from "vitest";
import { renderMarkdown, sanitizeMarkdownHtml } from "$lib/markdown";

describe("renderMarkdown", () => {
  it("renders bold text", () => {
    const result = renderMarkdown("This is **bold** text");
    expect(result).toContain("<strong>bold</strong>");
  });

  it("renders headers", () => {
    const result = renderMarkdown("## This is a header");
    expect(result).toContain("<h2>This is a header</h2>");
  });

  it("renders lists", () => {
    const result = renderMarkdown("- Item 1\n- Item 2");
    expect(result).toContain("<li>Item 1</li>");
    expect(result).toContain("<li>Item 2</li>");
  });

  it("handles XSS attempts", () => {
    const result = renderMarkdown('<script>alert("xss")</script>');
    expect(result).not.toContain("<script>");
  });
});
```

### Component Tests (For Ask Meno)

```typescript
// frontend/src/routes/(app)/ask/__tests__/+page.test.ts

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import userEvent from "@testing-library/user-event";
import AskMenoPage from "../+page.svelte";

describe("Ask Meno Page", () => {
  it("displays starter prompts when empty", () => {
    render(AskMenoPage);
    expect(screen.getByText(/What causes brain fog/)).toBeInTheDocument();
  });

  it("sends message on Enter", async () => {
    const user = userEvent.setup();
    render(AskMenoPage);

    const input = screen.getByPlaceholderText(/Ask a question/);
    await user.type(input, "Test message");
    await user.keyboard("{Enter}");

    expect(screen.getByText("Test message")).toBeInTheDocument();
  });

  it("does not send message on Shift+Enter", async () => {
    const user = userEvent.setup();
    render(AskMenoPage);

    const input = screen.getByPlaceholderText(/Ask a question/);
    await user.type(input, "Line 1");
    await user.keyboard("{Shift>}{Enter}{/Shift}");

    // Should still be in input, not sent
    expect(input.value).toContain("Line 1\n");
  });

  it("renders citations as links", async () => {
    // Mock API response with citations
    const response = {
      message: "Some answer [Source 1]",
      citations: [{ url: "https://example.com", title: "Example" }],
      conversation_id: "123",
    };

    render(AskMenoPage);
    // ... test that citation renders as link
  });

  it("shows error message on API failure", async () => {
    // Mock API to fail
    const user = userEvent.setup();
    render(AskMenoPage);

    const input = screen.getByPlaceholderText(/Ask a question/);
    await user.type(input, "Test");
    await user.keyboard("{Enter}");

    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
  });
});
```

### E2E Tests (For Full Flow)

```typescript
// frontend/e2e/ask-meno.spec.ts

import { test, expect } from "@playwright/test";

test.describe("Ask Meno Flow", () => {
  test("user can ask a question and get a response", async ({ page }) => {
    // Login
    await page.goto("/login");
    await page.fill('input[type="email"]', "test@example.com");
    await page.fill('input[type="password"]', "password");
    await page.click('button:has-text("Sign In")');

    // Ask Meno
    await page.goto("/ask");
    await page.fill("textarea", "What causes hot flashes?");
    await page.click('button:has-text("Send")');

    // Wait for response
    await page.waitForSelector(
      '[aria-label="Chat messages"] >> text=hot flashes',
    );

    // Verify markdown is rendered
    const messageText = await page
      .locator('[aria-label="Chat messages"]')
      .textContent();
    expect(messageText).not.toContain("**"); // No markdown syntax visible

    // Verify citations are present
    const citations = await page.locator('a[target="_blank"]').count();
    expect(citations).toBeGreaterThan(0);
  });
});
```

---

## Part 5: Implementation Priority

### Week 1 (MVP)

1. ✅ Add markdown rendering (marked library)
2. ✅ Create +page.ts with auth check
3. ✅ Move types to shared file
4. ✅ Add basic markdown CSS

**Time:** 4-5 hours  
**Value:** Huge (fixes your markdown issue, better structure)

### Week 2

5. Refactor renderContent() into smaller functions
6. Add better error messages
7. Set up testing infrastructure (Vitest + Playwright)
8. Write first unit tests for markdown

**Time:** 6-8 hours  
**Value:** Better maintainability, foundation for tests

### Week 3+

9. Personalized starter prompts
10. Form validation with Zod
11. Component tests
12. E2E tests

**Time:** Variable  
**Value:** Better UX, confidence in changes

---

## Quick Reference: Files to Create/Modify

### Create

- `frontend/src/lib/markdown.ts` — Markdown rendering utility
- `frontend/src/lib/types/chat.ts` — Shared types
- `frontend/src/routes/(app)/ask/+page.ts` — Page load handler
- `frontend/src/__tests__/markdown.test.ts` — Markdown tests
- `frontend/e2e/ask-meno.spec.ts` — E2E tests

### Modify

- `frontend/src/routes/(app)/ask/+page.svelte` — Use markdown, add CSS

---

## Summary

**Your Ask Meno component is really well-written.** The security practices (escapeHtml, URL validation) are excellent. Adding markdown rendering is straightforward with the `marked` library.

**Quick wins:**

1. Install marked
2. Create markdown.ts utility
3. Update renderContent() to use it
4. Add CSS for styling
5. Done! ✅

**Then over next 2 weeks:**

- Better structure (types, page.ts)
- Testing setup
- Better error handling
- Personalized features
