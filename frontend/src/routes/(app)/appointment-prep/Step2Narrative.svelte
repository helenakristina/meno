<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		onNext,
	}: {
		appointmentId: string;
		onNext: (narrative: string) => void;
	} = $props();

	let narrative = $state('');
	let isLoading = $state(true);
	let loadError = $state('');

	$effect(() => {
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

	function handleNext() {
		onNext(narrative);
	}
</script>

<div class="mx-auto max-w-2xl space-y-6">
	{#if isLoading}
		<div
			class="flex flex-col items-center gap-4 rounded-xl border border-slate-200 bg-white p-8"
			aria-busy="true"
			role="status"
		>
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-teal-200 border-t-teal-600"></div>
			<p class="text-sm text-slate-500" aria-live="polite">
				Generating your symptom summary…
			</p>
		</div>
	{:else if loadError}
		<div class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
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
		<div class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
			AI-generated summary — review and edit before sharing with your provider.
		</div>

		<div>
			<label for="narrative" class="mb-2 block text-sm font-medium text-slate-700">
				Your symptom summary
			</label>
			<textarea
				id="narrative"
				bind:value={narrative}
				rows="12"
				class="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-800 placeholder-slate-400 transition-colors focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-400/20"
				aria-describedby="narrative-hint"
			></textarea>
			<p id="narrative-hint" class="mt-1 text-xs text-slate-500">
				Edit freely — this is your document.
			</p>
		</div>

		<button
			type="button"
			onclick={handleNext}
			disabled={!narrative.trim()}
			class="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
		>
			Next: Prioritize your concerns
		</button>
	{/if}
</div>
