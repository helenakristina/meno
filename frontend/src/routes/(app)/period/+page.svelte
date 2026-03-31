<script lang="ts">
	import { onMount } from 'svelte';
	import { today, getLocalTimeZone, type DateValue, CalendarDate } from '@internationalized/date';
	import { apiClient } from '$lib/api/client';
	import { userSettings } from '$lib/stores/settings';
	import { get } from 'svelte/store';
	import PeriodCalendar from '$lib/components/period/PeriodCalendar.svelte';
	import PeriodLogModal from '$lib/components/period/PeriodLogModal.svelte';
	import type { FlowLevel, PeriodLog } from '$lib/types/period';

	type CycleAnalysis = {
		average_cycle_length: number | null;
		cycle_variability: number | null;
		months_since_last_period: number | null;
		inferred_stage: string | null;
		has_sufficient_data: boolean;
		calculated_at: string | null;
	};

	let logs = $state<PeriodLog[]>([]);
	let cycleAnalysis = $state<CycleAnalysis | null>(null);
	let journeyStage = $state<string | null>(null);
	let loadError = $state<string | null>(null);

	// Modal state
	let modalOpen = $state(false);
	let selectedDate = $state<DateValue | null>(null);
	let selectedLog = $state<PeriodLog | null>(null);

	// Bleeding alert banner (post-menopause)
	let bleedingAlertActive = $state(false);

	// Inference banner
	let bannerDismissed = $state(false);

	const showInferenceBanner = $derived(
		!bannerDismissed &&
			cycleAnalysis?.inferred_stage != null &&
			cycleAnalysis.inferred_stage !== journeyStage
	);

	let updatingStage = $state(false);

	function parseDateString(iso: string): CalendarDate {
		const [y, m, d] = iso.split('-').map(Number);
		return new CalendarDate(y, m, d);
	}

	async function loadData() {
		try {
			const [logsRes, analysisRes] = await Promise.all([
				apiClient.get<{ logs: PeriodLog[] }>('/api/period/logs'),
				apiClient.get('/api/period/analysis')
			]);

			// Reuse settings already fetched by the layout (avoid duplicate request)
			const cachedSettings = get(userSettings);
			journeyStage = cachedSettings?.journey_stage ?? null;

			const logsData = logsRes as { logs: PeriodLog[] };
			logs = logsData.logs;

			cycleAnalysis = analysisRes as CycleAnalysis;
		} catch {
			loadError = 'Unable to load period data. Please refresh and try again.';
		}
	}

	onMount(loadData);

	function handleDayClick(date: DateValue, existingLog: PeriodLog | null) {
		selectedDate = date;
		selectedLog = existingLog;
		modalOpen = true;
	}

	function handleLogToday() {
		selectedDate = today(getLocalTimeZone());
		selectedLog = null;
		modalOpen = true;
	}

	function handleSave(log: PeriodLog, bleedingAlert: boolean) {
		// Refresh logs list
		const existingIndex = logs.findIndex((l) => l.id === log.id);
		if (existingIndex >= 0) {
			logs = logs.map((l) => (l.id === log.id ? log : l));
		} else {
			logs = [log, ...logs];
		}
		if (bleedingAlert) bleedingAlertActive = true;
	}

	function handleDeleteLog(logId: string) {
		logs = logs.filter((l) => l.id !== logId);
	}

	async function handleUpdateJourneyStage() {
		if (!cycleAnalysis?.inferred_stage || updatingStage) return;
		updatingStage = true;
		try {
			await apiClient.patch('/api/users/settings', {
				journey_stage: cycleAnalysis.inferred_stage
			});
			journeyStage = cycleAnalysis.inferred_stage;
			bannerDismissed = true;
		} catch {
			// Fail silently — user can try again
		} finally {
			updatingStage = false;
		}
	}

	function formatStageLabel(stage: string | null): string {
		if (!stage) return '';
		const labels: Record<string, string> = {
			perimenopause: 'Perimenopause',
			menopause: 'Menopause',
			'post-menopause': 'Post-menopause',
			unsure: "I'm not sure"
		};
		return labels[stage] ?? stage;
	}
</script>

<svelte:head>
	<title>Cycles — Meno</title>
</svelte:head>

