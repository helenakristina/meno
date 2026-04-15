<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import type {
		AppointmentPrepHistory,
		AppointmentPrepHistoryResponse
	} from '$lib/types/appointment';

	let preps = $state<AppointmentPrepHistory[]>([]);
	let total = $state(0);
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let limit = $state(50);
	let offset = $state(0);

	onMount(async () => {
		await loadHistory();
	});

	async function loadHistory() {
		isLoading = true;
		error = null;

		try {
			const response = await apiClient.get<AppointmentPrepHistoryResponse>(
				'/api/appointment-prep/history',
				{
					limit: limit.toString(),
					offset: offset.toString()
				}
			);
			preps = response.preps;
			total = response.total;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load history';
			console.error('Failed to load appointment prep history:', err);
		} finally {
			isLoading = false;
		}
	}

	function formatDate(dateString: string): string {
		const date = new Date(dateString);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'long',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function handlePrevPage() {
		if (offset > 0) {
			offset = Math.max(0, offset - limit);
			loadHistory();
		}
	}

	function handleNextPage() {
		if (offset + limit < total) {
			offset = offset + limit;
			loadHistory();
		}
	}
</script>

<svelte:head>
	<title>Appointment Prep History - Meno</title>
</svelte:head>

<div class="space-y-6">
	<!-- Header -->
	<div>
		<h1 class="text-2xl font-bold text-neutral-800">Your Appointment Preps</h1>
		<p class="mt-1 text-neutral-600">
			Access all of your generated appointment preparation documents
		</p>
	</div>

	<!-- Loading state -->
	{#if isLoading}
		<div class="flex justify-center py-12">
			<div class="text-neutral-500">Loading...</div>
		</div>
	{:else if error}
		<!-- Error state -->
		<div class="rounded-lg border border-danger-light bg-danger-light p-4 text-danger-dark">
			<p class="font-semibold">Unable to load history</p>
			<p class="mt-1 text-sm">{error}</p>
		</div>
	{:else if preps.length === 0}
		<!-- Empty state -->
		<div class="rounded-lg bg-neutral-50 p-8 text-center">
			<p class="mb-4 font-medium text-neutral-600">No appointment preps yet.</p>
			<a
				href="/appointment-prep"
				class="inline-block rounded-lg bg-primary-500 px-6 py-2 text-white transition-colors hover:bg-primary-600"
			>
				Create your first appointment prep
			</a>
		</div>
	{:else}
		<!-- History list -->
		<div class="space-y-3">
			{#each preps as prep (prep.id)}
				<div
					class="rounded-lg border border-neutral-200 p-4 transition-colors hover:border-neutral-300"
				>
					<div class="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
						<div class="min-w-0 flex-1">
							<p class="font-semibold text-neutral-800">
								Generated {formatDate(prep.generated_at)}
							</p>
							<p class="text-sm text-neutral-600">
								Appointment ID: <code class="font-mono">{prep.appointment_id.slice(0, 8)}...</code>
							</p>
						</div>
						<div class="flex w-full gap-2 sm:w-auto">
							<a
								href={prep.provider_summary_path}
								target="_blank"
								rel="noopener noreferrer"
								class="flex min-h-10 flex-1 items-center justify-center rounded-lg bg-primary-500 px-4 py-2 text-center text-sm text-white transition-colors hover:bg-primary-600 sm:flex-none"
							>
								Provider Summary
							</a>
							<a
								href={prep.personal_cheatsheet_path}
								target="_blank"
								rel="noopener noreferrer"
								class="flex min-h-10 flex-1 items-center justify-center rounded-lg bg-primary-500 px-4 py-2 text-center text-sm text-white transition-colors hover:bg-primary-600 sm:flex-none"
							>
								Cheat Sheet
							</a>
						</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Pagination info and controls -->
		<div class="flex flex-col items-center justify-between gap-4 pt-4 sm:flex-row">
			<p class="text-sm text-neutral-600">
				Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} appointment preps
			</p>
			<div class="flex gap-2">
				<button
					onclick={handlePrevPage}
					disabled={offset === 0}
					class="min-h-10 rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					Previous
				</button>
				<button
					onclick={handleNextPage}
					disabled={offset + limit >= total}
					class="min-h-10 rounded-lg border border-neutral-200 px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50"
				>
					Next
				</button>
			</div>
		</div>
	{/if}
</div>
