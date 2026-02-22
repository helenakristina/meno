<script lang="ts">
	import { apiClient } from '$lib/api/client';

	let {
		providerType = $bindable(''),
		insurance = $bindable(''),
		namsOnly = $bindable(true),
		onchange
	}: {
		providerType: string;
		insurance: string;
		namsOnly: boolean;
		onchange?: () => void;
	} = $props();

	const PROVIDER_TYPES = [
		{ value: '', label: 'All' },
		{ value: 'ob_gyn', label: 'OB/GYN' },
		{ value: 'internal_medicine', label: 'Internal Medicine' },
		{ value: 'np_pa', label: 'NP/PA' },
		{ value: 'integrative_medicine', label: 'Integrative' },
		{ value: 'other', label: 'Other' }
	];

	let insuranceOptions = $state<string[]>([]);
	let insuranceLoaded = $state(false);
	let insuranceLoading = $state(false);
	// Local display value — tracks what's typed; insurance (bindable) is the committed filter
	let insuranceSearch = $state(insurance);
	let insuranceOpen = $state(false);

	let filteredInsurance = $derived(
		insuranceSearch.trim()
			? insuranceOptions.filter((opt) =>
					opt.toLowerCase().includes(insuranceSearch.trim().toLowerCase())
				)
			: insuranceOptions
	);

	// Sync insuranceSearch when insurance is programmatically cleared (e.g. from parent)
	$effect(() => {
		if (!insurance) insuranceSearch = '';
	});

	async function loadInsuranceOptions() {
		if (insuranceLoaded || insuranceLoading) return;
		insuranceLoading = true;
		try {
			const data = await apiClient.get<string[]>('/api/providers/insurance-options');
			insuranceOptions = data;
			insuranceLoaded = true;
		} catch (e) {
			console.error('Failed to load insurance options:', e);
		} finally {
			insuranceLoading = false;
		}
	}

	function openInsuranceDropdown() {
		insuranceOpen = true;
		loadInsuranceOptions();
	}

	function closeInsuranceDropdown() {
		// Delay so that click on an option registers before the dropdown closes
		setTimeout(() => {
			insuranceOpen = false;
		}, 150);
	}

	function selectInsurance(value: string) {
		insurance = value;
		insuranceSearch = value;
		insuranceOpen = false;
		onchange?.();
	}

	function clearInsurance() {
		insurance = '';
		insuranceSearch = '';
		insuranceOpen = false;
		onchange?.();
	}

	function handleTypeChange(value: string) {
		providerType = value;
		onchange?.();
	}

	function handleNamsToggle() {
		namsOnly = !namsOnly;
		onchange?.();
	}
</script>

<div class="space-y-5">
	<!-- Provider type segmented control -->
	<div>
		<p class="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Provider Type</p>
		<div class="flex flex-wrap gap-1.5" role="group" aria-label="Filter by provider type">
			{#each PROVIDER_TYPES as type (type.value)}
				<button
					onclick={() => handleTypeChange(type.value)}
					aria-pressed={providerType === type.value}
					class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300
						{providerType === type.value
						? 'border-teal-500 bg-teal-500 text-white'
						: 'border-slate-200 bg-white text-slate-600 hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700'}"
				>
					{type.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- Insurance + NAMS row -->
	<div class="flex flex-wrap items-start gap-5">
		<!-- Insurance searchable combobox -->
		<div class="relative min-w-[200px] flex-1">
			<p class="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">Insurance</p>
			<div class="relative">
				<input
					type="text"
					placeholder="Filter by insurance..."
					bind:value={insuranceSearch}
					onfocus={openInsuranceDropdown}
					oninput={openInsuranceDropdown}
					onblur={closeInsuranceDropdown}
					class="w-full rounded-lg border border-slate-200 bg-white py-2 pr-8 pl-3 text-sm text-slate-700 shadow-sm transition-colors focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
				/>
				{#if insuranceSearch}
					<button
						onmousedown={(e) => e.preventDefault()}
						onclick={clearInsurance}
						class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 transition-colors hover:text-slate-600 focus:outline-none"
						aria-label="Clear insurance filter"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="size-3.5"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
						>
							<path d="M18 6 6 18M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>

			<!-- Dropdown -->
			{#if insuranceOpen}
				<div
					class="absolute left-0 top-full z-20 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg"
				>
					{#if insuranceLoading}
						<div class="px-3 py-3 text-sm text-slate-400">Loading options…</div>
					{:else if filteredInsurance.length === 0}
						<div class="px-3 py-3 text-sm text-slate-400">No matches</div>
					{:else}
						{#each filteredInsurance.slice(0, 40) as opt (opt)}
							<button
								onmousedown={(e) => e.preventDefault()}
								onclick={() => selectInsurance(opt)}
								class="block w-full px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:bg-teal-50 hover:text-teal-700 focus:bg-teal-50 focus:outline-none"
							>
								{opt}
							</button>
						{/each}
					{/if}
				</div>
			{/if}
		</div>

		<!-- NAMS Only toggle -->
		<div class="shrink-0">
			<p class="mb-2 text-xs font-medium tracking-wide text-slate-500 uppercase">NAMS Certified</p>
			<button
				onclick={handleNamsToggle}
				role="switch"
				aria-checked={namsOnly}
				class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300
					{namsOnly
					? 'border-teal-500 bg-teal-500 text-white'
					: 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'}"
			>
				<span class="text-xs">{namsOnly ? '✓' : '○'}</span>
				NAMS Only
			</button>
		</div>
	</div>
</div>
