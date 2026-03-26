---
status: done
priority: p1
issue_id: "072"
tags: [code-review, frontend, design-system, pr-10]
dependencies: []
---

# Missed migration: SkeletonLoader, LoadingSpinner, ProviderSkeleton still use slate-*/teal-*

## Problem Statement

Three shared components were missed in the 29-file design system sweep. They still reference raw Tailwind `slate-*` and `teal-*` classes that are no longer part of the Meno design system. These components render on high-traffic routes (dashboard, log, providers) so the visual inconsistency is visible to every user during loading states.

## Findings

- `frontend/src/lib/components/shared/SkeletonLoader.svelte` lines 37–47: `border-slate-200`, `bg-slate-200`, `bg-slate-100`
- `frontend/src/lib/components/shared/LoadingSpinner.svelte` lines 31, 34: `border-slate-300`, `border-t-slate-600`, `text-slate-500`
- `frontend/src/lib/components/providers/ProviderSkeleton.svelte` lines 23–48: `border-slate-200`, `bg-slate-200`, `bg-slate-100`, `bg-amber-100`, `bg-teal-50` (line 35 — direct conflict with primary-50 migration)
- `SkeletonLoader` is imported in `dashboard/+page.svelte` and `log/+page.svelte`
- `ProviderSkeleton` appears on the providers route
- `slate-*` is cool blue-gray; the new `neutral-*` is warm stone — visible mismatch on the warm palette
- Identified by performance-oracle and architecture-strategist

## Proposed Solutions

### Option 1: Direct migration (Recommended)

Apply the same migration table used for the 29 route files:

**SkeletonLoader.svelte:**
- `border-slate-200` → `border-neutral-200`
- `bg-slate-200` → `bg-neutral-200`
- `bg-slate-100` → `bg-neutral-100`

**LoadingSpinner.svelte:**
- `border-slate-300` → `border-neutral-300`
- `border-t-slate-600` → `border-t-neutral-600`
- `text-slate-500` → `text-neutral-500`

**ProviderSkeleton.svelte:**
- All `slate-*` → `neutral-*` equivalents
- `bg-amber-100` → `bg-warning-light`
- `bg-teal-50` → `bg-primary-50`

**Pros:** Consistent, zero new abstractions, matches what every other file does
**Effort:** Small (< 30 min)
**Risk:** Zero — color class swaps only

## Recommended Action

Option 1. Fix before merge.

## Technical Details

- Affected files: `frontend/src/lib/components/shared/SkeletonLoader.svelte`, `LoadingSpinner.svelte`, `frontend/src/lib/components/providers/ProviderSkeleton.svelte`
- No logic changes, no API changes

## Acceptance Criteria

- [ ] `SkeletonLoader.svelte` contains no `slate-*` classes
- [ ] `LoadingSpinner.svelte` contains no `slate-*` classes
- [ ] `ProviderSkeleton.svelte` contains no `slate-*`, `teal-*`, or `amber-*` classes
- [ ] `grep -r "bg-slate\|text-slate\|border-slate\|bg-teal\|bg-amber" frontend/src/lib/components/shared` returns no results

## Work Log

- 2026-03-25: Identified by performance-oracle and architecture-strategist in PR #10 review
2026-03-25: Resolved.
