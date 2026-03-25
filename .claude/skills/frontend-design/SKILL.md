---
name: frontend-design
description: >
  Use when making ANY visual or styling decisions in the Meno frontend. This includes
  choosing colors, styling components, creating new UI elements, modifying layouts,
  adding buttons/badges/cards, or touching any CSS/Tailwind classes. This skill defines
  Meno's complete design system — colors, typography, spacing, component patterns —
  and must be followed exactly. Do not introduce colors, fonts, or patterns not defined here.
when_to_use: >
  Any task that involves visual appearance: new components, styling changes, new pages,
  color choices, button styling, card layouts, chart colors, badge design, form styling,
  or any modification to Tailwind classes in the frontend/ directory.
version: 1.0.0
languages: [typescript, svelte, css]
---

# Meno Frontend Design Skill

## Purpose

This skill defines the visual design system for Meno. All frontend work MUST follow these specifications. Do not introduce new colors, fonts, or spacing values without explicit approval.

## Color Palette

### Primary — Teal (actions, buttons, interactive elements)

Use for: Primary buttons, progress bars, chart bars, active nav items, links, toggles, focus rings.

```
--color-primary-50:  #f0fdf9    /* Lightest background tint */
--color-primary-100: #ccfbef    /* Light hover backgrounds */
--color-primary-200: #99f6de    /* Selected/active backgrounds */
--color-primary-300: #5ceac8    /* Light accent */
--color-primary-400: #2dd4a8    /* Secondary buttons, badges */
--color-primary-500: #14b892    /* DEFAULT — primary buttons, links, active states */
--color-primary-600: #0d9478    /* Hover state for primary buttons */
--color-primary-700: #0f7663    /* Pressed state */
--color-primary-800: #115e50    /* Dark accent text on light primary backgrounds */
--color-primary-900: #134d43    /* Darkest accent */
```

### Neutral — Warm Gray (text, borders, backgrounds, structure)

Use for: Body text, headings, borders, card backgrounds, disabled states.

```
--color-neutral-50:  #fafaf9    /* Page background (if not white) */
--color-neutral-100: #f5f5f4    /* Card hover backgrounds, subtle fills */
--color-neutral-200: #e7e5e4    /* Borders, dividers */
--color-neutral-300: #d6d3d1    /* Disabled text, placeholder text */
--color-neutral-400: #a8a29e    /* Secondary text, captions */
--color-neutral-500: #78716c    /* Muted body text */
--color-neutral-600: #57534e    /* Body text */
--color-neutral-700: #44403c    /* Strong body text */
--color-neutral-800: #292524    /* Headings */
--color-neutral-900: #1c1917    /* High-contrast text (use sparingly) */
```

### Accent — Coral (secondary highlights, warmth)

Use for: Period flow indicators, status badges that need warmth, secondary call-to-action, illustration accents.

```
--color-accent-50:  #fff7ed
--color-accent-100: #ffedd5
--color-accent-200: #fed7aa
--color-accent-300: #fdba74
--color-accent-400: #fb923c    /* DEFAULT — badges, period indicators, warm highlights */
--color-accent-500: #f97316    /* Stronger accent when needed */
--color-accent-600: #ea580c    /* Hover on accent elements */
--color-accent-700: #c2410c
--color-accent-800: #9a3412
--color-accent-900: #7c2d12
```

### Semantic Colors (use ONLY for their specific purpose)

```
/* Success — positive changes, improvements, confirmations */
--color-success-light: #dcfce7
--color-success:       #16a34a
--color-success-dark:  #166534

/* Warning — cautions, limited data, heads-up notices */
--color-warning-light: #fef9c3
--color-warning:       #ca8a04
--color-warning-dark:  #854d0e

/* Danger — destructive actions ONLY (delete, stop, remove) */
--color-danger-light:  #fee2e2
--color-danger:        #dc2626
--color-danger-dark:   #991b1b

/* Info — informational banners, neutral callouts */
--color-info-light:    #dbeafe
--color-info:          #2563eb
--color-info-dark:     #1e40af
```

### Background

```
--color-bg-page:    #ffffff      /* Main page background */
--color-bg-card:    #ffffff      /* Card backgrounds */
--color-bg-subtle:  #fafaf9      /* Subtle section differentiation */
--color-bg-overlay: rgba(0,0,0,0.5)  /* Modal overlays */
```

## Typography

### Font Stack

```
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', monospace;
```

### Scale

```
--text-xs:   0.75rem    /* 12px — fine print, timestamps */
--text-sm:   0.875rem   /* 14px — captions, secondary info */
--text-base: 1rem       /* 16px — body text */
--text-lg:   1.125rem   /* 18px — emphasized body */
--text-xl:   1.25rem    /* 20px — card headings */
--text-2xl:  1.5rem     /* 24px — section headings */
--text-3xl:  1.875rem   /* 30px — page titles */
```

