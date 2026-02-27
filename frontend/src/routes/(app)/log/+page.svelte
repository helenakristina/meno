<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { supabase } from '$lib/supabase/client';
	import { apiClient } from '$lib/api/client';

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

	function resetForm() {
		success = false;
		error = '';
	}
</script>

<div class="px-4 py-8 sm:px-0">
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-slate-900">Log Today's Symptoms</h1>
		<p class="mt-1 text-slate-500">Select the symptoms you're experiencing today.</p>
	</div>

	{#if success}
		<div
			in:fly={{ y: -10, duration: 300 }}
			class="rounded-2xl border border-emerald-200 bg-emerald-50 p-10 text-center"
		>
			<div
				class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-6 w-6 text-emerald-600"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
				</svg>
			</div>
			<h2 class="text-xl font-semibold text-emerald-800">Log saved!</h2>
			<p class="mt-1 text-sm text-emerald-700">Your symptoms have been recorded for today.</p>
			<button
				onclick={resetForm}
				class="mt-6 rounded-lg border border-emerald-300 bg-white px-5 py-2.5 text-sm font-medium text-emerald-800 transition-colors hover:bg-emerald-50"
			>
				Log more symptoms
			</button>
		</div>
	{:else if loadingSymptoms}
		<div class="flex items-center justify-center py-16">
			<div class="text-sm text-slate-400">Loading symptoms...</div>
		</div>
	{:else}
		<!-- Symptom card area -->
		{#if !poolExhausted}
			<section class="mb-6" aria-label="Available symptoms">
				<p class="mb-3 text-sm text-slate-500">
					Tap a symptom to log it — or dismiss it to see more options
				</p>
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
					{#each visibleCards as card (card.id)}
						<div
							in:fly={{ y: 10, duration: 200 }}
							out:fly={{ y: -6, duration: 150 }}
							class="group relative"
						>
							<button
								onclick={() => selectCard(card)}
								class="w-full rounded-xl border border-slate-200 bg-white px-4 py-4 text-left text-sm font-medium text-slate-700 shadow-sm transition-all duration-150 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
							>
								{card.name}
							</button>
							<button
								onclick={(e) => {
									e.stopPropagation();
									dismissCard(card);
								}}
								aria-label="Dismiss {card.name}"
								class="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 opacity-0 shadow-sm transition-all hover:border-red-200 hover:bg-red-50 hover:text-red-400 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
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
						</div>
					{/each}
				</div>
			</section>
		{:else if selectedSymptoms.length === 0}
			<div
				in:fade={{ duration: 200 }}
				class="mb-6 rounded-xl border border-dashed border-slate-300 bg-slate-50 py-8 text-center"
			>
				<p class="text-sm text-slate-400">
					All symptoms reviewed. Use the text box below to describe anything else.
				</p>
			</div>
		{/if}

		<!-- Selected symptom tray -->
		{#if selectedSymptoms.length > 0}
			<section
				in:fly={{ y: 6, duration: 200 }}
				class="mb-5 rounded-xl border border-teal-100 bg-teal-50/60 p-4"
				aria-label="Selected symptoms"
			>
				<p class="mb-3 text-xs font-semibold uppercase tracking-wide text-teal-600">
					{selectedSymptoms.length} symptom{selectedSymptoms.length === 1 ? '' : 's'} selected
				</p>
				<div class="flex flex-wrap gap-2">
					{#each selectedSymptoms as symptom (symptom.id)}
						<span
							in:fly={{ x: -4, duration: 150 }}
							out:fade={{ duration: 100 }}
							class="flex items-center gap-1.5 rounded-full bg-teal-100 py-1 pl-3 pr-2 text-sm font-medium text-teal-800"
						>
							{symptom.name}
							<button
								onclick={() => deselectChip(symptom)}
								aria-label="Remove {symptom.name}"
								class="flex h-4 w-4 items-center justify-center rounded-full text-teal-400 transition-colors hover:bg-teal-200 hover:text-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
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

		<!-- Free text entry -->
		<div class="mb-6">
			<textarea
				bind:value={freeText}
				placeholder="Describe anything else in your own words..."
				rows="3"
				class="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm transition-colors placeholder:text-slate-400 focus:border-teal-300 focus:outline-none focus:ring-2 focus:ring-teal-200"
			></textarea>
		</div>

		<!-- Error message -->
		{#if error}
			<div
				in:fly={{ y: -4, duration: 200 }}
				class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
			>
				{error}
			</div>
		{/if}

		<!-- Submit button -->
		<button
			onclick={handleSubmit}
			disabled={!canSubmit || submitting}
			class="w-full rounded-xl bg-slate-900 px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
		>
			{submitting ? 'Saving...' : "Save Today's Log"}
		</button>
	{/if}
</div>
