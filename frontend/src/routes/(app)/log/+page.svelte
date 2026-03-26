<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase/client';
	import { apiClient } from '$lib/api/client';
	import { SkeletonLoader } from '$lib/components/shared';

	const CARDS_VISIBLE = 8;

	interface Symptom {
		id: string;
		name: string;
		category: string;
		sort_order: number;
	}

	let allSymptoms: Symptom[] = $state([]);
	let selectedSymptoms: Symptom[] = $state([]);
	let dismissedIds: string[] = $state([]);
	let freeText = $state('');
	let loadingSymptoms = $state(true);
	let submitting = $state(false);
	let error = $state('');
	let success = $state(false);

	let availableSymptoms: Symptom[] = $derived(
		allSymptoms.filter(
			(s) => !selectedSymptoms.some((sel) => sel.id === s.id) && !dismissedIds.includes(s.id)
		)
	);

	let visibleCards: Symptom[] = $derived(availableSymptoms.slice(0, CARDS_VISIBLE));

	let poolExhausted: boolean = $derived(availableSymptoms.length === 0);

	let canSubmit: boolean = $derived(selectedSymptoms.length > 0 || freeText.trim().length > 0);

	let source: 'cards' | 'text' | 'both' = $derived(
		selectedSymptoms.length > 0 && freeText.trim().length > 0
			? 'both'
			: selectedSymptoms.length > 0
				? 'cards'
				: 'text'
	);

	onMount(async () => {
		const { data, error: fetchError } = await supabase
			.from('symptoms_reference')
			.select('*')
			.order('sort_order');

		if (fetchError) {
			error = 'Failed to load symptoms. Please refresh the page.';
		} else {
			allSymptoms = data ?? [];
		}
		loadingSymptoms = false;
	});

	function selectCard(symptom: Symptom) {
		selectedSymptoms = [...selectedSymptoms, symptom];
	}

	function dismissCard(symptom: Symptom) {
		dismissedIds = [...dismissedIds, symptom.id];
	}

	function deselectChip(symptom: Symptom) {
		selectedSymptoms = selectedSymptoms.filter((s) => s.id !== symptom.id);
	}

	async function handleSubmit() {
		if (!canSubmit || submitting) return;
		submitting = true;
		error = '';

		try {
			const currentSource = source;
			await apiClient.post('/api/symptoms/logs', {
				source: currentSource,
				symptoms: currentSource !== 'text' ? selectedSymptoms.map((s) => s.id) : [],
				free_text_entry: freeText.trim() || null
			});

			success = true;
			selectedSymptoms = [];
			dismissedIds = [];
			freeText = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save log. Please try again.';
			console.error('Submit error:', e);
		} finally {
			submitting = false;
		}
	}

	function goToDashboard() {
		goto('/dashboard');
	}
</script>

<svelte:head>
	<title>Log Symptoms - Meno</title>
</svelte:head>

