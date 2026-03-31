<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { apiClient } from '$lib/api/client';
	import ProviderCard from '$lib/components/providers/ProviderCard.svelte';
	import ProviderFilters from '$lib/components/providers/ProviderFilters.svelte';
	import ProviderSkeleton from '$lib/components/providers/ProviderSkeleton.svelte';
	import { ErrorBanner } from '$lib/components/shared';

	// -------------------------------------------------------------------------
	// Types
	// -------------------------------------------------------------------------

	interface Provider {
		id: string;
		name: string;
		credentials: string | null;
		practice_name: string | null;
		city: string;
		state: string;
		zip_code: string | null;
		phone: string | null;
		website: string | null;
		nams_certified: boolean;
		provider_type: string | null;
		specialties: string[];
		insurance_accepted: string[];
		data_source: string | null;
		last_verified: string | null;
	}

	interface SearchResponse {
		providers: Provider[];
		total: number;
		page: number;
		page_size: number;
		total_pages: number;
	}

	interface StateCount {
		state: string;
		count: number;
	}

	interface ShortlistEntry {
		id: string;
		user_id: string;
		provider_id: string;
		status: string;
		notes: string | null;
		added_at: string;
		updated_at: string;
		provider: Provider;
	}

	// -------------------------------------------------------------------------
	// Search form state
	// -------------------------------------------------------------------------

	let selectedState = $state('');
	let stateDropdownOpen = $state(false);
	let stateSearchInput = $state('');
	let city = $state('');
	let providerType = $state('');
	let insurance = $state('');
	let namsOnly = $state(true);
	let currentPage = $state(1);
	const PAGE_SIZE = 20;

	// -------------------------------------------------------------------------
	// UI state
	// -------------------------------------------------------------------------

	let states = $state<StateCount[]>([]);
	let results = $state<SearchResponse | null>(null);
	let loading = $state(false);
	let error = $state('');
	let hasSearched = $state(false);
	let filtersOpen = $state(false);

	// -------------------------------------------------------------------------
	// Shortlist state
	// -------------------------------------------------------------------------

	let shortlist = $state<ShortlistEntry[]>([]);
	let savedProviderIds = $state(new Set<string>());
	let shortlistExpanded = $state(false);
	let expandedEntries = $state(new Set<string>());
	let notesDraft = $state<Record<string, string>>({});
	let notesSaving = $state<Record<string, boolean>>({});
	let notesSaved = $state<Record<string, boolean>>({});

	// Status config for badges and dropdown
	const STATUS_CONFIG: Record<string, { label: string; badge: string }> = {
		to_call: { label: 'To Call', badge: 'bg-coral-100 text-coral-800' },
		called: { label: 'Called', badge: 'bg-primary-100 text-primary-700' },
		left_voicemail: { label: 'Left Voicemail', badge: 'bg-neutral-100 text-neutral-700' },
		booking: { label: 'Booked Appointment', badge: 'bg-primary-100 text-primary-800' },
		not_available: { label: 'Not Available', badge: 'bg-neutral-100 text-neutral-500' }
	};

	const STATUSES = Object.entries(STATUS_CONFIG).map(([value, cfg]) => ({
		value,
		label: cfg.label
	}));

	// -------------------------------------------------------------------------
	// Derived
	// -------------------------------------------------------------------------

	let canSearch = $derived(selectedState !== '');

	let showingFrom = $derived(results && results.total > 0 ? (currentPage - 1) * PAGE_SIZE + 1 : 0);
	let showingTo = $derived(results ? Math.min(currentPage * PAGE_SIZE, results.total) : 0);

	let paginationPages = $derived(
		results ? buildPaginationPages(currentPage, results.total_pages) : []
	);

	let selectedStateName = $derived(selectedState || 'the selected state');

	// Filter states by search input
	let filteredStates = $derived(
		stateSearchInput.trim() === ''
			? states
			: states.filter(
					(s) =>
						s.state.toLowerCase().includes(stateSearchInput.toLowerCase()) ||
						s.state === stateSearchInput.toUpperCase()
				)
	);

	// Shortlist entries shown in the section — collapse to 3 unless expanded
	let visibleShortlist = $derived(
		shortlist.length > 3 && !shortlistExpanded ? shortlist.slice(0, 3) : shortlist
	);

	// -------------------------------------------------------------------------
	// Helpers
	// -------------------------------------------------------------------------

	function buildPaginationPages(current: number, total: number): (number | '…')[] {
		if (total <= 1) return [];
		if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);

		if (current <= 4) {
			return [1, 2, 3, 4, 5, '…', total];
		}
		if (current >= total - 3) {
			return [1, '…', total - 4, total - 3, total - 2, total - 1, total];
		}
		return [1, '…', current - 1, current, current + 1, '…', total];
	}

	function getShortlistEntry(providerId: string): ShortlistEntry | null {
		return shortlist.find((e) => e.provider_id === providerId) ?? null;
	}

	// -------------------------------------------------------------------------
	// Shortlist data fetching + mutations
	// -------------------------------------------------------------------------

	async function loadShortlist() {
		try {
			const data = await apiClient.get<ShortlistEntry[]>('/api/providers/shortlist');
			shortlist = data ?? [];
			savedProviderIds = new Set(shortlist.map((e) => e.provider_id));
		} catch {
			// Fail silently — shortlist is a UX enhancement, not critical path.
			// This also handles the unauthenticated case gracefully.
		}
	}

	async function handleSave(providerId: string) {
		// Optimistic update
		savedProviderIds = new Set([...savedProviderIds, providerId]);
		try {
			await apiClient.post('/api/providers/shortlist', { provider_id: providerId });
			// Reload to get the full entry (including provider data) for the shortlist section
			await loadShortlist();
		} catch (e) {
			// 409 means already saved — state is correct, keep optimistic
			const msg = e instanceof Error ? e.message : '';
			if (!msg.includes('409')) {
				const updated = new Set(savedProviderIds);
				updated.delete(providerId);
				savedProviderIds = updated;
			}
		}
	}

	async function handleUnsave(providerId: string) {
		// Optimistic update
		const updated = new Set(savedProviderIds);
		updated.delete(providerId);
		savedProviderIds = updated;
		shortlist = shortlist.filter((e) => e.provider_id !== providerId);

		try {
			await apiClient.delete(`/api/providers/shortlist/${providerId}`);
		} catch {
			// Revert on failure
			await loadShortlist();
		}
	}

	async function handleUpdateStatus(providerId: string, newStatus: string) {
		// Optimistic update
		shortlist = shortlist.map((e) =>
			e.provider_id === providerId ? { ...e, status: newStatus } : e
		);
		try {
			await apiClient.patch(`/api/providers/shortlist/${providerId}`, { status: newStatus });
		} catch {
			await loadShortlist();
		}
	}

	async function handleRemoveFromShortlist(providerId: string) {
		await handleUnsave(providerId);
	}

	async function handleNotesSave(providerId: string) {
		const notes = notesDraft[providerId] ?? '';
		notesSaving[providerId] = true;
		try {
			await apiClient.patch(`/api/providers/shortlist/${providerId}`, { notes });
			shortlist = shortlist.map((e) =>
				e.provider_id === providerId ? { ...e, notes: notes.trim() || null } : e
			);
			notesSaved[providerId] = true;
			setTimeout(() => {
				notesSaved[providerId] = false;
			}, 2000);
		} catch {
			// Fail silently — notes are non-critical
		} finally {
			notesSaving[providerId] = false;
		}
	}

	// -------------------------------------------------------------------------
	// Data fetching — search
	// -------------------------------------------------------------------------

	async function loadStates() {
		try {
			const data = await apiClient.get<StateCount[]>('/api/providers/states');
			states = data ?? [];
		} catch (e) {
			console.error('Failed to load states:', e);
		}
	}

	async function search() {
		if (!canSearch) return;

		loading = true;
		error = '';

		try {
			const params: Record<string, string | number | boolean> = {
				state: selectedState,
				nams_only: namsOnly,
				page: currentPage,
				page_size: PAGE_SIZE
			};
			if (city.trim()) params.city = city.trim();
			if (providerType) params.provider_type = providerType;
			if (insurance) params.insurance = insurance;

			results = await apiClient.get<SearchResponse>('/api/providers/search', params);
			hasSearched = true;
			syncUrl();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to search providers. Please try again.';
			console.error('Provider search error:', e);
		} finally {
			loading = false;
		}
	}

	// -------------------------------------------------------------------------
	// URL sync
	// -------------------------------------------------------------------------

	function syncUrl() {
		const params = new URLSearchParams();
		if (selectedState) params.set('state', selectedState);
		if (city.trim()) params.set('city', city.trim());
		if (providerType) params.set('provider_type', providerType);
		if (insurance) params.set('insurance', insurance);
		if (!namsOnly) params.set('nams_only', 'false');
		if (currentPage > 1) params.set('page', String(currentPage));

		goto(`?${params.toString()}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function readUrlParams() {
		const sp = page.url.searchParams;
		const stateParam = sp.get('state');
		if (stateParam) selectedState = stateParam;
		if (sp.get('city')) city = sp.get('city')!;
		if (sp.get('provider_type')) providerType = sp.get('provider_type')!;
		if (sp.get('insurance')) insurance = sp.get('insurance')!;
		if (sp.get('nams_only') === 'false') namsOnly = false;
		const pageParam = sp.get('page');
		if (pageParam) currentPage = parseInt(pageParam) || 1;

		// Auto-execute if state is in URL
		if (stateParam) search();
	}

	// -------------------------------------------------------------------------
	// Event handlers
	// -------------------------------------------------------------------------

	function handleSearch() {
		currentPage = 1;
		search();
	}

	function handleFilterChange() {
		if (!hasSearched) return;
		currentPage = 1;
		search();
	}

	function goToPage(p: number) {
		currentPage = p;
		search();
		document.getElementById('results-section')?.scrollIntoView({ behavior: 'smooth' });
	}

	function handleSearchKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && canSearch) handleSearch();
	}

	function selectState(value: string) {
		selectedState = value;
		stateDropdownOpen = false;
	}

	function handleStateDropdownKeydown(e: KeyboardEvent) {
		const stateElements = states.map((s) => s.state);
		const currentIndex = stateElements.indexOf(selectedState);

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (!stateDropdownOpen) {
				stateDropdownOpen = true;
			} else {
				const nextIndex = currentIndex + 1;
				if (nextIndex < stateElements.length) {
					selectState(stateElements[nextIndex]);
				}
			}
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			if (stateDropdownOpen && currentIndex > 0) {
				selectState(stateElements[currentIndex - 1]);
			}
		} else if (e.key === 'Escape') {
			e.preventDefault();
			stateDropdownOpen = false;
		}
	}

	let selectedStateCount = $derived(states.find((s) => s.state === selectedState)?.count ?? null);

	// -------------------------------------------------------------------------
	// Mount
	// -------------------------------------------------------------------------

	onMount(async () => {
		// Load shortlist in the background — don't await it so search isn't blocked
		// if the shortlist endpoint is slow or fails.
		loadShortlist();
		await loadStates();
		readUrlParams();
	});
</script>

<div class="w-full max-w-full overflow-hidden px-4 py-8 sm:px-6 lg:px-8">
	<!-- Page header -->
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-neutral-800">Find a Menopause Specialist</h1>
		<p class="mt-1 text-neutral-500">
			Search our directory of NAMS-certified menopause practitioners near you.
		</p>
	</div>

	<!-- ── MY SHORTLIST ──────────────────────────────────────────────────── -->
	{#if shortlist.length > 0}
		<section class="mb-6 rounded-2xl border border-neutral-200 bg-white shadow-sm">
			<!-- Section header -->
			<div class="flex items-center justify-between px-6 py-4">
				<h2 class="text-sm font-semibold text-neutral-700">
					My Shortlist
					<span class="ml-1 font-normal text-neutral-400">({shortlist.length})</span>
				</h2>
				{#if shortlist.length > 3}
					<button
						onclick={() => (shortlistExpanded = !shortlistExpanded)}
						class="text-xs font-medium text-primary-600 transition-colors hover:text-primary-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
						aria-expanded={shortlistExpanded}
						aria-controls="shortlist-entries"
					>
						{shortlistExpanded ? 'Collapse' : `Show all ${shortlist.length}`}
					</button>
				{/if}
			</div>

			<!-- Entry list -->
			<ul id="shortlist-entries" class="divide-y divide-neutral-100 border-t border-neutral-100">
				{#each visibleShortlist as entry (entry.provider_id)}
					{@const statusCfg = STATUS_CONFIG[entry.status] ?? STATUS_CONFIG.to_call}
					{@const isExpanded = expandedEntries.has(entry.provider_id)}
					{@const TYPE_LABELS = {
						ob_gyn: 'OB/GYN',
						internal_medicine: 'Internal Medicine',
						np_pa: 'NP/PA',
						integrative_medicine: 'Integrative Medicine',
						other: 'Other'
					}}
					{@const MAX_INSURANCE = 2}
					{@const visibleIns = entry.provider.insurance_accepted.slice(0, MAX_INSURANCE)}
					{@const extraIns =
						entry.provider.insurance_accepted.length > MAX_INSURANCE
							? entry.provider.insurance_accepted.length - MAX_INSURANCE
							: 0}
					<li class="border-b-0">
						<!-- Compact row (always visible) -->
						<div class="flex items-center justify-between gap-2 px-6 py-3">
							<!-- Name, phone, status in a row -->
							<div class="min-w-0 flex-1">
								<div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-4">
									<h4 class="truncate text-sm font-semibold text-neutral-800">
										{entry.provider.name}
									</h4>
									{#if entry.provider.phone}
										<a
											href="tel:{entry.provider.phone}"
											class="text-xs font-medium whitespace-nowrap text-primary-600 hover:text-primary-800"
										>
											{entry.provider.phone}
										</a>
									{/if}
									<span
										class="inline-flex w-fit items-center rounded-full px-2 py-0.5 text-xs font-medium {statusCfg.badge}"
									>
										{statusCfg.label}
									</span>
								</div>
							</div>

							<!-- Expand/collapse button and remove button -->
							<div class="flex shrink-0 items-center gap-1">
								<button
									onclick={() => {
										const updated = new Set(expandedEntries);
										if (updated.has(entry.provider_id)) {
											updated.delete(entry.provider_id);
										} else {
											updated.add(entry.provider_id);
										}
										expandedEntries = updated;
									}}
									aria-label={isExpanded ? 'Collapse details' : 'Expand details'}
									class="flex h-9 w-9 items-center justify-center rounded text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="size-4 transition-transform {isExpanded ? 'rotate-180' : ''}"
										viewBox="0 0 24 24"
										fill="none"
										stroke="currentColor"
										stroke-width="2"
									>
										<path d="m6 9 6 6 6-6" />
									</svg>
								</button>
								<button
									onclick={() => handleRemoveFromShortlist(entry.provider_id)}
									aria-label="Remove from shortlist"
									class="flex h-9 w-9 items-center justify-center rounded text-neutral-300 transition-colors hover:bg-neutral-100 hover:text-neutral-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
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

						<!-- Expandable details -->
						{#if isExpanded}
							<div class="space-y-3 border-t border-neutral-100 bg-neutral-50 px-6 py-4">
								<!-- Provider info -->
								<div>
									<p class="mb-1 text-xs font-medium text-neutral-500">Provider Details</p>
									{#if entry.provider.practice_name}
										<p class="text-xs text-neutral-600">{entry.provider.practice_name}</p>
									{/if}
									<p class="text-xs text-neutral-600">
										{entry.provider.city}, {entry.provider.state}
									</p>
								</div>

								<!-- Type, NAMS, Website -->
								{#if entry.provider.provider_type || entry.provider.nams_certified || entry.provider.website}
									<div class="flex flex-wrap items-center gap-2">
										{#if entry.provider.provider_type}
											<span
												class="inline-flex rounded-full border border-primary-100 bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
											>
												{TYPE_LABELS[entry.provider.provider_type] ?? entry.provider.provider_type}
											</span>
										{/if}
										{#if entry.provider.nams_certified}
											<span
												class="inline-flex rounded-full border border-primary-200 bg-primary-50 px-2 py-0.5 text-xs font-semibold text-primary-700"
												title="NAMS Certified Menopause Practitioner"
											>
												✦ NAMS
											</span>
										{/if}
										{#if entry.provider.website}
											<a
												href={entry.provider.website}
												target="_blank"
												rel="noopener noreferrer"
												class="text-xs font-medium text-primary-600 hover:text-primary-800"
											>
												Website ↗
											</a>
										{/if}
									</div>
								{/if}

								<!-- Insurance -->
								{#if entry.provider.insurance_accepted.length > 0}
									<div>
										<p class="mb-1 text-xs font-medium text-neutral-500">Insurance</p>
										<div class="flex flex-wrap gap-1">
											{#each visibleIns as ins (ins)}
												<span
													class="rounded border border-neutral-200 bg-white px-1.5 py-0.5 text-xs text-neutral-600"
												>
													{ins}
												</span>
											{/each}
											{#if extraIns > 0}
												<span class="text-xs text-neutral-400">+{extraIns}</span>
											{/if}
										</div>
									</div>
								{/if}

								<!-- Actions -->
								<div class="flex gap-2 pt-1">
									<button
										onclick={() => {
											const card = document.querySelector(
												`[data-provider-id="${entry.provider_id}"]`
											) as HTMLElement;
											if (card) {
												const btn = card.querySelector(
													'[data-action="generate-script"]'
												) as HTMLButtonElement;
												btn?.click();
											}
										}}
										class="rounded border border-neutral-200 bg-white px-2.5 py-1.5 text-xs font-medium text-neutral-700 transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700"
									>
										Generate Script
									</button>
									<select
										value={entry.status}
										onchange={(e) =>
											handleUpdateStatus(entry.provider_id, (e.target as HTMLSelectElement).value)}
										class="rounded border border-neutral-200 bg-white px-2 py-1 text-xs text-neutral-600 focus:border-primary-400 focus:ring-1 focus:ring-primary-200 focus:outline-none"
										aria-label="Update call status"
									>
										{#each STATUSES as s (s.value)}
											<option value={s.value}>{s.label}</option>
										{/each}
									</select>
								</div>

								<!-- Notes -->
								<div class="relative">
									<textarea
										rows="2"
										placeholder="Add notes…"
										value={notesDraft[entry.provider_id] ?? entry.notes ?? ''}
										oninput={(e) => {
											notesDraft[entry.provider_id] = (e.target as HTMLTextAreaElement).value;
										}}
										onblur={() => handleNotesSave(entry.provider_id)}
										disabled={notesSaving[entry.provider_id]}
										class="w-full resize-none rounded border border-neutral-200 bg-white px-2.5 py-2 text-xs text-neutral-700 placeholder-neutral-400 focus:border-primary-400 focus:ring-1 focus:ring-primary-200 focus:outline-none disabled:opacity-60"
									></textarea>
									{#if notesSaved[entry.provider_id]}
										<span class="absolute right-2 bottom-2 text-xs text-primary-500">Saved</span>
									{/if}
								</div>
							</div>
						{/if}
					</li>
				{/each}
			</ul>

			<!-- "Show more" footer when collapsed and there are hidden entries -->
			{#if shortlist.length > 3 && !shortlistExpanded}
				<div class="border-t border-neutral-100 px-6 py-3 text-center">
					<button
						onclick={() => (shortlistExpanded = true)}
						class="text-xs text-neutral-400 transition-colors hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
					>
						+{shortlist.length - 3} more — show all
					</button>
				</div>
			{/if}
		</section>
	{/if}

	<!-- Search bar -->
	<section class="mb-4 rounded-2xl border border-neutral-200 bg-white px-6 py-5 shadow-sm">
		<div class="flex flex-wrap items-end gap-3">
			<!-- State custom dropdown -->
			<div class="relative min-w-[160px] flex-1">
				<p class="mb-1.5 text-sm font-medium text-neutral-500">
					State <span class="text-danger">*</span>
				</p>
				<!-- Backdrop to close on outside click -->
				{#if stateDropdownOpen}
					<div
						class="fixed inset-0 z-10"
						onclick={() => {
							stateDropdownOpen = false;
							stateSearchInput = '';
						}}
						role="presentation"
					></div>
				{/if}
				<button
					type="button"
					id="state-dropdown-button"
					onclick={() => {
						stateDropdownOpen = !stateDropdownOpen;
						if (stateDropdownOpen) {
							stateSearchInput = '';
						}
					}}
					onkeydown={handleStateDropdownKeydown}
					class="flex w-full items-center justify-between rounded-lg border bg-white px-3 py-3 text-sm shadow-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300
						{stateDropdownOpen
						? 'border-primary-400 ring-2 ring-primary-200'
						: 'border-neutral-200 hover:border-neutral-300'}
						{selectedState ? 'text-neutral-700' : 'text-neutral-400'}"
					aria-haspopup="listbox"
					aria-expanded={stateDropdownOpen}
					aria-controls="state-dropdown-list"
				>
					<span>
						{selectedState
							? `${selectedState}${selectedStateCount !== null ? ` (${selectedStateCount})` : ''}`
							: 'Select a state…'}
					</span>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-4 shrink-0 text-neutral-400 transition-transform {stateDropdownOpen
							? 'rotate-180'
							: ''}"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="m6 9 6 6 6-6" />
					</svg>
				</button>

				{#if stateDropdownOpen}
					<div
						id="state-dropdown-list"
						class="absolute top-full left-0 z-20 mt-1 w-full rounded-lg border border-neutral-200 bg-white shadow-lg"
						role="listbox"
						aria-label="State"
					>
						<div class="border-b border-neutral-100 p-2">
							<input
								type="text"
								placeholder="Type state name or code..."
								bind:value={stateSearchInput}
								class="w-full rounded border border-neutral-200 px-2 py-1.5 text-sm focus:border-primary-400 focus:ring-2 focus:ring-primary-200 focus:outline-none"
								aria-label="Search states"
							/>
						</div>
						<ul class="overflow-y-auto py-1" style="max-height: calc(100vh - 250px)">
							{#if filteredStates.length > 0}
								{#each filteredStates as s (s.state)}
									<li role="option" aria-selected={selectedState === s.state}>
										<button
											type="button"
											onclick={() => {
												selectState(s.state);
												stateDropdownOpen = false;
												stateSearchInput = '';
											}}
											class="flex w-full items-center justify-between px-3 py-3 text-left text-sm transition-colors
										{selectedState === s.state
												? 'bg-primary-50 font-medium text-primary-700'
												: 'text-neutral-700 hover:bg-primary-50 hover:text-primary-700'}"
										>
											<span>{s.state}</span>
											<span class="text-xs text-neutral-400">{s.count}</span>
										</button>
									</li>
								{/each}
							{:else}
								<li class="px-3 py-4 text-center text-sm text-neutral-400">No states found</li>
							{/if}
						</ul>
					</div>
				{/if}
			</div>

			<!-- City input -->
			<div class="min-w-[180px] flex-1">
				<label for="city-input" class="mb-1.5 block text-sm font-medium text-neutral-500">
					City <span class="text-neutral-300">(optional)</span>
				</label>
				<input
					id="city-input"
					type="text"
					placeholder="e.g. Minneapolis"
					bind:value={city}
					onkeydown={handleSearchKeydown}
					class="h-11 w-full rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-700 shadow-sm transition-colors focus:border-primary-400 focus:ring-2 focus:ring-primary-200 focus:outline-none"
				/>
			</div>

			<!-- Search button -->
			<button
				onclick={handleSearch}
				disabled={!canSearch || loading}
				class="min-h-11 rounded-lg bg-primary-500 px-5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 disabled:cursor-not-allowed disabled:opacity-50"
			>
				{loading && !hasSearched ? 'Searching…' : 'Search'}
			</button>
		</div>
	</section>

	<!-- Filters section -->
	{#if hasSearched}
		<section class="mb-4 rounded-2xl border border-neutral-200 bg-white px-6 py-5 shadow-sm">
			<!-- Mobile toggle -->
			<button
				onclick={() => (filtersOpen = !filtersOpen)}
				class="flex w-full items-center justify-between text-sm font-medium text-neutral-700 focus:outline-none sm:hidden"
				aria-expanded={filtersOpen}
				aria-controls="filters-panel"
			>
				<span>Filters</span>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="size-4 transition-transform {filtersOpen ? 'rotate-180' : ''}"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
				>
					<path d="m6 9 6 6 6-6" />
				</svg>
			</button>

			<!-- Filter content: always visible on sm+, toggled on mobile -->
			<div id="filters-panel" class="{filtersOpen ? 'mt-4 block' : 'hidden'} sm:block">
				<ProviderFilters
					bind:providerType
					bind:insurance
					bind:namsOnly
					onchange={handleFilterChange}
				/>
			</div>
		</section>
	{/if}

	<!-- Results -->
	<section id="results-section">
		{#if loading}
			<!-- Skeleton loading -->
			<div class="mb-4 h-5 w-48 animate-pulse rounded bg-neutral-200"></div>
			<ProviderSkeleton />
		{:else if error}
			<!-- Error state -->
			<ErrorBanner message={error} onRetry={handleSearch} />
		{:else if !hasSearched}
			<!-- Pre-search state -->
			<div
				class="rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 py-20 text-center"
			>
				<div
					class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary-100 text-2xl"
				>
					🔍
				</div>
				<p class="font-medium text-neutral-700">Find specialists near you</p>
				<p class="mt-1 text-sm text-neutral-400">
					Select a state above to search our directory of menopause-knowledgeable providers.
				</p>
			</div>
		{:else if results && results.total === 0}
			<!-- Empty state -->
			<div
				class="rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 py-16 text-center"
			>
				<div
					class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-neutral-200 text-2xl"
				>
					🌿
				</div>
				<p class="font-medium text-neutral-700">
					No specialists found in {city ? `${city}, ` : ''}{selectedStateName}
				</p>
				<p class="mt-1 text-sm text-neutral-400">
					Try searching just by state, or expanding your filters.
				</p>
				<button
					onclick={() => {
						city = '';
						providerType = '';
						insurance = '';
						namsOnly = true;
						handleSearch();
					}}
					class="mt-4 rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300"
				>
					Clear filters
				</button>
			</div>
		{:else if results}
			<!-- Results header -->
			<div class="mb-4 flex items-center justify-between gap-4">
				<p class="text-sm text-neutral-500">
					Showing <span class="font-medium text-neutral-700">{showingFrom}–{showingTo}</span>
					of
					<span class="font-medium text-neutral-700">{results.total}</span>
					providers in
					<span class="font-medium text-neutral-700">{selectedStateName}</span>
					{#if loading}
						<span class="ml-1 text-neutral-400">·&nbsp;Refreshing…</span>
					{/if}
				</p>
			</div>

			<!-- Provider cards -->
			<ol class="space-y-4" aria-label="Provider search results">
				{#each results.providers as provider (provider.id)}
					<li>
						<ProviderCard
							{provider}
							isSaved={savedProviderIds.has(provider.id)}
							shortlistEntry={getShortlistEntry(provider.id)}
							onSave={() => handleSave(provider.id)}
							onUnsave={() => handleUnsave(provider.id)}
							onShortlistChange={loadShortlist}
						/>
					</li>
				{/each}
			</ol>

			<!-- Pagination -->
			{#if paginationPages.length > 0}
				<nav
					class="mt-8 flex flex-wrap items-center justify-center gap-1.5"
					aria-label="Pagination"
				>
					<!-- Prev -->
					<button
						onclick={() => goToPage(currentPage - 1)}
						disabled={currentPage <= 1}
						class="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-600 transition-colors hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 disabled:cursor-not-allowed disabled:opacity-40"
						aria-label="Previous page"
					>
						← Prev
					</button>

					{#each paginationPages as p (String(p) + '-' + paginationPages.indexOf(p))}
						{#if p === '…'}
							<span class="px-1 text-sm text-neutral-400">…</span>
						{:else}
							<button
								onclick={() => goToPage(p as number)}
								aria-current={currentPage === p ? 'page' : undefined}
								class="min-w-[36px] rounded-lg border px-3 py-1.5 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300
									{currentPage === p
									? 'border-primary-500 bg-primary-500 font-medium text-white'
									: 'border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50'}"
							>
								{p}
							</button>
						{/if}
					{/each}

					<!-- Next -->
					<button
						onclick={() => goToPage(currentPage + 1)}
						disabled={currentPage >= (results?.total_pages ?? 1)}
						class="rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-sm text-neutral-600 transition-colors hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-300 disabled:cursor-not-allowed disabled:opacity-40"
						aria-label="Next page"
					>
						Next →
					</button>
				</nav>
			{/if}

			<!-- Disclaimer -->
			<p class="mt-8 text-center text-xs text-neutral-400">
				Provider availability and new patient status change frequently. We recommend calling ahead
				to confirm they are accepting new patients.
			</p>
		{/if}
	</section>
</div>
