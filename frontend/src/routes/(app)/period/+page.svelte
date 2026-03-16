<script lang="ts">
	import { onMount } from 'svelte';
	import { today, getLocalTimeZone, type DateValue, CalendarDate } from '@internationalized/date';
	import { apiClient } from '$lib/api/client';
	import PeriodCalendar from '$lib/components/period/PeriodCalendar.svelte';
	import PeriodLogModal from '$lib/components/period/PeriodLogModal.svelte';

	type FlowLevel = 'spotting' | 'light' | 'medium' | 'heavy';

	type PeriodLog = {
		id: string;
		period_start: string;
		period_end: string | null;
		flow_level: FlowLevel | null;
		notes: string | null;
		cycle_length: number | null;
		created_at: string;
	};

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
			const [settingsRes, logsRes, analysisRes] = await Promise.all([
				apiClient.get('/api/users/settings'),
				apiClient.get<{ logs: PeriodLog[]; total: number }>('/api/period/logs'),
				apiClient.get('/api/period/analysis')
			]);

			const settings = settingsRes as { period_tracking_enabled: boolean; journey_stage: string | null };
			journeyStage = settings.journey_stage;

			const logsData = logsRes as { logs: PeriodLog[]; total: number };
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
		<h1 class="text-2xl font-bold text-slate-900">Cycles</h1>
		<button
			onclick={handleLogToday}
			class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400 focus-visible:ring-offset-1"
		>
			Log today
		</button>
	</div>

	{#if loadError}
		<div class="rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">
			{loadError}
		</div>
	{:else}
		<!-- Inference banner -->
		{#if showInferenceBanner}
			<div
				class="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-4"
				role="status"
				aria-live="polite"
			>
				<p class="text-sm font-medium text-emerald-900">
					You haven't logged a period in {cycleAnalysis?.months_since_last_period} months.
				</p>
				<p class="mt-0.5 text-sm text-emerald-700">
					Would you like to update your journey stage to
					<strong>{formatStageLabel(cycleAnalysis?.inferred_stage ?? null)}</strong>?
				</p>
				<div class="mt-3 flex gap-2">
					<button
						onclick={handleUpdateJourneyStage}
						disabled={updatingStage}
						class="rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-800 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
					>
						{updatingStage ? 'Updating…' : 'Update'}
					</button>
					<button
						onclick={() => (bannerDismissed = true)}
						class="rounded-md border border-emerald-300 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
					>
						Dismiss
					</button>
				</div>
			</div>
		{/if}

		<!-- Calendar -->
		<div class="rounded-lg border border-slate-200 bg-white p-4 sm:p-6">
			<PeriodCalendar {logs} onDayClick={handleDayClick} />
		</div>

		<!-- Cycle summary (shown when there's enough data) -->
		{#if cycleAnalysis?.has_sufficient_data}
			<div class="mt-6 rounded-lg border border-slate-200 bg-white p-4">
				<h2 class="mb-3 text-sm font-semibold text-slate-700">Cycle Summary</h2>
				<dl class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#if cycleAnalysis.average_cycle_length != null}
						<div class="rounded-md bg-slate-50 px-3 py-2">
							<dt class="text-xs text-slate-500">Avg. cycle</dt>
							<dd class="mt-0.5 text-sm font-semibold text-slate-900">
								{Math.round(cycleAnalysis.average_cycle_length)} days
							</dd>
						</div>
					{/if}
					{#if cycleAnalysis.months_since_last_period != null}
						<div class="rounded-md bg-slate-50 px-3 py-2">
							<dt class="text-xs text-slate-500">Months since last</dt>
							<dd class="mt-0.5 text-sm font-semibold text-slate-900">
								{cycleAnalysis.months_since_last_period}
							</dd>
						</div>
					{/if}
					{#if cycleAnalysis.cycle_variability != null}
						<div class="rounded-md bg-slate-50 px-3 py-2">
							<dt class="text-xs text-slate-500">Variability</dt>
							<dd class="mt-0.5 text-sm font-semibold text-slate-900">
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
/>
