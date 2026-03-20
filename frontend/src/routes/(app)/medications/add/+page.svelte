<script lang="ts">
	import { goto } from '$app/navigation';
	import { apiClient } from '$lib/api/client';

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

	// Form state
	let medication_name = $state('');
	let dose = $state('');
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
		medication_name.trim().length > 0 && dose.trim().length > 0 && delivery_method.length > 0
	);

	function formatDeliveryMethod(method: string): string {
		return method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		if (!canSubmit || submitting) return;

		submitting = true;
		error = null;

		try {
			await apiClient.post('/api/medications', {
				medication_name: medication_name.trim(),
				dose: dose.trim(),
				delivery_method,
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
		<!-- Medication name -->
		<div>
			<label for="medication_name" class="mb-1.5 block text-sm font-medium text-slate-700">
				Medication name <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			<input
				id="medication_name"
				type="text"
				bind:value={medication_name}
				required
				placeholder="e.g. Estradiol"
				class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			/>
		</div>

		<!-- Dose -->
		<div>
			<label for="dose" class="mb-1.5 block text-sm font-medium text-slate-700">
				Dose <span class="text-red-500" aria-hidden="true">*</span>
			</label>
			<input
				id="dose"
				type="text"
				bind:value={dose}
				required
				placeholder="e.g. 50mcg, 1mg, 0.05%"
				class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
			/>
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
				{#each DELIVERY_METHODS as method}
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
				class="flex-1 rounded-lg bg-slate-800 px-4 py-3 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
			>
				{submitting ? 'Adding…' : 'Add medication'}
			</button>
		</div>
	</form>
</div>