<div class="mx-auto max-w-xl">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold text-neutral-800">Cycles</h1>
		<button
			onclick={handleLogToday}
			class="rounded-lg bg-primary-500 px-4 py-2 text-sm font-medium text-white hover:bg-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-1"
		>
			Log today
		</button>
	</div>

	{#if loadError}
		<div class="rounded-md bg-danger-light p-4 text-sm text-danger-dark" role="alert">
			{loadError}
		</div>
	{:else}
		<!-- Postmenopausal bleeding alert banner -->
		{#if bleedingAlertActive}
			<div
				class="mb-6 rounded-lg border border-warning bg-warning-light px-4 py-4"
				role="alert"
				aria-live="assertive"
			>
				<div class="flex items-start justify-between gap-3">
					<div>
						<p class="text-sm font-medium text-warning-dark">Please contact your doctor</p>
						<p class="mt-0.5 text-sm text-warning">
							Postmenopausal bleeding should be evaluated by a healthcare provider promptly.
						</p>
					</div>
					<button
						onclick={() => (bleedingAlertActive = false)}
						class="shrink-0 rounded-full p-1 text-warning hover:bg-warning-light focus:outline-none focus-visible:ring-2 focus-visible:ring-warning"
						aria-label="Dismiss alert"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="size-4"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<path d="M18 6 6 18M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
		{/if}

		<!-- Inference banner -->
		{#if showInferenceBanner}
			<div
				class="mb-6 rounded-lg border border-primary-200 bg-primary-50 px-4 py-4"
				role="status"
				aria-live="polite"
			>
				<p class="text-sm font-medium text-primary-800">
					You haven't logged a period in {cycleAnalysis?.months_since_last_period} months.
				</p>
				<p class="mt-0.5 text-sm text-primary-700">
					Would you like to update your journey stage to
					<strong>{formatStageLabel(cycleAnalysis?.inferred_stage ?? null)}</strong>?
				</p>
				<div class="mt-3 flex gap-2">
					<button
						onclick={handleUpdateJourneyStage}
						disabled={updatingStage}
						class="rounded-md bg-primary-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 disabled:opacity-50"
					>
						{updatingStage ? 'Updating…' : 'Update'}
					</button>
					<button
						onclick={() => (bannerDismissed = true)}
						class="rounded-md border border-primary-200 px-3 py-1.5 text-xs font-medium text-primary-700 hover:bg-primary-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
					>
						Dismiss
					</button>
				</div>
			</div>
		{/if}

		<!-- Calendar -->
		<div class="rounded-lg border border-neutral-200 bg-white p-4 sm:p-6">
			<PeriodCalendar {logs} onDayClick={handleDayClick} />
		</div>

		<!-- Cycle summary (shown when there's enough data) -->
		{#if cycleAnalysis?.has_sufficient_data}
			<div class="mt-6 rounded-lg border border-neutral-200 bg-white p-4">
				<h2 class="mb-3 text-sm font-semibold text-neutral-700">Cycle Summary</h2>
				<dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#if cycleAnalysis.average_cycle_length != null}
						<div class="rounded-md bg-neutral-50 px-3 py-2">
							<dt class="text-xs text-neutral-500">Avg. cycle</dt>
							<dd class="mt-0.5 text-sm font-semibold text-neutral-800">
								{Math.round(cycleAnalysis.average_cycle_length)} days
							</dd>
						</div>
					{/if}
					{#if cycleAnalysis.months_since_last_period != null}
						<div class="rounded-md bg-neutral-50 px-3 py-2">
							<dt class="text-xs text-neutral-500">Months since last</dt>
							<dd class="mt-0.5 text-sm font-semibold text-neutral-800">
								{cycleAnalysis.months_since_last_period}
							</dd>
						</div>
					{/if}
					{#if cycleAnalysis.cycle_variability != null}
						<div class="rounded-md bg-neutral-50 px-3 py-2">
							<dt class="text-xs text-neutral-500">Variability</dt>
							<dd class="mt-0.5 text-sm font-semibold text-neutral-800">
								±{Math.round(cycleAnalysis.cycle_variability)} days
							</dd>
						</div>
					{/if}
				</dl>
			</div>
		{/if}
	{/if}
</div>

<!-- Period log modal -->
<PeriodLogModal
	bind:open={modalOpen}
	date={selectedDate}
	existingLog={selectedLog}
	{journeyStage}
	onSave={handleSave}
	onDelete={handleDeleteLog}
/>
