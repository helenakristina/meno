<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { ApiError } from '$lib/types';

	let {
		appointmentId,
		onStartOver,
		onError,
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
		<div class="rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
			<h2 class="text-lg font-semibold text-slate-800">Ready to generate your prep materials?</h2>
			<p class="mt-2 text-sm text-slate-500">
				We'll create a provider summary and a personal cheat sheet based on everything you've
				entered.
			</p>

			{#if generateError}
				<div
					class="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
					role="alert"
				>
					{generateError}
				</div>
			{/if}

			<button
				type="button"
				onclick={handleGenerate}
				disabled={isGenerating}
				class="mt-6 w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
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
			class="rounded-xl border border-teal-200 bg-teal-50 p-6 text-center"
			role="status"
			aria-live="polite"
		>
			<div class="text-3xl" aria-hidden="true">✓</div>
			<h2 class="mt-2 text-lg font-semibold text-teal-800">
				{message || 'Your appointment prep is ready!'}
			</h2>
			<p class="mt-1 text-sm text-teal-700">Take these documents to your appointment.</p>
		</div>

		<div class="space-y-3">
			<a
				href={summaryUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50"
			>
				<div>
					<p class="font-semibold text-slate-800">Provider Summary</p>
					<p class="text-sm text-slate-500">A clinical overview to share with your provider</p>
				</div>
				<span class="text-teal-600" aria-hidden="true">↓ PDF</span>
			</a>

			<a
				href={cheatsheetUrl}
				target="_blank"
				rel="noopener noreferrer"
				class="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50"
			>
				<div>
					<p class="font-semibold text-slate-800">Personal Cheat Sheet</p>
					<p class="text-sm text-slate-500">Your private reference for the appointment</p>
				</div>
				<span class="text-teal-600" aria-hidden="true">↓ PDF</span>
			</a>
		</div>

		<button
			type="button"
			onclick={onStartOver}
			class="w-full rounded-xl border border-slate-200 py-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
		>
			Start over
		</button>
	{/if}
</div>
