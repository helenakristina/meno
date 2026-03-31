<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { apiClient } from '$lib/api/client';
	import type { SymptomComparisonResponse, ComparisonRow } from '$lib/types/api';

	let loading = $state(true);
	let error = $state<string | null>(null);
	let data = $state<SymptomComparisonResponse | null>(null);

	const id = $derived(page.params.id);

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '—';
		return new Date(`${dateStr}T12:00:00`).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		});
	}

	function directionLabel(row: ComparisonRow): string {
		if (row.direction === 'improved') return 'Improved';
		if (row.direction === 'worsened') return 'Worsened';
		return 'Unchanged';
	}

	function directionIcon(row: ComparisonRow): string {
		if (row.direction === 'improved') return '↓';
		if (row.direction === 'worsened') return '↑';
		return '→';
	}

	function directionClasses(row: ComparisonRow): string {
		if (row.direction === 'improved') return 'text-success bg-success-light';
		if (row.direction === 'worsened') return 'text-danger-dark bg-danger-light';
		return 'text-neutral-500 bg-neutral-50';
	}

	function formatPct(pct: number): string {
		if (pct === 0) return '—';
		return `${Math.round(Math.abs(pct))}%`;
	}

	const isSparse = $derived(data ? data.before_is_sparse || data.after_is_sparse : false);

	onMount(async () => {
		try {
			data = await apiClient.get(`/api/medications/${id}/symptom-comparison` as any);
		} catch {
			error = 'Unable to load symptom comparison. Please go back and try again.';
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>
		{data ? `${data.medication_name} — Symptom Impact` : 'Symptom Impact'} — Meno
	</title>
</svelte:head>

<div class="mx-auto max-w-2xl">
	<div class="mb-6">
		<a
			href="/medications/{id}"
			class="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700"
		>
			<svg
				xmlns="http://www.w3.org/2000/svg"
				class="h-4 w-4"
				fill="none"
				viewBox="0 0 24 24"
				stroke="currentColor"
				stroke-width="2"
				aria-hidden="true"
			>
				<path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
			</svg>
			Back to medication
		</a>
	</div>

	{#if loading}
		<div class="space-y-4">
			<div class="h-8 w-64 animate-pulse rounded bg-neutral-200"></div>
			<div class="h-4 w-48 animate-pulse rounded bg-neutral-100"></div>
			<div class="mt-6 space-y-2">
				{#each { length: 5 } as _}
					<div class="h-12 animate-pulse rounded-lg bg-neutral-100"></div>
				{/each}
			</div>
		</div>
	{:else if error}
		<div class="rounded-md bg-danger-light p-4 text-sm text-danger-dark" role="alert">{error}</div>
	{:else if data}
		<div class="mb-6">
			<h1 class="text-2xl font-bold text-neutral-800">{data.medication_name}</h1>
			<p class="mt-1 text-sm text-neutral-500">Symptom impact — before vs. after starting</p>
		</div>

		<!-- Date windows -->
		{#if data.before_start && data.after_start}
			<div class="mb-6 grid grid-cols-2 gap-3">
				<div class="rounded-lg border border-neutral-200 bg-white p-3">
					<div class="mb-1 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
						Before
					</div>
					<div class="text-xs text-neutral-600">
						{formatDate(data.before_start)} – {formatDate(data.before_end)}
					</div>
				</div>
				<div class="rounded-lg border border-neutral-200 bg-white p-3">
					<div class="mb-1 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
						After
					</div>
					<div class="text-xs text-neutral-600">
						{formatDate(data.after_start)} – {formatDate(data.after_end)}
					</div>
				</div>
			</div>
		{/if}

		<!-- No after data yet -->
		{#if !data.has_after_data}
			<div
				class="mb-4 rounded-md border border-warning bg-warning-light p-3 text-sm text-warning-dark"
				role="note"
			>
				<span class="font-medium">No data after start date yet.</span> Keep logging symptoms to see how
				this medication affects you over time.
			</div>
		{/if}

		<!-- Sparse data warning -->
		{#if isSparse}
			<div
				class="mb-4 rounded-md border border-warning bg-warning-light p-3 text-sm text-warning-dark"
				role="note"
			>
				<span class="font-medium">Limited data</span> — results may not be representative. Log symptoms
				more consistently for a clearer picture.
			</div>
		{/if}

		<!-- Confounding changes warning -->
		{#if data.has_confounding_changes}
			<div
				class="mb-4 rounded-md border border-primary-200 bg-primary-50 p-3 text-sm text-primary-800"
				role="note"
			>
				<span class="font-medium">Note:</span> Other medication changes occurred during this window. Results
				may reflect multiple changes.
			</div>
		{/if}

		<!-- Comparison table -->
		{#if data.rows.length === 0}
			<div class="rounded-lg border border-dashed border-neutral-300 p-8 text-center">
				<p class="text-sm text-neutral-500">
					Not enough data yet to compare symptoms. Keep logging and check back later.
				</p>
			</div>
		{:else}
			<div class="overflow-hidden rounded-lg border border-neutral-200 bg-white">
				<!-- Column headers -->
				<div
					class="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 border-b border-neutral-200 px-4 py-2.5 text-xs font-semibold tracking-wide text-neutral-400 uppercase"
				>
					<div>Symptom</div>
					<div class="text-right">Before</div>
					<div class="text-right">After</div>
					<div class="text-right">Change</div>
				</div>

				<!-- Rows -->
				<ul class="divide-y divide-neutral-100" role="list">
					{#each data.rows as row (row.symptom_id)}
						<li class="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 px-4 py-3">
							<div>
								<div class="text-sm font-medium text-neutral-800">{row.symptom_name}</div>
								<div class="text-xs text-neutral-400">{row.category}</div>
							</div>
							<div class="text-right text-sm text-neutral-600">{Math.round(row.before_pct)}%</div>
							<div class="text-right text-sm text-neutral-600">{Math.round(row.after_pct)}%</div>
							<div class="text-right">
								<span
									class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium {directionClasses(
										row
									)}"
									aria-label={directionLabel(row)}
								>
									<span aria-hidden="true">{directionIcon(row)}</span>
									{formatPct(row.after_pct - row.before_pct)}
								</span>
							</div>
						</li>
					{/each}
				</ul>
			</div>

			<p class="mt-3 text-xs text-neutral-400">
				Frequency shown as percentage of days with that symptom logged. This is pattern data, not
				medical advice.
			</p>
		{/if}
	{/if}
</div>
