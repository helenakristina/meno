<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import type { AppointmentPrepHistory, AppointmentPrepHistoryResponse } from '$lib/types/appointment';

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

	function downloadPdf(url: string, filename: string) {
		const link = document.createElement('a');
		link.href = url;
		link.download = filename;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
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

<div class="space-y-6">
	<!-- Header -->
	<div>
		<h1 class="text-2xl font-bold text-slate-900">Your Appointment Preps</h1>
		<p class="text-slate-600 mt-1">Access all of your generated appointment preparation documents</p>
	</div>

	<!-- Loading state -->
	{#if isLoading}
		<div class="flex justify-center py-12">
			<div class="text-slate-500">Loading...</div>
		</div>
	{:else if error}
		<!-- Error state -->
		<div class="rounded-lg bg-red-50 p-4 text-red-700 border border-red-200">
			<p class="font-semibold">Unable to load history</p>
			<p class="text-sm mt-1">{error}</p>
		</div>
	{:else if preps.length === 0}
		<!-- Empty state -->
		<div class="rounded-lg bg-slate-50 p-8 text-center">
			<p class="text-slate-600 font-medium mb-4">No appointment preps yet.</p>
			<a
				href="/appointment-prep"
				class="inline-block rounded-lg bg-teal-600 px-6 py-2 text-white hover:bg-teal-700 transition-colors"
			>
				Create your first appointment prep
			</a>
		</div>
	{:else}
		<!-- History list -->
		<div class="space-y-3">
			{#each preps as prep (prep.id)}
				<div class="rounded-lg border border-slate-200 p-4 hover:border-slate-300 transition-colors">
					<div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
						<div class="flex-1 min-w-0">
							<p class="font-semibold text-slate-900">Generated {formatDate(prep.generated_at)}</p>
							<p class="text-sm text-slate-600">
								Appointment ID: <code class="font-mono">{prep.appointment_id.slice(0, 8)}...</code>
							</p>
						</div>
						<div class="flex gap-2 w-full sm:w-auto">
							<a
								href={prep.provider_summary_path}
								download={`provider-summary-${prep.appointment_id.slice(0, 8)}.pdf`}
								class="flex-1 sm:flex-none rounded-lg bg-teal-600 px-4 py-2 text-sm text-white text-center hover:bg-teal-700 transition-colors min-h-10 flex items-center justify-center"
							>
								Provider Summary
							</a>
							<a
								href={prep.personal_cheatsheet_path}
								download={`cheat-sheet-${prep.appointment_id.slice(0, 8)}.pdf`}
								class="flex-1 sm:flex-none rounded-lg bg-teal-600 px-4 py-2 text-sm text-white text-center hover:bg-teal-700 transition-colors min-h-10 flex items-center justify-center"
							>
								Cheat Sheet
							</a>
						</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Pagination info and controls -->
		<div class="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4">
			<p class="text-sm text-slate-600">
				Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} appointment preps
			</p>
			<div class="flex gap-2">
				<button
					onclick={handlePrevPage}
					disabled={offset === 0}
					class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-10"
				>
					Previous
				</button>
				<button
					onclick={handleNextPage}
					disabled={offset + limit >= total}
					class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-10"
				>
					Next
				</button>
			</div>
		</div>
	{/if}
</div>
