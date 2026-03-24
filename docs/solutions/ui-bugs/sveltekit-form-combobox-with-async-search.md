---
title: SvelteKit Form Combobox with Async Search and Cascading Field Dependencies
category: ui-bugs
date: 2026-03-20
tags: [svelte5, combobox, autocomplete, accessibility, aria, debounce, medication-tracking]
symptoms:
  - Free-text form fields produce inconsistent, hard-to-compare data across users
  - Backend has curated reference data but frontend doesn't use it
  - Dose and delivery method options need to change based on selected medication
components:
  - frontend/src/routes/(app)/medications/add/+page.svelte
  - frontend/src/lib/types/api.ts
---

## Problem

The Add Medication form used plain text inputs for medication name and dose, producing inconsistent entries ("estradiol", "Estradiol", "estradiol patch 0.05") that couldn't be compared across users. The backend already had a complete `medications_reference` table with 17+ curated HRT medications, each with `common_doses[]` and `common_forms[]`, plus a working `GET /api/medications/reference?query=` endpoint. None of it was wired to the frontend.

## Solution

**Frontend-only change** — no backend work needed. Added a search-as-you-type combobox to the name field that populates dose options and filters delivery methods from the selected reference medication. Users who can't find their medication can still enter a custom entry.

## Key Patterns

### 1. Wiring a reference search endpoint to a combobox

Add the interface and endpoint to `api.ts`:
```typescript
export interface MedicationReferenceResult {
  id: string;
  brand_name: string | null;
  generic_name: string;
  hormone_type: string;
  common_forms: string[];   // delivery methods valid for this med
  common_doses: string[];   // pre-approved doses
  notes: string | null;
  is_user_created: boolean;
}

// In ApiEndpoints:
'/api/medications/reference': {
  request: never;
  response: MedicationReferenceResult[];
};
```

Call with query params (typed client handles URL construction):
```typescript
const results = await apiClient.get('/api/medications/reference', {
  query: searchQuery.trim()
});
```

### 2. Debounced search to prevent excessive API calls

```typescript
let searchTimer: ReturnType<typeof setTimeout>;

function onSearchInput() {
  clearTimeout(searchTimer);
  selectedMedication = null;
  medication_name = searchQuery;

  if (searchQuery.trim().length < 2) {
    searchResults = [];
    showDropdown = false;
    return;
  }

  searchTimer = setTimeout(async () => {
    isSearching = true;
    try {
      const results = await apiClient.get('/api/medications/reference', {
        query: searchQuery.trim()
      });
      searchResults = Array.isArray(results) ? results : [];
      showDropdown = true;
    } catch {
      searchResults = [];
    } finally {
      isSearching = false;
    }
  }, 300);  // 300ms debounce
}
```

### 3. `$derived` for cascading field state

```typescript
// Dose value to submit — different logic for reference vs custom
const doseValue = $derived(
  selectedMedication
    ? (selectedDose === 'custom' ? customDose.trim() : selectedDose)
    : dose.trim()
);

// Delivery methods: filtered to medication's valid forms, or full list
const availableDeliveryMethods = $derived<readonly string[]>(
  selectedMedication && selectedMedication.common_forms.length > 0
    ? selectedMedication.common_forms
    : DELIVERY_METHODS
);
```

Auto-select when only one delivery method is valid:
```typescript
function selectMedication(med: MedicationReferenceResult) {
  selectedMedication = med;
  searchQuery = med.brand_name ?? med.generic_name;
  medication_name = searchQuery;
  // Auto-select if only one form (e.g. Climara → patch only)
  delivery_method = med.common_forms.length === 1 ? med.common_forms[0] : '';
  selectedDose = '';
  customDose = '';
  showDropdown = false;
}
```

### 4. `onmousedown` not `onclick` for dropdown items

**Critical:** Use `onmousedown` on dropdown items, not `onclick`.

**Why:** The sequence of events when a user clicks a dropdown item while the input is focused:
1. `mousedown` fires on the dropdown item ← `onmousedown` handles here ✅
2. `blur` fires on the input ← `onblur` hides the dropdown
3. `mouseup` fires
4. `click` fires ← too late, dropdown already hidden ❌

