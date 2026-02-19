<script lang="ts">
	import { slide } from 'svelte/transition';
	import { supabase } from '$lib/supabase/client';

	const API_BASE = 'http://localhost:8000';

	// -------------------------------------------------------------------------
	// Types
	// -------------------------------------------------------------------------

	interface SymptomDetail {
		id: string;
		name: string;
		category: string;
	}

	interface Log {
		id: string;
		user_id: string;
		logged_at: string;
		symptoms: SymptomDetail[];
		free_text_entry: string | null;
		source: string;
	}

	interface SymptomFrequency {
		symptom_id: string;
		symptom_name: string;
		category: string;
		count: number;
	}

	interface SymptomPair {
		symptom1_id: string;
		symptom1_name: string;
		symptom2_id: string;
		symptom2_name: string;
		cooccurrence_count: number;
		cooccurrence_rate: number;
		total_occurrences_symptom1: number;
	}

	interface FreeTextEntry {
		text: string;
		time: string;
		logId: string;
	}

	interface DayGroup {
		date: string; // YYYY-MM-DD
		label: string; // "Today", "Yesterday", "March 15"
		logCount: number;
		symptoms: SymptomDetail[]; // unique across all logs for this day
		freeTextEntries: FreeTextEntry[];
	}

	// -------------------------------------------------------------------------
	// Helpers
	// -------------------------------------------------------------------------

	// Returns YYYY-MM-DD in local time — reliable cross-browser via en-CA locale.
	function toLocalDateKey(isoString: string): string {
		return new Date(isoString).toLocaleDateString('en-CA');
	}

	function formatTime(isoString: string): string {
		return new Date(isoString).toLocaleTimeString('en-US', {
			hour: 'numeric',
			minute: '2-digit'
		});
	}

	function dayLabel(dateKey: string): string {
		const todayKey = new Date().toLocaleDateString('en-CA');
		const yesterdayKey = new Date(Date.now() - 86_400_000).toLocaleDateString('en-CA');

		if (dateKey === todayKey) return 'Today';
		if (dateKey === yesterdayKey) return 'Yesterday';

		// Parse at noon local time to avoid DST edge cases
		const d = new Date(`${dateKey}T12:00:00`);
		const opts: Intl.DateTimeFormatOptions =
			d.getFullYear() === new Date().getFullYear()
				? { month: 'long', day: 'numeric' }
				: { month: 'long', day: 'numeric', year: 'numeric' };

		return d.toLocaleDateString('en-US', opts);
	}

	function groupByDay(rawLogs: Log[]): DayGroup[] {
		const map = new Map<string, Log[]>();

		for (const log of rawLogs) {
			const key = toLocalDateKey(log.logged_at);
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(log);
		}

		const groups: DayGroup[] = [];

		for (const [date, dayLogs] of map) {
			// Deduplicate symptoms by ID across all logs for this day
			const seenIds = new Set<string>();
			const symptoms: SymptomDetail[] = [];
			for (const log of dayLogs) {
				for (const s of log.symptoms) {
					if (!seenIds.has(s.id)) {
						seenIds.add(s.id);
						symptoms.push(s);
					}
				}
			}

			const freeTextEntries: FreeTextEntry[] = dayLogs
				.filter((l) => l.free_text_entry)
				.map((l) => ({ text: l.free_text_entry!, time: formatTime(l.logged_at), logId: l.id }));

			groups.push({ date, label: dayLabel(date), logCount: dayLogs.length, symptoms, freeTextEntries });
		}

		// Sort newest-first (dates are YYYY-MM-DD so string comparison works)
		return groups.sort((a, b) => b.date.localeCompare(a.date));
	}

	// -------------------------------------------------------------------------
	// State
	// -------------------------------------------------------------------------

	let loading = $state(true);
	let error = $state('');
	let logs: Log[] = $state([]);

	let frequencyLoading = $state(true);
	let frequencyError = $state('');
	let frequencyStats: SymptomFrequency[] = $state([]);

	let cooccurrenceLoading = $state(true);
	let cooccurrenceError = $state('');
	let cooccurrenceStats: SymptomPair[] = $state([]);

	let selectedRange = $state('7');
	let expandedNotes = $state<Record<string, boolean>>({});

	let dayGroups: DayGroup[] = $derived(groupByDay(logs));
	let topSymptoms: SymptomFrequency[] = $derived(frequencyStats.slice(0, 10));
	// Avoid division by zero for the bar-width calculation
	let maxCount: number = $derived(topSymptoms[0]?.count ?? 1);
	let topPairs: SymptomPair[] = $derived(cooccurrenceStats.slice(0, 6));

	const rangeLabels: Record<string, string> = {
		'7': 'Last 7 days',
		'14': 'Last 14 days',
		'30': 'Last 30 days'
	};

	// -------------------------------------------------------------------------
	// Data fetch — reactive to selectedRange, all three calls run in parallel
	// -------------------------------------------------------------------------

	$effect(() => {
		fetchAll(selectedRange);
	});

	async function fetchAll(range: string) {
		loading = true;
		frequencyLoading = true;
		cooccurrenceLoading = true;
		error = '';
		frequencyError = '';
		cooccurrenceError = '';
		expandedNotes = {};

		const { data: sessionData } = await supabase.auth.getSession();
		const token = sessionData.session?.access_token;

		if (!token) {
			error = 'Please sign in to view your history.';
			frequencyError = 'Please sign in to view your history.';
			cooccurrenceError = 'Please sign in to view your history.';
			loading = false;
			frequencyLoading = false;
			cooccurrenceLoading = false;
			return;
		}

		const startDate = new Date();
		startDate.setDate(startDate.getDate() - (parseInt(range) - 1));
		const startDateStr = startDate.toLocaleDateString('en-CA');

		await Promise.all([
			fetchLogs(token, startDateStr),
			fetchFrequencyStats(token, startDateStr),
			fetchCooccurrenceStats(token, startDateStr)
		]);
	}

	async function fetchLogs(token: string, startDateStr: string) {
		try {
			const params = new URLSearchParams({ start_date: startDateStr, limit: '100' });
			const response = await fetch(`${API_BASE}/api/symptoms/logs?${params}`, {
				headers: { Authorization: `Bearer ${token}` }
			});

			if (!response.ok) {
				error = `Failed to load your history (${response.status}). Please try again.`;
			} else {
				const data = await response.json();
				logs = data.logs ?? [];
			}
		} catch (e) {
			error = 'Network error. Please check your connection and try again.';
			console.error('Dashboard fetch error:', e);
		} finally {
			loading = false;
		}
	}

	async function fetchFrequencyStats(token: string, startDateStr: string) {
		try {
			const params = new URLSearchParams({ start_date: startDateStr });
			const response = await fetch(`${API_BASE}/api/symptoms/stats/frequency?${params}`, {
				headers: { Authorization: `Bearer ${token}` }
			});

			if (!response.ok) {
				frequencyError = `Failed to load statistics (${response.status}). Please try again.`;
			} else {
				const data = await response.json();
				frequencyStats = data.stats ?? [];
			}
		} catch (e) {
			frequencyError = 'Network error. Please check your connection and try again.';
			console.error('Frequency stats fetch error:', e);
		} finally {
			frequencyLoading = false;
		}
	}

	async function fetchCooccurrenceStats(token: string, startDateStr: string) {
		try {
			const params = new URLSearchParams({ start_date: startDateStr, min_threshold: '2' });
			const response = await fetch(`${API_BASE}/api/symptoms/stats/cooccurrence?${params}`, {
				headers: { Authorization: `Bearer ${token}` }
			});

			if (!response.ok) {
				cooccurrenceError = `Failed to load patterns (${response.status}). Please try again.`;
			} else {
				const data = await response.json();
				cooccurrenceStats = data.pairs ?? [];
			}
		} catch (e) {
			cooccurrenceError = 'Network error. Please check your connection and try again.';
			console.error('Co-occurrence stats fetch error:', e);
		} finally {
			cooccurrenceLoading = false;
		}
	}

	function toggleNotes(date: string) {
		expandedNotes[date] = !expandedNotes[date];
	}
