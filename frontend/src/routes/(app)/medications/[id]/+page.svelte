<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { apiClient } from '$lib/api/client';
	import type { Medication } from '$lib/types/api';

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

	// Page state
	let loading = $state(true);
	let error = $state<string | null>(null);
	let medication = $state<Medication | null>(null);

	// Edit fields (notes + end_date)
	let editNotes = $state('');
	let editEndDate = $state('');
	let saving = $state(false);
	let saveError = $state<string | null>(null);
	let saveSuccess = $state(false);

	// Dose change form
	let newDose = $state('');
	let newDeliveryMethod = $state('');
	let effectiveDate = $state(new Date().toISOString().split('T')[0]);
	let changingDose = $state(false);
	let doseChangeError = $state<string | null>(null);
	let doseChangeSuccess = $state(false);

	// Delete confirmation
	let confirmDelete = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	const id = $derived(page.params.id);

	const canSave = $derived(
		editNotes !== (medication?.notes ?? '') || editEndDate !== (medication?.end_date ?? '')
	);

	const canChangeDose = $derived(newDose.trim().length > 0 && newDeliveryMethod.length > 0);

	function formatDeliveryMethod(method: string): string {
		return method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		});
	}

	onMount(async () => {
		try {
			const med = await apiClient.get(`/api/medications/${id}` as any);
			medication = med;
			editNotes = med.notes ?? '';
			editEndDate = med.end_date ?? '';
			newDeliveryMethod = med.delivery_method;
		} catch {
			error = 'Unable to load medication. Please go back and try again.';
		} finally {
			loading = false;
		}
	});

	async function handleSave(e: Event) {
		e.preventDefault();
		if (!canSave || saving) return;

		saving = true;
		saveError = null;
		saveSuccess = false;

		try {
			const updated = await apiClient.put(`/api/medications/${id}` as any, {
				notes: editNotes.trim() || null,
				end_date: editEndDate || null
			} as any);
			medication = updated;
			editNotes = updated.notes ?? '';
			editEndDate = updated.end_date ?? '';
			saveSuccess = true;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save changes. Please try again.';
		} finally {
			saving = false;
		}
	}

	async function handleDoseChange(e: Event) {
		e.preventDefault();
		if (!canChangeDose || changingDose) return;

		changingDose = true;
		doseChangeError = null;
		doseChangeSuccess = false;

		try {
			const updated = await apiClient.post(`/api/medications/${id}/change` as any, {
				new_dose: newDose.trim(),
				new_delivery_method: newDeliveryMethod,
				effective_date: effectiveDate
			} as any);
			medication = updated;
			newDose = '';
			doseChangeSuccess = true;
		} catch (e) {
			doseChangeError =
				e instanceof Error ? e.message : 'Failed to record dose change. Please try again.';
		} finally {
			changingDose = false;
		}
	}

	async function handleDelete() {
		if (deleting) return;

		if (!confirmDelete) {
			confirmDelete = true;
			return;
		}

		deleting = true;
		deleteError = null;

		try {
			await apiClient.delete(`/api/medications/${id}` as any);
			goto('/medications');
		} catch (e) {
			deleteError = e instanceof Error ? e.message : 'Failed to delete medication. Please try again.';
			deleting = false;
			confirmDelete = false;
		}
	}
</script>