```svelte
<!-- ❌ Wrong — dropdown hidden before click registers -->
<li onclick={() => selectMedication(med)}>

<!-- ✅ Correct — fires before blur -->
<li onmousedown={() => selectMedication(med)}>
```

Pair with a delayed `onblur` to give `onmousedown` time to fire:
```typescript
function onBlur() {
  setTimeout(() => { showDropdown = false; }, 150);
}
```

### 5. Keyboard navigation

```typescript
function onKeyDown(e: KeyboardEvent) {
  if (!showDropdown) return;
  const total = searchResults.length + 1; // +1 for the custom option

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    highlightedIndex = (highlightedIndex + 1) % total;
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    highlightedIndex = (highlightedIndex - 1 + total) % total;
  } else if (e.key === 'Enter' && highlightedIndex >= 0) {
    e.preventDefault();
    if (highlightedIndex < searchResults.length) {
      selectMedication(searchResults[highlightedIndex]);
    } else {
      selectCustom();
    }
  } else if (e.key === 'Escape') {
    showDropdown = false;
    highlightedIndex = -1;
  }
}
```

### 6. ARIA combobox markup

```svelte
<input
  role="combobox"
  aria-expanded={showDropdown}
  aria-autocomplete="list"
  aria-controls="medication-listbox"
  aria-activedescendant={highlightedIndex >= 0 ? `med-option-${highlightedIndex}` : undefined}
  bind:value={searchQuery}
  oninput={onSearchInput}
  onkeydown={onKeyDown}
  onblur={onBlur}
  autocomplete="off"
/>

<ul id="medication-listbox" role="listbox" aria-label="Medication suggestions">
  {#each searchResults as med, i}
    <li
      id="med-option-{i}"
      role="option"
      aria-selected={highlightedIndex === i}
      onmousedown={() => selectMedication(med)}
    >
      <span class="font-medium">{med.generic_name}</span>
      {#if med.brand_name}<span class="text-slate-500"> ({med.brand_name})</span>{/if}
      <span class="text-xs text-slate-400">{med.common_forms.join(', ')}</span>
    </li>
  {/each}
  <!-- Always show a custom option -->
  <li
    id="med-option-{searchResults.length}"
    role="option"
    aria-selected={highlightedIndex === searchResults.length}
    onmousedown={selectCustom}
  >
    + Add "{searchQuery}" as custom medication
  </li>
</ul>
```

### 7. Conditional dose UI (dropdown → custom text input)

```svelte
{#if selectedMedication && selectedMedication.common_doses.length > 0}
  <select bind:value={selectedDose} required>
    <option value="" disabled>Select a dose</option>
    {#each selectedMedication.common_doses as d}
      <option value={d}>{d}</option>
    {/each}
    <option value="custom">Other (type custom)</option>
  </select>
  {#if selectedDose === 'custom'}
    <input bind:value={customDose} placeholder="Enter dose (e.g. 0.075mg)" />
  {/if}
{:else}
  <!-- Custom mode or reference with no common doses -->
  <input bind:value={dose} placeholder="e.g. 50mcg, 1mg, 0.05%" required />
{/if}
```

## Prevention / Reuse Checklist

- [ ] Use `onmousedown` (not `onclick`) for all dropdown items in a combobox
- [ ] Pair `onblur` with a 150ms delay so mousedown fires first
- [ ] Debounce search input at 300ms minimum
- [ ] Validate API results as `Array.isArray(results)` before assigning — API errors can return non-arrays
- [ ] Set `autocomplete="off"` on the combobox input to prevent browser autocomplete interfering
- [ ] Include a "custom entry" option so users aren't blocked if their medication isn't listed
- [ ] Use `$derived` for any field values that depend on the selected reference item

## Related

- `frontend/src/lib/components/providers/ProviderFilters.svelte` — similar pattern: searchable insurance dropdown with keyboard nav
- No shared `<Combobox>` component exists yet; both implementations are inline. Consider extracting if a third use case arises.
