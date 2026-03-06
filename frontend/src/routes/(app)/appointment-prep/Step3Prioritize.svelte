<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import { DEFAULT_CONCERNS } from '$lib/types/appointment';
	import type { AppointmentContext, AppointmentGoal } from '$lib/types/appointment';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		context,
		onNext,
		onError,
	}: {
		appointmentId: string;
		context: AppointmentContext;
		onNext: (concerns: string[]) => void;
		onError: (msg: string) => void;
	} = $props();

	let concerns = $state<string[]>([...DEFAULT_CONCERNS[context.goal as AppointmentGoal]]);
	let newConcernText = $state('');
	let isSaving = $state(false);
	let dragSrcIndex = $state<number | null>(null);

	function moveUp(index: number) {
		if (index === 0) return;
		const updated = [...concerns];
		[updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
		concerns = updated;
	}

	function moveDown(index: number) {
		if (index === concerns.length - 1) return;
		const updated = [...concerns];
		[updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
		concerns = updated;
	}

	function removeConcern(index: number) {
		concerns = concerns.filter((_, i) => i !== index);
	}

	function addConcern() {
		const text = newConcernText.trim();
		if (!text) return;
		concerns = [...concerns, text];
		newConcernText = '';
	}

	function handleAddKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			addConcern();
		}
	}

	// Drag and drop handlers
	function handleDragStart(e: DragEvent, index: number) {
		dragSrcIndex = index;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'move';
		}
	}

	function handleDrop(e: DragEvent, targetIndex: number) {
		e.preventDefault();
		if (dragSrcIndex === null || dragSrcIndex === targetIndex) return;

		const updated = [...concerns];
		const [moved] = updated.splice(dragSrcIndex, 1);
		updated.splice(targetIndex, 0, moved);
		concerns = updated;
		dragSrcIndex = null;
	}

	function handleDragEnd() {
		dragSrcIndex = null;
	}

	async function handleNext() {
		if (concerns.length === 0) return;
		isSaving = true;
		try {
			await apiClient.put(
				`/api/appointment-prep/${appointmentId}/prioritize` as '/api/appointment-prep/{id}/prioritize',
				{ concerns }
			);
			onNext(concerns);
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to save concerns. Please try again.';
			onError(msg);
		} finally {
			isSaving = false;
		}
	}
</script>

<div class="mx-auto max-w-2xl space-y-6">
	<p class="text-sm text-slate-600">
		Drag to reorder, or use the arrows. Your top concern will be listed first in your materials.
	</p>

	<!-- Concerns list -->
	<ol class="space-y-2" aria-label="Prioritized concerns">
		{#each concerns as concern, i (concern + i)}
			<li
				draggable="true"
				ondragstart={(e) => handleDragStart(e, i)}
				ondragover={handleDragOver}
				ondrop={(e) => handleDrop(e, i)}
				ondragend={handleDragEnd}
				aria-label="Drag to reorder: {concern}"
				class="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition-opacity {dragSrcIndex === i
					? 'opacity-40'
					: 'opacity-100'}"
			>
				<!-- Drag handle -->
				<span
					class="cursor-grab select-none text-slate-400 active:cursor-grabbing"
					aria-hidden="true"
				>
					⠿
				</span>

				<!-- Number -->
				<span class="min-w-[1.5rem] text-sm font-semibold text-slate-500">{i + 1}.</span>

				<!-- Concern text -->
				<span class="flex-1 text-sm text-slate-800">{concern}</span>

				<!-- Up/down + remove -->
				<div class="flex items-center gap-1">
					<button
						type="button"
						onclick={() => moveUp(i)}
						disabled={i === 0}
						aria-label="Move '{concern}' up"
						class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30"
					>
						▲
					</button>
					<button
						type="button"
						onclick={() => moveDown(i)}
						disabled={i === concerns.length - 1}
						aria-label="Move '{concern}' down"
						class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 disabled:cursor-not-allowed disabled:opacity-30"
					>
						▼
					</button>
					<button
						type="button"
						onclick={() => removeConcern(i)}
						aria-label="Remove '{concern}'"
						class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
					>
						×
					</button>
				</div>
			</li>
		{/each}
	</ol>

	<!-- Add new concern -->
	<div class="flex gap-2">
		<input
			type="text"
			bind:value={newConcernText}
			onkeydown={handleAddKeydown}
			placeholder="Add a concern…"
			class="h-11 flex-1 rounded-xl border border-slate-200 px-4 text-sm text-slate-800 placeholder-slate-400 transition-colors focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-400/20"
			aria-label="New concern text"
		/>
		<button
			type="button"
			onclick={addConcern}
			disabled={!newConcernText.trim()}
			class="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
		>
			Add
		</button>
	</div>

	{#if concerns.length === 0}
		<p class="text-sm text-red-600">Add at least one concern to continue.</p>
	{/if}

	<button
		type="button"
		onclick={handleNext}
		disabled={concerns.length === 0 || isSaving}
		class="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
	>
		{isSaving ? 'Saving…' : 'Next: Practice scenarios'}
	</button>
</div>
