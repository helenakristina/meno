<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		onStartOver,
		onError
	}: {
		appointmentId: string;
		onStartOver: () => void;
		onError: (msg: string) => void;
	} = $props();

	let isGenerating = $state(false);
	let summaryUrl = $state('');
	let cheatsheetUrl = $state('');
	let message = $state('');
	let generateError = $state('');

	async function handleGenerate() {
		isGenerating = true;
		generateError = '';
		try {
			const res = await apiClient.post(
				`/api/appointment-prep/${appointmentId}/generate` as '/api/appointment-prep/{id}/generate'
			);
			summaryUrl = res.provider_summary_url;
			cheatsheetUrl = res.personal_cheat_sheet_url;
			message = res.message;
		} catch (e) {
			const msg =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to generate documents. Please try again.';
			generateError = msg;
			onError(msg);
		} finally {
			isGenerating = false;
		}
	}

	let isDone = $derived(!!summaryUrl && !!cheatsheetUrl);
</script>

<div class="mx-auto max-w-2xl space-y-6">
	{#if !isDone}
		<div class="rounded-xl border border-neutral-200 bg-white p-6 text-center shadow-sm">
			<h2 class="text-lg font-semibold text-neutral-800">Ready to generate your prep materials?</h2>
			<p class="mt-2 text-sm text-neutral-500">
				We'll create a provider summary and a personal cheat sheet based on everything you've
				entered.
			</p>

			{#if generateError}
				<div
					class="mt-4 rounded-lg border border-danger-light bg-danger-light p-3 text-sm text-danger-dark"
					role="alert"
				>
					{generateError}
				</div>
			{/if}

			<button
				type="button"
				onclick={handleGenerate}
				disabled={isGenerating}
				class="mt-6 w-full rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
			>
				{#if isGenerating}
					<span class="flex items-center justify-center gap-2">
						<span
							class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"
						></span>
						Generating your documents…
					</span>
				{:else}
					Generate my appointment prep
				{/if}
			</button>
		</div>
	{:else}
		<!-- Success state -->
		<div
			class="rounded-xl border border-primary-200 bg-primary-50 p-6 text-center"
			role="status"
			aria-live="polite"
		>
			<div class="text-3xl" aria-hidden="true">✓</div>
			<h2 class="mt-2 text-lg font-semibold text-primary-800">
				{message || 'Your appointment prep is ready!'}
			</h2>
			<p class="mt-1 text-sm text-primary-700">
				Your Provider Summary is ready to email ahead or hand to your provider. Your Personal Cheat
				Sheet is yours to carry in.
			</p>
		</div>

		<div class="space-y-3">
			<a
				href={summaryUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-4 shadow-sm transition-colors hover:border-primary-300 hover:bg-primary-50"
			>
				<div>
					<p class="font-semibold text-neutral-800">Provider Summary</p>
					<p class="text-sm text-neutral-500">A clinical overview to share with your provider</p>
				</div>
				<span class="text-primary-600" aria-hidden="true">↓ PDF</span>
			</a>

			<a
				href={cheatsheetUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="flex items-center justify-between rounded-xl border border-neutral-200 bg-white p-4 shadow-sm transition-colors hover:border-primary-300 hover:bg-primary-50"
			>
				<div>
					<p class="font-semibold text-neutral-800">Personal Cheat Sheet</p>
					<p class="text-sm text-neutral-500">Your private reference for the appointment</p>
				</div>
				<span class="text-primary-600" aria-hidden="true">↓ PDF</span>
			</a>
		</div>

		<div class="flex flex-col gap-3 sm:flex-row sm:gap-2">
			<button
				type="button"
				onclick={onStartOver}
				class="flex-1 rounded-xl border border-neutral-200 py-3 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
			>
				Start over
			</button>
			<a
				href="/appointment-prep/history"
				class="flex-1 rounded-xl border border-neutral-200 py-3 text-center text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
			>
				View all my preps
			</a>
		</div>
	{/if}
</div>