<svelte:head>
	<title>{medication ? medication.medication_name : 'Medication'} — Meno</title>
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

	{#if loading}
		<div class="space-y-4">
			<div class="h-8 w-48 animate-pulse rounded bg-slate-200"></div>
			<div class="h-32 animate-pulse rounded-lg bg-slate-100"></div>
		</div>
	{:else if error}
		<div class="rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">{error}</div>
	{:else if medication}
		<!-- Header -->
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-2xl font-bold text-slate-900">{medication.medication_name}</h1>
				<p class="mt-1 text-sm text-slate-500">
					{medication.dose} · {formatDeliveryMethod(medication.delivery_method)}{medication.frequency
						? ` · ${medication.frequency.replace(/_/g, ' ')}`
						: ''}
				</p>
				<p class="mt-0.5 text-xs text-slate-400">Started {formatDate(medication.start_date)}</p>
				{#if medication.end_date}
					<p class="mt-0.5 text-xs text-slate-400">Ended {formatDate(medication.end_date)}</p>
				{/if}
			</div>
			<a
				href="/medications/{id}/impact"
				class="rounded-md border border-slate-200 px-3 py-2 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
			>
				View impact
			</a>
		</div>

		<!-- Edit notes + end date -->
		<section class="mb-6 rounded-lg border border-slate-200 bg-white p-4">
			<h2 class="mb-4 text-sm font-semibold text-slate-900">Edit details</h2>

			{#if saveSuccess}
				<div class="mb-3 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
					Changes saved.
				</div>
			{/if}

			{#if saveError}
				<div class="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
					{saveError}
				</div>
			{/if}

			<form onsubmit={handleSave} class="space-y-4">
				<div>
					<label for="notes" class="mb-1.5 block text-sm font-medium text-slate-700">
						Notes
						<span class="text-xs font-normal text-slate-400">(optional)</span>
					</label>
					<textarea
						id="notes"
						bind:value={editNotes}
						rows="3"
						placeholder="Any notes about this medication…"
						class="w-full resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
					></textarea>
				</div>

				<div>
					<label for="end_date" class="mb-1.5 block text-sm font-medium text-slate-700">
						End date
						<span class="text-xs font-normal text-slate-400"
							>(optional — set this to mark the medication as stopped)</span
						>
					</label>
					<input
						id="end_date"
						type="date"
						bind:value={editEndDate}
						class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
					/>
					{#if editEndDate}
						<button
							type="button"
							onclick={() => {
								editEndDate = '';
							}}
							class="mt-1 text-xs text-slate-500 underline hover:text-slate-700"
						>
							Clear end date
						</button>
					{/if}
				</div>

				<button
					type="submit"
					disabled={!canSave || saving}
					class="w-full rounded-lg bg-slate-800 px-4 py-3 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
				>
					{saving ? 'Saving…' : 'Save changes'}
				</button>
			</form>
		</section>

		<!-- Dose change section -->
		{#if !medication.end_date}
			<section class="mb-6 rounded-lg border border-slate-200 bg-white p-4">
				<h2 class="mb-1 text-sm font-semibold text-slate-900">Record a dose change</h2>
				<p class="mb-4 text-xs text-slate-500">
					Use this to track a new dose — it will create a new entry and link it to this one.
				</p>

				{#if doseChangeSuccess}
					<div class="mb-3 rounded-md bg-green-50 p-3 text-sm text-green-700" role="status">
						Dose change recorded.
					</div>
				{/if}

				{#if doseChangeError}
					<div class="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700" role="alert">
						{doseChangeError}
					</div>
				{/if}

				<form onsubmit={handleDoseChange} class="space-y-4">
					<div>
						<label for="new_dose" class="mb-1.5 block text-sm font-medium text-slate-700">
							New dose <span class="text-red-500" aria-hidden="true">*</span>
						</label>
						<input
							id="new_dose"
							type="text"
							bind:value={newDose}
							placeholder="e.g. 75mcg, 2mg"
							class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
						/>
					</div>

					<div>
						<label
							for="new_delivery_method"
							class="mb-1.5 block text-sm font-medium text-slate-700"
						>
							Delivery method <span class="text-red-500" aria-hidden="true">*</span>
						</label>
						<select
							id="new_delivery_method"
							bind:value={newDeliveryMethod}
							class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
						>
							{#each DELIVERY_METHODS as method}
								<option value={method}>{formatDeliveryMethod(method)}</option>
							{/each}
						</select>
					</div>

					<div>
						<label for="effective_date" class="mb-1.5 block text-sm font-medium text-slate-700">
							Effective date <span class="text-red-500" aria-hidden="true">*</span>
						</label>
						<input
							id="effective_date"
							type="date"
							bind:value={effectiveDate}
							class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
						/>
					</div>

					<button
						type="submit"
						disabled={!canChangeDose || changingDose}
						class="w-full rounded-lg border border-slate-300 px-4 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
					>
						{changingDose ? 'Recording…' : 'Record dose change'}
					</button>
				</form>
			</section>
		{/if}

		<!-- Delete -->
		<section class="rounded-lg border border-red-100 bg-red-50 p-4">
			<h2 class="mb-1 text-sm font-semibold text-red-800">Delete medication</h2>
			<p class="mb-3 text-xs text-red-700">
				This will permanently remove this medication and all associated data.
			</p>

			{#if deleteError}
				<div class="mb-3 rounded-md bg-red-100 p-3 text-sm text-red-800" role="alert">
					{deleteError}
				</div>
			{/if}

			{#if confirmDelete}
				<div class="flex gap-2">
					<button
						onclick={handleDelete}
						disabled={deleting}
						class="flex-1 rounded-lg bg-red-600 px-4 py-3 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
					>
						{deleting ? 'Deleting…' : 'Yes, delete'}
					</button>
					<button
						onclick={() => {
							confirmDelete = false;
						}}
						disabled={deleting}
						class="flex-1 rounded-lg border border-red-200 bg-white px-4 py-3 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
					>
						Cancel
					</button>
				</div>
			{:else}
				<button
					onclick={handleDelete}
					class="w-full rounded-lg border border-red-200 bg-white px-4 py-3 text-sm font-medium text-red-700 hover:bg-red-50"
				>
					Delete medication
				</button>
			{/if}
		</section>
	{/if}
</div>