<div class="w-full max-w-full overflow-hidden px-4 py-8 sm:px-6 lg:px-8">
	<section class="mb-8" aria-label="Page header">
		<h1 class="text-2xl font-bold text-neutral-800">Log Today's Symptoms</h1>
		<p class="mt-1 text-neutral-500">Select the symptoms you're experiencing today.</p>
	</section>

	{#if success}
		<section
			in:fly={{ y: -10, duration: 300 }}
			class="rounded-2xl border border-success-light bg-success-light p-10 text-center"
			aria-label="Success message"
		>
			<div
				class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-success-light"
				aria-hidden="true"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-6 w-6 text-success"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
				</svg>
			</div>
			<h2 class="text-xl font-semibold text-success-dark">Log saved!</h2>
			<p class="mt-1 text-sm text-success">Your symptoms have been recorded for today.</p>
			<button
				onclick={goToDashboard}
				class="mt-6 rounded-lg border border-neutral-300 bg-white px-5 py-2.5 text-sm font-semibold text-neutral-700 transition-colors hover:bg-neutral-50"
			>
				Go to Dashboard
			</button>
		</section>
	{:else if loadingSymptoms}
		<section class="mb-6" aria-label="Loading symptoms">
			<p class="mb-3 text-sm text-neutral-500">
				Tap a symptom to log it — or dismiss it to see more options
			</p>
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
				{#each Array(8) as _}
					<div class="rounded-xl border border-neutral-200 bg-white shadow-sm">
						<SkeletonLoader variant="text" lines={1} height="h-6" />
					</div>
				{/each}
			</div>
		</section>
	{:else}
		<!-- Symptom card area -->
		{#if !poolExhausted}
			<section class="mb-6" aria-label="Available symptoms">
				<p class="mb-3 text-sm text-neutral-500">
					Tap a symptom to log it — or dismiss it to see more options
				</p>
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
					{#each visibleCards as card (card.id)}
						<div
							in:fly={{ y: 10, duration: 200 }}
							out:fly={{ y: -6, duration: 150 }}
							class="relative flex flex-col rounded-xl border border-neutral-200 bg-white shadow-sm transition-all duration-150 hover:border-primary-300 hover:bg-primary-50 hover:shadow"
						>
							<!-- Dismiss button - always visible in top-right -->
							<button
								onclick={(e) => {
									e.stopPropagation();
									dismissCard(card);
								}}
								aria-label="Dismiss {card.name}"
								class="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-300"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									class="h-4 w-4"
									viewBox="0 0 20 20"
									fill="currentColor"
									aria-hidden="true"
								>
									<path
										fill-rule="evenodd"
										d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>

							<!-- Card content -->
							<button
								onclick={() => selectCard(card)}
								class="flex flex-1 items-center justify-center px-4 py-6 text-left text-sm font-medium text-neutral-700 transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
							>
								{card.name}
							</button>
						</div>
					{/each}
				</div>
			</section>
		{:else if selectedSymptoms.length === 0}
			<section
				in:fade={{ duration: 200 }}
				class="mb-6 rounded-xl border border-dashed border-neutral-300 bg-neutral-50 py-8 text-center"
				aria-label="All symptoms reviewed"
			>
				<p class="text-sm text-neutral-400">
					All symptoms reviewed. Use the text box below to describe anything else.
				</p>
			</section>
		{/if}

		<!-- Selected symptom tray -->
		{#if selectedSymptoms.length > 0}
			<section
				in:fly={{ y: 6, duration: 200 }}
				class="mb-5 rounded-xl border border-primary-100 bg-primary-50/60 p-4"
				aria-label="Selected symptoms"
			>
				<p class="mb-3 text-xs font-semibold uppercase tracking-wide text-primary-600">
					{selectedSymptoms.length} symptom{selectedSymptoms.length === 1 ? '' : 's'} selected
				</p>
				<div class="flex flex-wrap gap-2">
					{#each selectedSymptoms as symptom (symptom.id)}
						<span
							in:fly={{ x: -4, duration: 150 }}
							out:fade={{ duration: 100 }}
							class="flex items-center gap-1.5 rounded-full bg-primary-100 py-1 pl-3 pr-2 text-sm font-medium text-primary-800"
						>
							{symptom.name}
							<button
								onclick={() => deselectChip(symptom)}
								aria-label="Remove {symptom.name}"
								class="flex h-4 w-4 items-center justify-center rounded-full text-primary-400 transition-colors hover:bg-primary-200 hover:text-primary-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									class="h-2.5 w-2.5"
									viewBox="0 0 20 20"
									fill="currentColor"
									aria-hidden="true"
								>
									<path
										fill-rule="evenodd"
										d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>
						</span>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Form inputs section -->
		<section class="mb-6" aria-label="Log entry form">
			<!-- Free text entry -->
			<div class="mb-6">
				<textarea
					bind:value={freeText}
					placeholder="Describe anything else in your own words..."
					rows="3"
					class="w-full resize-none rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700 shadow-sm transition-colors placeholder:text-neutral-400 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-200"
				></textarea>
			</div>

			<!-- Error message -->
			{#if error}
				<div
					in:fly={{ y: -4, duration: 200 }}
					class="mb-4 rounded-lg border border-danger-light bg-danger-light px-4 py-3 text-sm text-danger-dark"
					role="alert"
					aria-live="assertive"
				>
					{error}
				</div>
			{/if}

			<!-- Submit button -->
			<button
				onclick={handleSubmit}
				disabled={!canSubmit || submitting}
				class="w-full rounded-xl bg-primary-500 px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-600 disabled:cursor-not-allowed disabled:bg-neutral-200 disabled:text-neutral-400"
			>
				{submitting ? 'Saving...' : "Save Today's Log"}
			</button>
		</section>
	{/if}
</div>