### Weights

```
--font-normal:   400    /* Body text */
--font-medium:   500    /* Subtle emphasis, nav items */
--font-semibold: 600    /* Card headings, buttons */
--font-bold:     700    /* Page titles, section headings */
```

## Spacing

Use Tailwind's default spacing scale. Key values:

```
1:  0.25rem (4px)
2:  0.5rem  (8px)
3:  0.75rem (12px)
4:  1rem    (16px)
6:  1.5rem  (24px)
8:  2rem    (32px)
12: 3rem    (48px)
16: 4rem    (64px)
```

### Consistent spacing rules:

- Card padding: `p-6` (24px)
- Section padding: `py-8` or `py-12`
- Gap between cards/items: `gap-4` (16px) or `gap-6` (24px)
- Form field spacing: `space-y-4`

## Border Radius

```
--radius-sm:  0.375rem  (6px)   /* Buttons, badges, pills */
--radius-md:  0.5rem    (8px)   /* Cards, inputs */
--radius-lg:  0.75rem   (12px)  /* Modals, large cards */
--radius-full: 9999px            /* Avatars, circular elements */
```

## Shadows

```
--shadow-sm:  0 1px 2px rgba(0,0,0,0.05)       /* Subtle card elevation */
--shadow-md:  0 4px 6px -1px rgba(0,0,0,0.1)    /* Elevated cards, dropdowns */
--shadow-lg:  0 10px 15px -3px rgba(0,0,0,0.1)  /* Modals, popovers */
```

## Component Patterns

### Buttons

- **Primary:** `bg-primary-500 text-white hover:bg-primary-600` — use for main actions (Save, Submit, Generate, Search)
- **Secondary:** `border border-neutral-300 text-neutral-700 hover:bg-neutral-50` — use for secondary actions (Cancel, Back, View)
- **Danger:** `bg-danger text-white hover:bg-danger-dark` — ONLY for destructive actions (Delete, Remove)
- **Ghost:** `text-primary-500 hover:bg-primary-50` — for tertiary actions, inline links that look like buttons
- All buttons: `rounded-md px-4 py-2 font-semibold text-sm`
- Never use navy/dark backgrounds for buttons

### Cards

- `bg-white border border-neutral-200 rounded-lg p-6`
- No colored backgrounds on cards unless it's a callout (use semantic light backgrounds for callouts)
- Hover state (if interactive): `hover:border-primary-300 hover:shadow-sm transition-all`

### Status Badges

- **Booked Appointment:** `bg-primary-100 text-primary-800`
- **To Call:** `bg-accent-100 text-accent-800`
- **Left Voicemail:** `bg-warning-light text-warning-dark`
- All badges: `px-2.5 py-0.5 rounded-full text-xs font-medium`

### Navigation

- Background: `bg-white border-b border-neutral-200`
- Nav text: `text-neutral-600 hover:text-primary-600`
- Active item: `text-primary-600 font-semibold` with underline or bottom border
- "Meno" wordmark: `text-neutral-800 font-bold`

### Charts and Data Visualization

- Primary data bars: `bg-primary-400` or `bg-primary-500`
- Secondary data: `bg-primary-200`
- Use the primary teal ramp for all chart elements — do not introduce new colors for charts
- Axis labels and values: `text-neutral-500 text-sm`

### Forms

- Input borders: `border-neutral-300 focus:border-primary-500 focus:ring-primary-500`
- Labels: `text-neutral-700 font-medium text-sm`
- Placeholder text: `text-neutral-400`
- Required indicator: `text-danger` asterisk

### Medical Disclaimer Banner

- `bg-warning-light border border-warning text-warning-dark text-sm`
- This is the ONLY place a yellow/amber background should appear

## Rules for CC

1. **NEVER introduce new colors.** All colors must come from the palette defined above.
2. **NEVER use navy, dark blue, or dark backgrounds for buttons or interactive elements.** The primary teal is the action color.
3. **NEVER use different link colors on different pages.** Links are always `text-primary-600 hover:text-primary-700`.
4. **NEVER use colored card backgrounds** unless it's a semantic callout (warning, info, success).
5. **NEVER use random accent colors for new features.** If something needs visual distinction, use the accent coral or a different shade of the primary teal.
6. **All status badges follow the badge pattern above.** Do not invent new badge colors.
7. **Charts and data visualization use the primary teal ramp only.** No rainbow charts.
8. **The danger/red color is reserved for destructive actions only.** Period logging buttons should use the accent coral, not red.
9. **Maintain consistent spacing.** Cards are `p-6`, sections are `py-8` or `py-12`, gaps are `gap-4` or `gap-6`.
10. **When in doubt, use the primary teal or neutral gray.** The palette is intentionally constrained. Fewer colors = more cohesion.
