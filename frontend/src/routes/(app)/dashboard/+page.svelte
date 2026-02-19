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
	let selectedRange = $state('7');
	let expandedNotes = $state<Record<string, boolean>>({});

	let dayGroups: DayGroup[] = $derived(groupByDay(logs));

	const rangeLabels: Record<string, string> = {
		'7': 'Last 7 days',
		'14': 'Last 14 days',
		'30': 'Last 30 days'
	};

	// -------------------------------------------------------------------------
	// Data fetch — reactive to selectedRange
	// -------------------------------------------------------------------------

	$effect(() => {
		fetchLogs(selectedRange);
	});

	async function fetchLogs(range: string) {
		loading = true;
		error = '';
		expandedNotes = {};

		try {
			const { data: sessionData } = await supabase.auth.getSession();
			const token = sessionData.session?.access_token;

			if (!token) {
				error = 'Please sign in to view your history.';
				return;
			}

			const startDate = new Date();
			startDate.setDate(startDate.getDate() - (parseInt(range) - 1));

			const params = new URLSearchParams({
				start_date: startDate.toLocaleDateString('en-CA'),
				limit: '100'
			});

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
						<p class="text-sm text-slate-400 italic">No details recorded</p>
					{/if}
				</li>
			{/each}
		</ol>
	{/if}
</div>