</script>

<div class="px-4 py-8 sm:px-0">
	<!-- Header -->
	<div class="mb-8 flex flex-wrap items-start justify-between gap-4">
		<div>
			<h1 class="text-2xl font-bold text-slate-900">Your Symptom History</h1>
			<p class="mt-1 text-slate-500">{rangeLabels[selectedRange]}, grouped by day</p>
		</div>
		<select
			bind:value={selectedRange}
			aria-label="Date range"
			class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-200"
		>
			<option value="7">Last 7 days</option>
			<option value="14">Last 14 days</option>
			<option value="30">Last 30 days</option>
		</select>
	</div>

	<!-- Frequency Chart -->
	<section
		class="mb-8 rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm"
		aria-labelledby="freq-chart-heading"
	>
		<h2 id="freq-chart-heading" class="mb-5 text-base font-semibold text-slate-800">
			Most Frequent Symptoms
		</h2>

		{#if frequencyLoading}
			<div class="flex items-center justify-center py-10">
				<div class="text-sm text-slate-400">Loading...</div>
			</div>
		{:else if frequencyError}
			<div class="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
				{frequencyError}
			</div>
		{:else if topSymptoms.length === 0}
			<p class="py-6 text-center text-sm text-slate-400">No symptoms logged in this period.</p>
		{:else}
			<ol class="space-y-3" aria-label="Symptom frequency chart">
				{#each topSymptoms as stat (stat.symptom_id)}
					<li class="flex items-center gap-3">
						<!-- Name: right-aligned, fixed width, truncated if very long -->
						<span
							class="w-36 shrink-0 truncate text-right text-sm text-slate-700"
							title={stat.symptom_name}
						>
							{stat.symptom_name}
						</span>

						<!-- Bar track -->
						<div class="relative h-5 flex-1 overflow-hidden rounded bg-teal-50">
							<div
								class="absolute inset-y-0 left-0 rounded bg-teal-500"
								style="width: {(stat.count / maxCount) * 100}%"
								aria-hidden="true"
							></div>
						</div>

						<!-- Count -->
						<span class="w-6 shrink-0 text-right text-sm font-medium tabular-nums text-slate-500">
							{stat.count}
						</span>
					</li>
				{/each}
			</ol>
		{/if}
	</section>

	<!-- Co-occurrence Section -->
	<section
		class="mb-8 rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm"
		aria-labelledby="coocc-heading"
	>
		<div class="mb-5 flex items-start justify-between gap-2">
			<div>
				<h2 id="coocc-heading" class="text-base font-semibold text-slate-800">
					Symptoms That Travel Together
				</h2>
				<p class="mt-0.5 text-sm text-slate-400">Patterns in your symptom logs</p>
			</div>
			<!-- Info tooltip -->
			<button
				title="When two symptoms appear together often, it's worth noting — it can help you spot triggers and have more informed conversations with your provider."
				aria-label="About co-occurrence patterns"
				class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-200 text-xs text-slate-400 transition-colors hover:border-teal-300 hover:text-teal-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
			>
				?
			</button>
		</div>

		{#if cooccurrenceLoading}
			<div class="flex items-center justify-center py-10">
				<div class="text-sm text-slate-400">Loading...</div>
			</div>
		{:else if cooccurrenceError}
			<div class="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
				{cooccurrenceError}
			</div>
		{:else if topPairs.length === 0}
			<p class="py-6 text-center text-sm text-slate-400">
				Not enough data yet to identify patterns. Keep logging to see connections.
			</p>
		{:else}
			<ol class="divide-y divide-slate-50" aria-label="Symptom co-occurrence patterns">
				{#each topPairs as pair (`${pair.symptom1_id}-${pair.symptom2_id}`)}
					<li class="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
						<!-- Symptom names -->
						<div class="flex min-w-0 flex-wrap items-center gap-1.5">
							<span
								class="rounded-full border border-teal-100 bg-teal-50 px-2.5 py-0.5 text-sm font-medium text-teal-700"
							>
								{pair.symptom1_name}
							</span>
							<span class="text-xs text-slate-400">and</span>
							<span
								class="rounded-full border border-teal-100 bg-teal-50 px-2.5 py-0.5 text-sm font-medium text-teal-700"
							>
								{pair.symptom2_name}
							</span>
						</div>

						<!-- Stats -->
						<div class="shrink-0 text-right">
							<span class="text-lg font-bold tabular-nums text-teal-600">
								{Math.round(pair.cooccurrence_rate * 100)}%
							</span>
							<span class="ml-1 text-xs text-slate-400">
								of the time
							</span>
							<div class="text-xs text-slate-400">
								{pair.cooccurrence_count} {pair.cooccurrence_count === 1 ? 'time' : 'times'} together
							</div>
						</div>
					</li>
				{/each}
			</ol>
		{/if}
	</section>

	<!-- Section separator -->
	<hr class="mb-8 border-slate-100" />

	<!-- Loading -->
	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="text-sm text-slate-400">Loading your history...</div>
		</div>

	<!-- Error -->
	{:else if error}
		<div class="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
			{error}
		</div>

	<!-- Empty state -->
	{:else if dayGroups.length === 0}
		<div class="rounded-2xl border border-dashed border-slate-300 bg-slate-50 py-16 text-center">
			<p class="text-slate-500">No symptoms logged in this period.</p>
			<p class="mt-1 text-sm text-slate-400">Start by logging your symptoms.</p>
			<a
				href="/log"
				class="mt-5 inline-block rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
			>
				Log today's symptoms
			</a>
		</div>

	<!-- History -->
	{:else}
		<ol class="space-y-4">
			{#each dayGroups as group (group.date)}
				{@const notesExpanded = !!expandedNotes[group.date]}
				{@const noteCount = group.freeTextEntries.length}
				<li class="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
					<!-- Day header -->
					<div class="mb-3 flex items-baseline justify-between">
						<h2 class="text-base font-semibold text-slate-800">{group.label}</h2>
						{#if group.logCount > 1}
							<span class="text-xs text-slate-400">{group.logCount} entries</span>
						{/if}
					</div>

					<!-- Symptom pills -->
					{#if group.symptoms.length > 0}
						<div class="flex flex-wrap gap-2" aria-label="Symptoms logged">
							{#each group.symptoms as symptom (symptom.id)}
								<span
									class="rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-sm font-medium text-teal-700"
								>
									{symptom.name}
								</span>
							{/each}
						</div>
					{/if}

					<!-- Collapsible free text notes -->
					{#if noteCount > 0}
						<div class="mt-3">
							<button
								onclick={() => toggleNotes(group.date)}
								aria-expanded={notesExpanded}
								class="flex cursor-pointer items-center gap-1 text-sm text-slate-400 transition-colors hover:text-slate-600 focus:outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-teal-300"
							>
								<span>📝 {noteCount} {noteCount === 1 ? 'note' : 'notes'}</span>
								<span class="mx-1 text-slate-300">·</span>
								<span class="text-teal-600 hover:underline">
									{notesExpanded ? 'Hide details' : 'Show details'}
								</span>
							</button>
							{#if notesExpanded}
								<ul
									transition:slide={{ duration: 200 }}
									class="mt-2 space-y-2 border-l-2 border-slate-100 pl-4"
									aria-label="Journal entries"
								>
									{#each group.freeTextEntries as entry (entry.logId)}
										<li class="text-sm">
											<span class="text-slate-700">"{entry.text}"</span>
											<span class="ml-2 text-xs text-slate-400">{entry.time}</span>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}

					<!-- Edge case: text-only day with no symptoms -->
					{#if group.symptoms.length === 0 && noteCount === 0}
						<p class="text-sm italic text-slate-400">No details recorded</p>
					{/if}
				</li>
			{/each}
		</ol>
	{/if}
</div>
