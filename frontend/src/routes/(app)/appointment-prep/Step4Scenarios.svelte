<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { ScenarioCard } from '$lib/types/appointment';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		onNext,
	}: {
		appointmentId: string;
		onNext: (scenarios: ScenarioCard[]) => void;
	} = $props();

	let scenarios = $state<ScenarioCard[]>([]);
	let isLoading = $state(true);
	let loadError = $state('');

	$effect(() => {
		loadScenarios();
	});

	async function loadScenarios() {
		isLoading = true;
		loadError = '';
		try {
			const res = await apiClient.post(
				`/api/appointment-prep/${appointmentId}/scenarios` as '/api/appointment-prep/{id}/scenarios'
			);
			scenarios = res.scenarios;
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to generate scenarios. Please try again.';
			loadError = msg;
		} finally {
			isLoading = false;
		}
	}

	function handleNext() {
		onNext(scenarios);
	}
</script>

<div class="mx-auto max-w-2xl space-y-6">
	{#if isLoading}
		<div
			class="flex flex-col items-center gap-4 rounded-xl border border-neutral-200 bg-white p-8"
			aria-busy="true"
			role="status"
		>
			<div class="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600"></div>
			<p class="text-sm text-neutral-500" aria-live="polite">
				Generating practice scenarios… this may take a moment.
			</p>
		</div>
	{:else if loadError}
		<div class="rounded-xl border border-danger-light bg-danger-light p-4 text-sm text-danger-dark" role="alert">
			{loadError}
			<button
				type="button"
				onclick={loadScenarios}
				class="ml-2 font-medium underline hover:no-underline"
			>
				Try again
			</button>
		</div>
	{:else}
		<p class="text-sm text-neutral-600">
			Read through these scenarios before your appointment. They're tailored to your situation.
		</p>

		<div class="space-y-4">
			{#each scenarios as card (card.id)}
				<div class="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
					<h3 class="font-semibold text-neutral-800">{card.title}</h3>
					<p class="mt-1 text-sm italic text-neutral-500">{card.situation}</p>
					<div class="mt-3 rounded-lg bg-primary-50 p-3">
						<p class="text-sm text-primary-800">{card.suggestion}</p>
					</div>
					<span
						class="mt-2 inline-block rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-500"
					>
						{card.category.replace(/-/g, ' ')}
					</span>
				</div>
			{/each}
		</div>

		<button
			type="button"
			onclick={handleNext}
			class="w-full rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600"
		>
			I'm ready — get my materials
		</button>
	{/if}
</div>
