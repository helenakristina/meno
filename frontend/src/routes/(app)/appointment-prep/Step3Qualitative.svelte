<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { QualitativeContext } from '$lib/types/appointment';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		onNext,
		onError
	}: {
		appointmentId: string;
		onNext: (ctx: QualitativeContext) => void;
		onError: (msg: string) => void;
	} = $props();

	let what_have_you_tried = $state('');
	let specific_ask = $state('');
	let history_clotting_risk = $state<'yes' | 'no' | 'not_sure' | null>(null);
	let history_breast_cancer = $state<'yes' | 'no' | 'not_sure' | null>(null);
	let isSaving = $state(false);

	async function handleNext() {
		isSaving = true;
		const payload: QualitativeContext = {
			what_have_you_tried: what_have_you_tried.trim() || null,
			specific_ask: specific_ask.trim() || null,
			history_clotting_risk: history_clotting_risk,
			history_breast_cancer: history_breast_cancer
		};
		try {
			await apiClient.put(
				`/api/appointment-prep/${appointmentId}/qualitative-context` as '/api/appointment-prep/{id}/qualitative-context',
				payload
			);
			onNext(payload);
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to save. Please try again.';
			onError(msg);
		} finally {
			isSaving = false;
		}
	}

	function handleSkip() {
		onNext({
			what_have_you_tried: null,
			specific_ask: null,
			history_clotting_risk: null,
			history_breast_cancer: null
		});
	}
</script>

<div class="mx-auto max-w-2xl space-y-6">
	<p class="text-sm text-neutral-600">
		This helps us write materials that sound like you, not a statistics report. All fields are
		optional.
	</p>

	<!-- What have you tried -->
	<div>
		<label for="what-tried" class="mb-1 block text-sm font-medium text-neutral-700">
			What have you already tried?
		</label>
		<p class="mb-2 text-xs text-neutral-500">
			Lifestyle changes, supplements, previous treatments — anything relevant.
		</p>
		<textarea
			id="what-tried"
			bind:value={what_have_you_tried}
			rows="3"
			maxlength="500"
			placeholder="e.g. Tried black cohosh for 6 weeks, sleep hygiene changes, reduced caffeine…"
			class="w-full rounded-xl border border-neutral-200 px-4 py-3 text-sm text-neutral-800 placeholder-neutral-400 transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 focus:outline-none"
		></textarea>
		<p class="mt-1 text-right text-xs text-neutral-400">{what_have_you_tried.length}/500</p>
	</div>

	<!-- Specific ask -->
	<div>
		<label for="specific-ask" class="mb-1 block text-sm font-medium text-neutral-700">
			What do you specifically want from this appointment?
		</label>
		<p class="mb-2 text-xs text-neutral-500">
			A referral, a specific test, a treatment to try — be as direct as you want.
		</p>
		<textarea
			id="specific-ask"
			bind:value={specific_ask}
			rows="2"
			maxlength="300"
			placeholder="e.g. I want to discuss starting hormone therapy, or I want a referral to a specialist…"
			class="w-full rounded-xl border border-neutral-200 px-4 py-3 text-sm text-neutral-800 placeholder-neutral-400 transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 focus:outline-none"
		></textarea>
		<p class="mt-1 text-right text-xs text-neutral-400">{specific_ask.length}/300</p>
	</div>

	<!-- Clotting risk -->
	<div>
		<p class="mb-2 text-sm font-medium text-neutral-700">
			Do you have a personal or family history of blood clots or clotting disorders?
		</p>
		<div class="flex flex-col gap-2" role="radiogroup" aria-label="History of clotting risk">
			{#each [['yes', 'Yes'], ['no', 'No'], ['not_sure', 'Not sure']] as [val, label]}
				<label class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-neutral-50">
					<input
						type="radio"
						name="clotting"
						value={val}
						checked={history_clotting_risk === val}
						onchange={() => (history_clotting_risk = val as 'yes' | 'no' | 'not_sure')}
						class="h-4 w-4 text-primary-500 focus:ring-primary-400"
					/>
					<span class="text-sm text-neutral-700">{label}</span>
				</label>
			{/each}
		</div>
		{#if history_clotting_risk === 'yes'}
			<p class="mt-2 rounded-lg bg-warning-light px-3 py-2 text-xs text-warning-dark">
				We'll make sure your materials note this. Discuss with your provider how it affects your
				options.
			</p>
		{/if}
	</div>

	<!-- Breast cancer risk -->
	<div>
		<p class="mb-2 text-sm font-medium text-neutral-700">
			Do you have a personal or family history of breast cancer?
		</p>
		<div class="flex flex-col gap-2" role="radiogroup" aria-label="History of breast cancer">
			{#each [['yes', 'Yes'], ['no', 'No'], ['not_sure', 'Not sure']] as [val, label]}
				<label class="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-neutral-50">
					<input
						type="radio"
						name="breast-cancer"
						value={val}
						checked={history_breast_cancer === val}
						onchange={() => (history_breast_cancer = val as 'yes' | 'no' | 'not_sure')}
						class="h-4 w-4 text-primary-500 focus:ring-primary-400"
					/>
					<span class="text-sm text-neutral-700">{label}</span>
				</label>
			{/each}
		</div>
		{#if history_breast_cancer === 'yes'}
			<p class="mt-2 rounded-lg bg-warning-light px-3 py-2 text-xs text-warning-dark">
				We'll make sure your materials note this. Discuss with your provider how it affects your
				options.
			</p>
		{/if}
	</div>

	<div class="flex flex-col gap-3 sm:flex-row sm:gap-2">
		<button
			type="button"
			onclick={handleSkip}
			class="flex-1 rounded-xl border border-neutral-200 py-3 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
		>
			Skip this step
		</button>
		<button
			type="button"
			onclick={handleNext}
			disabled={isSaving}
			class="flex-1 rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
		>
			{isSaving ? 'Saving…' : 'Next: Practice scenarios'}
		</button>
	</div>
</div>
