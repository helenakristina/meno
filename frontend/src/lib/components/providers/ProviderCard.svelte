<script lang="ts">
	import CallingScriptModal from './CallingScriptModal.svelte';

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

	interface ShortlistEntry {
		id: string;
		user_id: string;
		provider_id: string;
		status: string;
		notes: string | null;
		added_at: string;
		updated_at: string;
	}

	let {
		provider,
		isSaved = false,
		shortlistEntry = null,
		onSave,
		onUnsave,
		onShortlistChange
	}: {
		provider: Provider;
		isSaved?: boolean;
		shortlistEntry?: ShortlistEntry | null;
		onSave?: () => void;
		onUnsave?: () => void;
		onShortlistChange?: () => void;
	} = $props();

	let modalOpen = $state(false);
	let saveLoading = $state(false);

	const MAX_INSURANCE = 3;

	let visibleInsurance = $derived(provider.insurance_accepted.slice(0, MAX_INSURANCE));
	let extraInsurance = $derived(
		provider.insurance_accepted.length > MAX_INSURANCE
			? provider.insurance_accepted.length - MAX_INSURANCE
			: 0
	);

	const TYPE_LABELS: Record<string, string> = {
		ob_gyn: 'OB/GYN',
		internal_medicine: 'Internal Medicine',
		np_pa: 'NP/PA',
		integrative_medicine: 'Integrative Medicine',
		other: 'Other'
	};

	function formatType(type: string | null): string {
		if (!type) return '';
		return TYPE_LABELS[type] ?? type;
	}

	function formatVerified(dateStr: string | null): string {
		if (!dateStr) return '';
		return new Date(`${dateStr}T12:00:00`).toLocaleDateString('en-US', {
			month: 'long',
			year: 'numeric'
		});
	}

	async function handleBookmarkClick() {
		if (saveLoading) return;
		saveLoading = true;
		try {
			if (isSaved) {
				await onUnsave?.();
			} else {
				await onSave?.();
			}
		} finally {
			saveLoading = false;
		}
	}
</script>

<article
	class="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm transition-shadow hover:shadow-md"
>
	<!-- Top row: name/location + badges -->
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="min-w-0">
			<h3 class="text-base font-semibold text-slate-900">
				{provider.name}{provider.credentials ? `, ${provider.credentials}` : ''}
			</h3>
			{#if provider.practice_name}
				<p class="mt-0.5 text-sm text-slate-500">{provider.practice_name}</p>
			{/if}
			<p class="mt-1 text-sm text-slate-600">{provider.city}, {provider.state}</p>
		</div>

		<!-- Right side: NAMS badge + bookmark -->
		<div class="flex shrink-0 items-center gap-2">
			{#if provider.nams_certified}
				<span
					class="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-700"
					title="NAMS Certified Menopause Practitioner"
				>
					✦ NAMS Certified
				</span>
			{/if}

			<!-- Bookmark button (only shown when save callbacks are provided) -->
			{#if onSave || onUnsave}
				<button
					onclick={handleBookmarkClick}
					disabled={saveLoading}
					aria-label={isSaved ? 'Remove from shortlist' : 'Save to shortlist'}
					title={isSaved ? 'Remove from shortlist' : 'Save to shortlist'}
					class="flex h-8 w-8 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300 disabled:cursor-not-allowed
						{isSaved
						? 'text-amber-500 hover:bg-amber-50 hover:text-amber-600'
						: 'text-slate-300 hover:bg-slate-50 hover:text-slate-500'}"
				>
					{#if saveLoading}
						<!-- Spinner -->
						<div
							class="size-4 animate-spin rounded-full border-2 border-slate-200 border-t-slate-500"
						></div>
					{:else if isSaved}
						<!-- Filled bookmark -->
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="size-5"
							viewBox="0 0 24 24"
							fill="currentColor"
						>
							<path d="M5 4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v18l-7-4-7 4V4z" />
						</svg>
					{:else}
						<!-- Outline bookmark -->
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="size-5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="1.75"
						>
							<path d="M19 21l-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
						</svg>
					{/if}
				</button>
			{/if}
		</div>
	</div>

	<!-- Provider type -->
	{#if provider.provider_type}
		<div class="mt-3">
			<span
				class="inline-flex items-center rounded-full border border-teal-100 bg-teal-50 px-2.5 py-0.5 text-xs font-medium text-teal-700"
			>
				{formatType(provider.provider_type)}
			</span>
		</div>
	{/if}

	<!-- Insurance tags -->
	{#if provider.insurance_accepted.length > 0}
		<div class="mt-3 flex flex-wrap items-center gap-1.5">
			<span class="text-xs text-slate-400">Insurance:</span>
			{#each visibleInsurance as ins (ins)}
				<span
					class="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-600"
				>
					<!-- Insurance names are normalized upstream in backend/app/core/insurance_normalizer.py -->
					{ins}
				</span>
			{/each}
			{#if extraInsurance > 0}
				<span class="text-xs text-slate-400">+{extraInsurance} more</span>
			{/if}
		</div>
	{/if}

	<!-- Contact + action row -->
	<div class="mt-4 flex flex-wrap items-center justify-between gap-3">
		<div class="flex flex-wrap items-center gap-4">
			{#if provider.phone}
				<a
					href="tel:{provider.phone}"
					class="flex items-center gap-1.5 text-sm text-teal-600 transition-colors hover:text-teal-800"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-4 shrink-0"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="1.75"
					>
						<path
							d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.6a16 16 0 0 0 6.29 6.29l.96-.96a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"
						/>
					</svg>
					{provider.phone}
				</a>
			{/if}
			{#if provider.website}
				<a
					href={provider.website}
					target="_blank"
					rel="noopener noreferrer"
					class="flex items-center gap-1 text-sm text-teal-600 transition-colors hover:text-teal-800"
				>
					Website
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-3.5"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
						<polyline points="15 3 21 3 21 9" />
						<line x1="10" y1="14" x2="21" y2="3" />
					</svg>
				</a>
			{/if}
		</div>

		<button
			onclick={() => (modalOpen = true)}
			class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
		>
			Generate Calling Script
		</button>
	</div>

	<!-- Last verified -->
	{#if provider.last_verified}
		<p class="mt-3 text-xs text-slate-400">Verified {formatVerified(provider.last_verified)}</p>
	{/if}
</article>

<CallingScriptModal
	bind:open={modalOpen}
	{provider}
	{isSaved}
	{shortlistEntry}
	{onSave}
	{onShortlistChange}
/>
