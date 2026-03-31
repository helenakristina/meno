# PRD: Meno Frontend Design System Overhaul

## Summary

Apply the Meno frontend design skill (`frontend-design`) across the entire frontend codebase. Replace all ad-hoc color choices, inconsistent button styles, and random accent colors with the standardized design tokens defined in the skill. Add the Meno logo to the navigation bar.

## Problem

The Meno frontend has accumulated inconsistent styling over months of feature development. Different pages use different button colors (teal, navy, dark blue, red), different link colors, different card styles, and different accent colors. The nav bar displays "Meno" as plain text with no logo. There is no favicon. The app looks like it was built by a different designer on each page.

## Proposed Solution

Systematically update every frontend component and page to use the design tokens defined in the `frontend-design` skill. Add the logo image to the navigation bar. Generate and add a favicon.

## Scope

### In Scope

**Navigation bar:**

- Replace the plain text "Meno" wordmark with the logo image located at `frontend/src/lib/assets/logo.png`
- Logo height should be approximately 32-36px, maintaining aspect ratio
- Display the logo alongside the text "Meno" or standalone — whichever looks cleaner at that size
- Update nav link colors to match the design skill: `text-neutral-600 hover:text-primary-600`, active state `text-primary-600 font-semibold`
- Remove any navy or dark background colors from the nav

**Favicon:**

- Generate a favicon from the logo image (32x32 .ico or .png)
- Generate an Apple touch icon (180x180)
- Add both to the appropriate location in the Next.js/SvelteKit project and reference in the HTML head

**Buttons — global:**

- Primary buttons: `bg-primary-500 text-white hover:bg-primary-600 rounded-md px-4 py-2 font-semibold text-sm`
- Secondary buttons: `border border-neutral-300 text-neutral-700 hover:bg-neutral-50 rounded-md px-4 py-2 font-semibold text-sm`
- Danger buttons (delete/remove only): `bg-danger text-white hover:bg-danger-dark`
- Ghost buttons: `text-primary-500 hover:bg-primary-50`
- Remove ALL navy, dark blue, or dark background buttons throughout the app
- The "Log period" button on the Cycles page should use primary teal, not the current red

**Cards — global:**

- Standardize to: `bg-white border border-neutral-200 rounded-lg p-6`
- Interactive cards get: `hover:border-primary-300 hover:shadow-sm transition-all`
- Remove any colored card backgrounds unless they are semantic callouts (warning, info)

**Status badges (Providers page):**

- "Booked Appointment": `bg-primary-100 text-primary-800`
- "To Call": `bg-accent-100 text-accent-800`
- "Left Voicemail": `bg-warning-light text-warning-dark`
- All badges: `px-2.5 py-0.5 rounded-full text-xs font-medium`

**Charts and data visualization (Dashboard):**

- Symptom frequency bars: use `primary-400` or `primary-500` consistently
- Remove any off-palette chart colors

**Links — global:**

- All links: `text-primary-600 hover:text-primary-700`
- No blue links, no navy links, no inconsistent link colors between pages

**Forms — global:**

- Input borders: `border-neutral-300 focus:border-primary-500 focus:ring-primary-500`
- Labels: `text-neutral-700 font-medium text-sm`
- Placeholder text: `text-neutral-400`

**Medical disclaimer banner (Ask Meno):**

- `bg-warning-light border border-warning text-warning-dark text-sm`

**Text colors — global:**

- Page headings: `text-neutral-800 font-bold`
- Body text: `text-neutral-600`
- Secondary/muted text: `text-neutral-400` or `text-neutral-500`
- Remove any hardcoded gray values that don't match the warm neutral palette

**Symptom logging cards:**

- Selected state should use `border-primary-500 bg-primary-50`
- Unselected state: `border-neutral-200 bg-white`
- Dismiss X button: `text-neutral-400 hover:text-neutral-600`

**Medication impact table:**

- Positive changes (decrease in symptom): `text-success`
- Negative changes (increase in symptom): `text-danger`
- Neutral/no change: `text-neutral-500`
- These semantic colors are correct to use here — this is their intended purpose

### Out of Scope

- Content changes (copy, headings, descriptions)
- Layout restructuring (page structure, component hierarchy)
- New features or functionality
- Backend changes
- Mobile responsiveness changes (unless something is currently broken)

## Implementation Approach

### Step 1: Design tokens file

Create a CSS custom properties file or Tailwind config extension that defines all the design tokens from the skill. This becomes the single source of truth.

### Step 2: Global styles

Update any global CSS to use the new tokens. Set base text color, link color, and background.

### Step 3: Shared components

Update shared components first — Navbar, Footer, Button (if componentized), Card, Badge. These cascade to every page.

### Step 4: Page by page

Work through each page systematically:

1. Dashboard
2. Log Symptoms
3. Ask Meno
4. Appointment Prep
5. Providers
6. Export
7. Cycles
8. Medications

### Step 5: Favicon

Generate and install the favicon and Apple touch icon.

## Key Constraint

**Read and follow the `frontend-design` skill exactly.** Every color, every button style, every card pattern, every spacing value is defined there. Do not introduce ANY colors or patterns not in the skill. When in doubt, use primary teal or neutral gray.

## Acceptance Criteria

- [ ] Logo appears in the navigation bar at appropriate size
- [ ] Favicon appears in the browser tab
- [ ] All primary action buttons use the same teal (`primary-500`)
- [ ] No navy, dark blue, or off-palette button colors remain anywhere in the app
- [ ] All links use `primary-600` consistently across all pages
- [ ] All cards follow the standardized card pattern
- [ ] Status badges on the Providers page use the defined badge colors
- [ ] Dashboard chart bars use the primary teal
- [ ] The "Log period" button is teal, not red
- [ ] Text colors use the warm neutral palette throughout
- [ ] Medical disclaimer banner uses warning semantic colors
- [ ] The app feels visually cohesive — a single designer could have built every page
- [ ] No regressions in functionality (all buttons still work, all forms still submit, all links still navigate)

## Testing

This is a visual-only change. No unit tests needed. Manual visual review of every page listed above to confirm consistency and no regressions.

## Reference

- **Design skill:** `frontend-design` skill in the project's skills directory
- **Logo file:** `frontend/src/lib/assets/logo.png`
- **Color palette, component patterns, and rules:** All defined in the frontend-design skill — read it before making any changes
