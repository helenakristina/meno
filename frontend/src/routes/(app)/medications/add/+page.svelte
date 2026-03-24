<script lang="ts">
	import { goto } from '$app/navigation';
	import { apiClient } from '$lib/api/client';
	import type { MedicationReferenceResult } from '$lib/types/api';

	const DELIVERY_METHODS = [
		'patch',
		'pill',
		'gel',
		'cream',
		'ring',
		'injection',
		'pellet',
		'spray',
		'troche',
		'sublingual',
		'other'
	] as const;

	// Combobox state
	let searchQuery = $state('');
	let searchResults = $state<MedicationReferenceResult[]>([]);
	let selectedMedication = $state<MedicationReferenceResult | null>(null);
	let showDropdown = $state(false);
	let isSearching = $state(false);
	let highlightedIndex = $state(-1);

	// Dose state — used when no reference medication is selected
	let dose = $state('');
	// Dose state when reference is selected
	let selectedDose = $state(''); // one of common_doses, or 'custom'
	let customDose = $state('');
	const useCustomDose = $derived(selectedDose === 'custom');

	// The dose value to submit
	const doseValue = $derived(
		selectedMedication
			? useCustomDose
				? customDose.trim()
				: selectedDose
			: dose.trim()
	);

	// Delivery method filtered to the reference medication's forms (or full list)
	const availableDeliveryMethods = $derived<readonly string[]>(
		selectedMedication && selectedMedication.common_forms.length > 0
			? selectedMedication.common_forms
			: DELIVERY_METHODS
	);

	// The medication_name to submit (display name from combobox)
	let medication_name = $state('');
	let delivery_method = $state('');
	let frequency = $state('');
	const today = new Date();
	let start_date = $state(
		`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
	);
	let notes = $state('');

	let submitting = $state(false);
	let error = $state<string | null>(null);

	const canSubmit = $derived(
		medication_name.trim().length > 0 &&
			doseValue.length > 0 &&
			delivery_method.length > 0 &&
			!submitting
	);

	function formatDeliveryMethod(method: string): string {
		return method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	// --- Combobox logic ---

	let searchTimer: ReturnType<typeof setTimeout>;

	function onSearchInput() {
		clearTimeout(searchTimer);
		// Clear any prior selection when user starts re-typing
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
		}, 300);
	}

	function selectMedication(med: MedicationReferenceResult) {
		selectedMedication = med;
		searchQuery = med.brand_name ?? med.generic_name;
		medication_name = searchQuery;
		showDropdown = false;
		highlightedIndex = -1;

		// Auto-select delivery method when there's only one option
		delivery_method = med.common_forms.length === 1 ? med.common_forms[0] : '';

		// Reset dose
		selectedDose = '';
		customDose = '';
	}

	function selectCustom() {
		selectedMedication = null;
		medication_name = searchQuery;
		showDropdown = false;
		highlightedIndex = -1;
		delivery_method = '';
		dose = '';
	}

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

	function onBlur() {
		// Delay so mousedown on dropdown items fires before the blur hides the list
		setTimeout(() => {
			showDropdown = false;
		}, 150);
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!canSubmit || submitting) return;

		submitting = true;
		error = null;

		try {
			await apiClient.post('/api/medications', {
				medication_name: medication_name.trim(),
				dose: doseValue,
				delivery_method,
				...(selectedMedication ? { medication_ref_id: selectedMedication.id } : {}),
				...(frequency.trim() ? { frequency: frequency.trim() } : {}),
				start_date,
				...(notes.trim() ? { notes: notes.trim() } : {})
			});
			goto('/medications');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to add medication. Please try again.';
		} finally {
			submitting = false;
		}
	}
</script>

<svelte:head>
	<title>Add Medication — Meno</title>
</svelte:head>

<div class="mx-auto max-w-lg">
	<div class="mb-6">
		<a
			href="/medications"
			class="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
				aria-hidden="true"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
			</svg>
			Back to medications
		</a>
	</div>

	<h1 class="mb-6 text-2xl font-bold text-slate-900">Add Medication</h1>

	{#if error}
		<div class="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">
			{error}
		</div>
	{/if}

	<form onsubmit={handleSubmit} class="space-y-5" novalidate>
		<!-- Medication name — combobox -->
		<div>
			<label for="medication_name" class="mb-1.5 block text-sm font-medium text-slate-700">
				Medication name <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			<div class="relative">
				<input
					id="medication_name"
					type="text"
					role="combobox"
					aria-expanded={showDropdown}
					aria-autocomplete="list"
					aria-controls="medication-listbox"
					aria-activedescendant={highlightedIndex >= 0
						? `med-option-${highlightedIndex}`
						: undefined}
					bind:value={searchQuery}
					oninput={onSearchInput}
					onkeydown={onKeyDown}
					onblur={onBlur}
					onfocus={() => {
						if (searchResults.length > 0) showDropdown = true;
					}}
					required
					autocomplete="off"
					placeholder="Search medications (e.g. Estradiol, Climara)"
					class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
				/>
				{#if isSearching}
					<span
						class="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400"
						aria-live="polite"
					>
						Searching…
					</span>
				{/if}

				{#if showDropdown && (searchResults.length > 0 || searchQuery.trim().length >= 2)}
					<ul
						id="medication-listbox"
						role="listbox"
						aria-label="Medication suggestions"
						class="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-md"
					>
						{#each searchResults as med, i}
							<li
								id="med-option-{i}"
								role="option"
								aria-selected={highlightedIndex === i}
								class="cursor-pointer px-3 py-2.5 text-sm hover:bg-slate-50 {highlightedIndex === i
									? 'bg-slate-50'
									: ''}"
								onmousedown={() => selectMedication(med)}
							>
								<span class="font-medium text-slate-900">{med.generic_name}</span>
								{#if med.brand_name}
									<span class="text-slate-500"> ({med.brand_name})</span>
								{/if}
								{#if med.common_forms.length > 0}
									<span class="ml-1.5 text-xs text-slate-400"
										>{med.common_forms.map(formatDeliveryMethod).join(', ')}</span
									>
								{/if}
							</li>
						{/each}
						<!-- Custom option -->
						<li
							id="med-option-{searchResults.length}"
							role="option"
							aria-selected={highlightedIndex === searchResults.length}
							class="cursor-pointer border-t border-slate-100 px-3 py-2.5 text-sm text-slate-500 hover:bg-slate-50 {highlightedIndex ===
							searchResults.length
								? 'bg-slate-50'
								: ''}"
							onmousedown={selectCustom}
						>
							+ Add "{searchQuery}" as custom medication
						</li>
					</ul>
				{/if}
			</div>
			{#if selectedMedication}
				<p class="mt-1 text-xs text-teal-600">
					{selectedMedication.generic_name}
					{#if selectedMedication.brand_name}({selectedMedication.brand_name}){/if}
					selected
				</p>
			{/if}
		</div>

		<!-- Dose -->
		<div>
			<label for="dose" class="mb-1.5 block text-sm font-medium text-slate-700">
				Dose <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			{#if selectedMedication && selectedMedication.common_doses.length > 0}
				<select
					id="dose"
					bind:value={selectedDose}
					required
					class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
				>
					<option value="" disabled>Select a dose</option>
					{#each selectedMedication.common_doses as d}
						<option value={d}>{d}</option>
					{/each}
					<option value="custom">Other (type custom)</option>
				</select>
				{#if useCustomDose}
					<input
						id="dose_custom"
						type="text"
						bind:value={customDose}
						placeholder="Enter dose (e.g. 0.075mg)"
						class="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
					/>
				{/if}
			{:else}
				<input
					id="dose"
					type="text"
					bind:value={dose}
					required
					placeholder="e.g. 50mcg, 1mg, 0.05%"
					class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
				/>
			{/if}
		</div>

		<!-- Delivery method -->
		<div>
			<label for="delivery_method" class="mb-1.5 block text-sm font-medium text-slate-700">
				Delivery method <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			<select
				id="delivery_method"
				bind:value={delivery_method}
				required
				class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			>
				<option value="" disabled>Select a delivery method</option>
				{#each availableDeliveryMethods as method}
					<option value={method}>{formatDeliveryMethod(method)}</option>
				{/each}
			</select>
		</div>

		<!-- Frequency (optional) -->
		<div>
			<label for="frequency" class="mb-1.5 block text-sm font-medium text-slate-700">
				Frequency <span class="text-xs font-normal text-slate-400">(optional)</span>
			</label>
			<input
				id="frequency"
				type="text"
				bind:value={frequency}
				placeholder="e.g. once weekly, daily, twice a week"
				class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			/>
		</div>

		<!-- Start date -->
		<div>
			<label for="start_date" class="mb-1.5 block text-sm font-medium text-slate-700">
				Start date <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			<input
				id="start_date"
				type="date"
				bind:value={start_date}
				required
				class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			/>
		</div>

		<!-- Notes (optional) -->
		<div>
			<label for="notes" class="mb-1.5 block text-sm font-medium text-slate-700">
				Notes <span class="text-xs font-normal text-slate-400">(optional)</span>
			</label>
			<textarea
				id="notes"
				bind:value={notes}
				rows="3"
				placeholder="Any additional notes about this medication…"
				class="w-full resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			></textarea>
		</div>

		<div class="flex gap-3 pt-2">
			<a
				href="/medications"
				class="flex-1 rounded-lg border border-slate-300 px-4 py-3 text-center text-sm font-medium text-slate-700 hover:bg-slate-50"
			>
				Cancel
			</a>
			<button
				type="submit"
				disabled={!canSubmit || submitting}
				class="flex-1 rounded-lg bg-teal-600 px-4 py-3 text-sm font-medium text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
			>
				{submitting ? 'Adding…' : 'Add medication'}
			</button>
		</div>
	</form>
</div>
