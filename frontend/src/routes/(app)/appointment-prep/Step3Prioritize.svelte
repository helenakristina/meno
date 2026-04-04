<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import { DEFAULT_CONCERNS } from '$lib/types/appointment';
	import type { AppointmentContext, AppointmentGoal, Concern } from '$lib/types/appointment';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		context,
		onNext,
		onError
	}: {
		appointmentId: string;
		context: AppointmentContext;
		onNext: (concerns: Concern[]) => void;
		onError: (msg: string) => void;
	} = $props();

	let concerns = $state<Concern[]>(
		DEFAULT_CONCERNS[context.goal as AppointmentGoal].map((text) => ({ text }))
	);
	let newConcernText = $state('');
	let isSaving = $state(false);
	let dragSrcIndex = $state<number | null>(null);
	let expandedCommentIndex = $state<number | null>(null);

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
		concerns = [...concerns, { text }];
		newConcernText = '';
	}

	function handleAddKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			addConcern();
		}
	}

	function updateComment(index: number, comment: string) {
		const updated = [...concerns];
		updated[index] = { ...updated[index], comment: comment || undefined };
		concerns = updated;
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
	<p class="text-sm text-neutral-600">
		Put what matters most first. Providers often only get to the first few topics raised — lead with
		what you need most from this appointment.
	</p>

	<!-- Concerns list -->
	<ol class="space-y-2" aria-label="Prioritized concerns">
		{#each concerns as concern, i (concern.text + i)}
			<li
				draggable="true"
				ondragstart={(e) => handleDragStart(e, i)}
				ondragover={handleDragOver}
				ondrop={(e) => handleDrop(e, i)}
				ondragend={handleDragEnd}
				aria-label="Drag to reorder: {concern.text}"
				class="rounded-xl border border-neutral-200 bg-white shadow-sm transition-opacity {dragSrcIndex ===
				i
					? 'opacity-40'
					: 'opacity-100'}"
			>
				<div class="flex items-center gap-3 px-4 py-3">
					<!-- Drag handle -->
					<span
						class="cursor-grab text-neutral-400 select-none active:cursor-grabbing"
						aria-hidden="true"
					>
						⠿
					</span>

					<!-- Number -->
					<span class="min-w-[1.5rem] text-sm font-semibold text-neutral-500">{i + 1}.</span>

					<!-- Concern text -->
					<span class="flex-1 text-sm text-neutral-800">{concern.text}</span>

					<!-- Comment toggle + Up/down + remove -->
					<div class="flex items-center gap-1">
						<button
							type="button"
							onclick={() =>
								(expandedCommentIndex = expandedCommentIndex === i ? null : i)}
							aria-label="{expandedCommentIndex === i ? 'Hide' : 'Add'} context for '{concern.text}'"
							aria-expanded={expandedCommentIndex === i}
							class="flex h-11 w-11 items-center justify-center rounded-lg text-xs text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600"
							title="Add context"
						>
							+
						</button>
						<button
							type="button"
							onclick={() => moveUp(i)}
							disabled={i === 0}
							aria-label="Move '{concern.text}' up"
							class="flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 disabled:cursor-not-allowed disabled:opacity-30"
						>
							▲
						</button>
						<button
							type="button"
							onclick={() => moveDown(i)}
							disabled={i === concerns.length - 1}
							aria-label="Move '{concern.text}' down"
							class="flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 disabled:cursor-not-allowed disabled:opacity-30"
						>
							▼
						</button>
						<button
							type="button"
							onclick={() => removeConcern(i)}
							aria-label="Remove '{concern.text}'"
							class="flex h-11 w-11 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-danger-light hover:text-danger"
						>
							×
						</button>
					</div>
				</div>

				{#if expandedCommentIndex === i}
					<div class="border-t border-neutral-100 px-4 pb-3">
						<textarea
							rows="2"
							value={concern.comment ?? ''}
							oninput={(e) => updateComment(i, (e.currentTarget as HTMLTextAreaElement).value)}
							placeholder="What specifically do you want your provider to know about this? (optional)"
							maxlength="200"
							class="mt-2 w-full rounded-lg border border-neutral-200 px-3 py-2 text-xs text-neutral-700 placeholder-neutral-400 transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 focus:outline-none"
							aria-label="Additional context for '{concern.text}'"
						></textarea>
						<p class="mt-1 text-right text-xs text-neutral-400">
							{(concern.comment ?? '').length}/200
						</p>
					</div>
				{/if}
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
			class="h-11 flex-1 rounded-xl border border-neutral-200 px-4 text-sm text-neutral-800 placeholder-neutral-400 transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 focus:outline-none"
			aria-label="New concern text"
		/>
		<button
			type="button"
			onclick={addConcern}
			disabled={!newConcernText.trim()}
			class="rounded-xl bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-200 disabled:cursor-not-allowed disabled:opacity-40"
		>
			Add
		</button>
	</div>

	{#if concerns.length === 0}
		<p class="text-sm text-danger">Add at least one concern to continue.</p>
	{/if}

	<button
		type="button"
		onclick={handleNext}
		disabled={concerns.length === 0 || isSaving}
		class="w-full rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
	>
		{isSaving ? 'Saving…' : 'Next: A little more about you'}
	</button>
</div>
