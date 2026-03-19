<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { userSettings } from '$lib/stores/settings';
	import { goto } from '$app/navigation';
	import type { Medication } from '$lib/types/api';

	let loading = $state(true);
	let error = $state<string | null>(null);
	let allMedications = $state<Medication[]>([]);

	const currentMedications = $derived(allMedications.filter((m) => !m.end_date));
	const pastMedications = $derived(allMedications.filter((m) => !!m.end_date));

	onMount(async () => {
		// Wait a tick so the layout's onMount can populate userSettings first
		await new Promise((resolve) => setTimeout(resolve, 0));

		if ($userSettings !== null && !$userSettings.mht_tracking_enabled) {
			goto('/settings');
			return;
		}

		try {
			allMedications = await apiClient.get('/api/medications');
		} catch {
			error = 'Unable to load medications. Please refresh and try again.';
		} finally {
			loading = false;
		}
	});

	function formatDeliveryMethod(method: string): string {
		return method.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
	}

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString('en-GB', {
			day: 'numeric',
			month: 'short',
			year: 'numeric'
		});
	}
</script>

<svelte:head>
	<title>MHT Medications — Meno</title>
</svelte:head>

<div class="mx-auto max-w-2xl">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold text-slate-900">MHT Medications</h1>
		<a
			href="/medications/add"
			class="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
		>
			Add medication
		</a>
	</div>

	{#if loading}
		<div class="text-slate-600">Loading medications…</div>
	{:else if error}
		<div class="rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">{error}</div>
	{:else}
		<!-- Current medications -->
		<section class="mb-8">
			<h2 class="mb-3 text-base font-semibold text-slate-900">Current</h2>
			{#if currentMedications.length === 0}
				<div class="rounded-lg border border-dashed border-slate-300 p-6 text-center">
					<p class="text-sm text-slate-500">No active medications.</p>
					<a
						href="/medications/add"
						class="mt-2 inline-block text-sm font-medium text-slate-700 underline hover:text-slate-900"
					>
						Add your first medication
					</a>
				</div>
			{:else}
				<ul class="space-y-3">
					{#each currentMedications as med (med.id)}
						<li class="rounded-lg border border-slate-200 bg-white p-4">
							<div class="flex items-start justify-between">
								<div>
									<div class="text-sm font-semibold text-slate-900">{med.medication_name}</div>
									<div class="mt-0.5 text-xs text-slate-500">
										{med.dose} · {formatDeliveryMethod(med.delivery_method)}{med.frequency
											? ` · ${med.frequency.replace(/_/g, ' ')}`
											: ''}
									</div>
									<div class="mt-1 text-xs text-slate-400">
										Started {formatDate(med.start_date)}
									</div>
								</div>
								<div class="flex gap-2">
									<a
										href="/medications/{med.id}/impact"
										class="min-h-[44px] flex items-center rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
									>
										Impact
									</a>
									<a
										href="/medications/{med.id}"
										class="min-h-[44px] flex items-center rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
									>
										View
									</a>
								</div>
							</div>
						</li>
					{/each}
				</ul>
			{/if}
		</section>

		<!-- Past medications -->
		{#if pastMedications.length > 0}
			<section>
				<h2 class="mb-3 text-base font-semibold text-slate-900">Past</h2>
				<ul class="space-y-3">
					{#each pastMedications as med (med.id)}
						<li class="rounded-lg border border-slate-200 bg-white p-4 opacity-75">
							<div class="flex items-start justify-between">
								<div>
									<div class="text-sm font-semibold text-slate-900">{med.medication_name}</div>
									<div class="mt-0.5 text-xs text-slate-500">
										{med.dose} · {formatDeliveryMethod(med.delivery_method)}
									</div>
									<div class="mt-1 text-xs text-slate-400">
										{formatDate(med.start_date)} – {formatDate(med.end_date!)}
									</div>
								</div>
								<a
									href="/medications/{med.id}"
									class="min-h-[44px] flex items-center rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:border-slate-300 hover:bg-slate-50"
								>
									View
								</a>
							</div>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	{/if}
</div>
