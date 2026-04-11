<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		existingNarrative = null,
		onNext
	}: {
		appointmentId: string;
		existingNarrative: string | null;
		onNext: (narrative: string) => void;
	} = $props();

	let narrative = $state(existingNarrative ?? '');
	let isLoading = $state(existingNarrative === null);
	let isSaving = $state(false);
	let loadError = $state('');

	onMount(() => {
		if (existingNarrative !== null) return;
		loadNarrative();
	});

	async function loadNarrative() {
		isLoading = true;
		loadError = '';
		try {
			const res = await apiClient.post(
				`/api/appointment-prep/${appointmentId}/narrative` as '/api/appointment-prep/{id}/narrative',
				{ days_back: 60 }
			);
			narrative = res.narrative;
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to generate narrative. Please try again.';
			loadError = msg;
		} finally {
			isLoading = false;
		}
	}

	async function handleNext() {
		if (!narrative.trim()) return;
		isSaving = true;
		try {
			await apiClient.put(
				`/api/appointment-prep/${appointmentId}/narrative` as '/api/appointment-prep/{id}/narrative',
				{ narrative }
			);
			onNext(narrative);
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to save narrative. Please try again.';
			loadError = msg;
		} finally {
			isSaving = false;
		}
	}
</script>

<div class="mx-auto max-w-2xl space-y-6">
	{#if isLoading}
		<div
			class="flex flex-col items-center gap-4 rounded-xl border border-neutral-200 bg-white p-8"
			aria-busy="true"
			role="status"
		>
			<div
				class="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"
			></div>
			<p class="text-sm text-neutral-500" aria-live="polite">Generating your health picture…</p>
		</div>
	{:else if loadError}
		<div
			class="rounded-xl border border-danger-light bg-danger-light p-4 text-sm text-danger-dark"
			role="alert"
		>
			{loadError}
			<button
				type="button"
				onclick={loadNarrative}
				class="ml-2 font-medium underline hover:no-underline"
			>
				Try again
			</button>
		</div>
	{:else}
		<div
			class="rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm text-primary-800"
		>
			This summary goes directly to your provider's document, word for word. Read it carefully and
			edit anything that doesn't sound right or doesn't reflect your experience. This is the most
			important thing you'll do in this process.
		</div>

		<div>
			<label for="narrative" class="mb-2 block text-sm font-medium text-neutral-700">
				Your health picture
			</label>
			<textarea
				id="narrative"
				bind:value={narrative}
				rows="12"
				class="w-full rounded-xl border border-neutral-200 px-4 py-3 text-sm text-neutral-800 placeholder-neutral-400 transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 focus:outline-none"
				aria-describedby="narrative-hint"
			></textarea>
			<p id="narrative-hint" class="mt-1 text-xs text-neutral-500">
				Your edits are saved automatically. What you see here is what your provider will read.
			</p>
		</div>

		<button
			type="button"
			onclick={handleNext}
			disabled={!narrative.trim() || isSaving}
			class="w-full rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
		>
			{isSaving ? 'Saving…' : 'Next: Prioritize your concerns'}
		</button>
	{/if}
</div>
