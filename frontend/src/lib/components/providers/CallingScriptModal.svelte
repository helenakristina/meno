<script lang="ts">
	import { apiClient } from '$lib/api/client';

	type ModalState = 'form' | 'loading' | 'result';
	type InsuranceType = 'private' | 'medicare' | 'medicaid' | 'self_pay' | 'other';

	const STATUSES = [
		{ value: 'to_call', label: 'To Call' },
		{ value: 'called', label: 'Called' },
		{ value: 'left_voicemail', label: 'Left Voicemail' },
		{ value: 'booking', label: 'Booking Appointment' },
		{ value: 'not_available', label: 'Not Available' }
	] as const;

	type ShortlistStatus = (typeof STATUSES)[number]['value'];

	interface Provider {
		id: string;
		name: string;
		credentials: string | null;
		practice_name: string | null;
		phone: string | null;
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
		open = $bindable(false),
		provider,
		isSaved = false,
		shortlistEntry = null,
		onSave,
		onShortlistChange
	}: {
		open: boolean;
		provider: Provider | null;
		isSaved?: boolean;
		shortlistEntry?: ShortlistEntry | null;
		onSave?: () => void;
		onShortlistChange?: () => void;
	} = $props();

	let modalState = $state<ModalState>('form');
	let insuranceType = $state<InsuranceType | ''>('');
	let insurancePlanName = $state('');
	let insurancePlanUnknown = $state(false);
	let interestedInTelehealth = $state(false);
	let generatedScript = $state('');
	let error = $state('');
	let copied = $state(false);
	// True while fetching saved insurance preference on open — skeletons the form fields
	let prefLoading = $state(false);

	// Call tracker state (managed locally in result state)
	let localIsSaved = $state(false);
	let localStatus = $state<ShortlistStatus>('to_call');
	let localNotes = $state('');
	let notesSaving = $state(false);
	let notesSaved = $state(false);
	let trackerSaving = $state(false);

	let isFormValid = $derived(insuranceType !== '');

	const INSURANCE_OPTIONS: { value: InsuranceType; label: string }[] = [
		{ value: 'private', label: 'Private Insurance' },
		{ value: 'medicare', label: 'Medicare' },
		{ value: 'medicaid', label: 'Medicaid' },
		{ value: 'self_pay', label: 'Self-pay' },
		{ value: 'other', label: 'Other' }
	];

	const STATUS_COLORS: Record<ShortlistStatus, string> = {
		to_call: 'text-blue-700 border-blue-200 bg-blue-50',
		called: 'text-teal-700 border-teal-200 bg-teal-50',
		left_voicemail: 'text-amber-700 border-amber-200 bg-amber-50',
		booking: 'text-green-700 border-green-200 bg-green-50',
		not_available: 'text-slate-500 border-slate-200 bg-slate-50'
	};

	function close() {
		open = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	// Reset form state and load saved preference each time the modal opens.
	// Also sync call tracker state from props.
	$effect(() => {
		if (open) {
			modalState = 'form';
			insuranceType = '';
			insurancePlanName = '';
			insurancePlanUnknown = false;
			interestedInTelehealth = false;
			generatedScript = '';
			error = '';
			copied = false;

			// Sync call tracker from parent props
			localIsSaved = isSaved;
			localStatus = (shortlistEntry?.status as ShortlistStatus) ?? 'to_call';
			localNotes = shortlistEntry?.notes ?? '';
			notesSaved = false;

			loadInsurancePreference();
		}
	});

	async function loadInsurancePreference() {
		prefLoading = true;
		try {
			const pref = await apiClient.get<{
				insurance_type: string | null;
				insurance_plan_name: string | null;
			}>('/api/users/insurance-preference');

			const validTypes: InsuranceType[] = ['private', 'medicare', 'medicaid', 'self_pay', 'other'];
			if (pref.insurance_type && validTypes.includes(pref.insurance_type as InsuranceType)) {
				insuranceType = pref.insurance_type as InsuranceType;
			}
			if (pref.insurance_plan_name) {
				insurancePlanName = pref.insurance_plan_name;
			}
		} catch {
			// Fail silently — show blank form
		} finally {
			prefLoading = false;
		}
	}

	async function saveInsurancePreference() {
		if (!insuranceType) return;
		try {
			await apiClient.patch('/api/users/insurance-preference', {
				insurance_type: insuranceType,
				insurance_plan_name: insurancePlanName.trim() || null
			});
		} catch {
			// Fail silently — persistence is a convenience feature
		}
	}

	function selectInsuranceType(type: InsuranceType) {
		insuranceType = type;
		insurancePlanName = '';
		insurancePlanUnknown = false;
	}

	async function generateScript() {
		if (!provider || !insuranceType) return;

		modalState = 'loading';
		error = '';

		const providerName = provider.credentials
			? `${provider.name}, ${provider.credentials}`
			: provider.name;

		try {
			const response = await apiClient.post<{ script: string; provider_name: string }>(
				'/api/providers/calling-script',
				{
					provider_id: provider.id,
					provider_name: providerName,
					insurance_type: insuranceType,
					insurance_plan_name: insurancePlanName.trim() || null,
					insurance_plan_unknown: insurancePlanUnknown,
					interested_in_telehealth: interestedInTelehealth
				}
			);
			generatedScript = response.script;
			modalState = 'result';
			// Fire-and-forget: persist insurance selection for next open
			saveInsurancePreference();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to generate script. Please try again.';
			modalState = 'form';
		}
	}

	async function copyToClipboard() {
		try {
			await navigator.clipboard.writeText(generatedScript);
			copied = true;
			setTimeout(() => {
				copied = false;
			}, 2000);
		} catch {
			// Clipboard API unavailable — silent fail
		}
	}

	function generateAgain() {
		modalState = 'form';
		generatedScript = '';
		error = '';
	}

	// ---------------------------------------------------------------------------
	// Call tracker actions
	// ---------------------------------------------------------------------------

	async function handleSaveToList() {
		if (!provider || trackerSaving) return;
		trackerSaving = true;
		try {
			await apiClient.post('/api/providers/shortlist', { provider_id: provider.id });
			localIsSaved = true;
			localStatus = 'to_call';
			onSave?.();
			onShortlistChange?.();
		} catch {
			// If 409, it's already saved — sync local state
			localIsSaved = true;
		} finally {
			trackerSaving = false;
		}
	}

	async function handleStatusChange(newStatus: ShortlistStatus) {
		if (!provider || localStatus === newStatus) return;
		localStatus = newStatus;
		try {
			await apiClient.patch(`/api/providers/shortlist/${provider.id}`, {
				status: newStatus
			});
			onShortlistChange?.();
		} catch {
			// Fail silently — status will resync on next page load
		}
	}

	async function handleNotesBlur() {
		if (!provider || !localIsSaved) return;
		// Skip if notes haven't changed from what the parent passed in
		const originalNotes = shortlistEntry?.notes ?? '';
		if (localNotes === originalNotes) return;

		notesSaving = true;
		try {
			await apiClient.patch(`/api/providers/shortlist/${provider.id}`, {
				notes: localNotes
			});
			notesSaved = true;
			setTimeout(() => (notesSaved = false), 2000);
			onShortlistChange?.();
		} catch {
			// Fail silently
		} finally {
			notesSaving = false;
		}
	}
</script>

{#if open && provider}
	<!-- Backdrop -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 backdrop-blur-sm sm:items-center"
		role="dialog"
		aria-modal="true"
		aria-labelledby="calling-script-title"
		tabindex="-1"
		onclick={close}
		onkeydown={handleKeydown}
	>
		<!-- Panel — stop propagation so clicking inside doesn't close -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			class="w-full max-w-md rounded-2xl bg-white px-6 py-6 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="document"
		>
			<!-- Header -->
			<div class="mb-5 flex items-start justify-between gap-4">
				<div>
					<h2 id="calling-script-title" class="text-base font-semibold text-slate-900">
						{modalState === 'result' ? 'Your Calling Script' : 'Generate Calling Script'}
					</h2>
					<p class="mt-0.5 text-sm text-slate-500">
						{provider.name}{provider.credentials ? `, ${provider.credentials}` : ''}
						{#if provider.practice_name}
							<span class="text-slate-400"> · {provider.practice_name}</span>
						{/if}
					</p>
				</div>
				<button
					onclick={close}
					class="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
					aria-label="Close modal"
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

			<!-- ── FORM STATE ────────────────────────────────────────────── -->
			{#if modalState === 'form'}
				<div class="space-y-5">
					<!-- Insurance type selector -->
					<div>
						<p class="mb-2 text-sm font-medium text-slate-700">Insurance type</p>
						{#if prefLoading}
							<!-- Skeleton pills while saved preference loads -->
							<div class="flex flex-wrap gap-1.5" aria-hidden="true">
								{#each [80, 72, 72, 64, 52] as w}
									<div
										class="h-7 animate-pulse rounded-full bg-slate-100"
										style="width: {w}px"
									></div>
								{/each}
							</div>
						{:else}
							<div class="flex flex-wrap gap-1.5" role="group" aria-label="Select insurance type">
								{#each INSURANCE_OPTIONS as opt (opt.value)}
									<button
										onclick={() => selectInsuranceType(opt.value)}
										aria-pressed={insuranceType === opt.value}
										class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300
											{insuranceType === opt.value
											? 'border-teal-500 bg-teal-500 text-white'
											: 'border-slate-200 bg-white text-slate-600 hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700'}"
									>
										{opt.label}
									</button>
								{/each}
							</div>
						{/if}
					</div>

					<!-- Conditional plan name fields -->
					{#if prefLoading}
						<!-- Skeleton input while preference loads -->
						<div class="h-9 w-full animate-pulse rounded-lg bg-slate-100"></div>
					{:else if insuranceType === 'private'}
						<div>
							<label
								class="mb-1.5 block text-sm font-medium text-slate-700"
								for="cs-insurance-plan"
							>
								Your insurance plan
							</label>
							<input
								id="cs-insurance-plan"
								type="text"
								bind:value={insurancePlanName}
								placeholder="e.g. Aetna PPO, Blue Cross Blue Shield"
								class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
							/>
						</div>
					{:else if insuranceType === 'medicaid'}
						<div>
							<label
								class="mb-1.5 block text-sm font-medium text-slate-700"
								for="cs-medicaid-plan"
							>
								Your Medicaid plan name
							</label>
							<p class="mb-2 text-xs text-slate-500">
								This is the name on your Medicaid card or welcome letter — e.g. "UCare", "Hennepin
								Health", "Blue Plus", "Centene"
							</p>
							<input
								id="cs-medicaid-plan"
								type="text"
								bind:value={insurancePlanName}
								disabled={insurancePlanUnknown}
								placeholder="e.g. UCare"
								class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none disabled:bg-slate-50 disabled:text-slate-400"
							/>
							<label class="mt-2 flex cursor-pointer items-center gap-2 text-sm text-slate-600">
								<input
									type="checkbox"
									bind:checked={insurancePlanUnknown}
									class="rounded border-slate-300 text-teal-500 focus:ring-teal-300"
								/>
								I'm not sure of my specific plan
							</label>
						</div>
					{:else if insuranceType === 'medicare'}
						<div>
							<label
								class="mb-1.5 block text-sm font-medium text-slate-700"
								for="cs-medicare-plan"
							>
								Your Medicare plan
							</label>
							<p class="mb-2 text-xs text-slate-500">
								If you have a Medicare Advantage plan, enter its name. If you have original Medicare
								(Parts A & B only), leave blank.
							</p>
							<input
								id="cs-medicare-plan"
								type="text"
								bind:value={insurancePlanName}
								placeholder="e.g. UnitedHealthcare AARP, Humana Gold"
								class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
							/>
						</div>
					{:else if insuranceType === 'other'}
						<div>
							<label
								class="mb-1.5 block text-sm font-medium text-slate-700"
								for="cs-other-insurance"
							>
								Your insurance or coverage
							</label>
							<input
								id="cs-other-insurance"
								type="text"
								bind:value={insurancePlanName}
								placeholder="Describe your coverage"
								class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
							/>
						</div>
					{/if}

					<!-- Telehealth checkbox -->
					<label class="flex cursor-pointer items-center gap-2.5 text-sm text-slate-700">
						<input
							type="checkbox"
							bind:checked={interestedInTelehealth}
							class="rounded border-slate-300 text-teal-500 focus:ring-teal-300"
						/>
						I'm interested in telehealth appointments
					</label>

					<!-- Inline error -->
					{#if error}
						<p class="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
							{error}
						</p>
					{/if}

					<!-- Generate button -->
					<button
						onclick={generateScript}
						disabled={!isFormValid}
						class="w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300
							{isFormValid
							? 'bg-slate-900 text-white hover:bg-slate-800'
							: 'cursor-not-allowed bg-slate-100 text-slate-400'}"
					>
						Generate My Script
					</button>
				</div>

			<!-- ── LOADING STATE ─────────────────────────────────────────── -->
			{:else if modalState === 'loading'}
				<div class="flex flex-col items-center gap-4 py-8">
					<div
						class="size-8 animate-spin rounded-full border-2 border-slate-200 border-t-teal-500"
					></div>
					<p class="text-sm text-slate-500">Writing your script…</p>
				</div>

			<!-- ── RESULT STATE ──────────────────────────────────────────── -->
			{:else if modalState === 'result'}
				<div class="space-y-4">
					<!-- Script card — warm off-white, generous line height for reading aloud -->
					<div class="rounded-xl bg-amber-50 px-5 py-4">
						<p class="text-base leading-relaxed text-slate-800">{generatedScript}</p>
					</div>

					<!-- Ready to call row -->
					{#if provider.phone}
						<div class="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-3">
							<span class="text-slate-400">📞</span>
							<span class="text-sm text-slate-500">Ready to call?</span>
							<a
								href="tel:{provider.phone}"
								class="text-sm font-medium text-teal-600 hover:text-teal-800"
							>
								{provider.phone}
							</a>
						</div>
					{/if}

					<!-- ── CALL TRACKER ─────────────────────────────────── -->
					{#if onSave || localIsSaved}
						<div class="rounded-xl border border-slate-100 bg-slate-50 px-4 py-4">
							<p class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
								Call Tracker
							</p>

							{#if !localIsSaved}
								<!-- Save to list button -->
								<button
									onclick={handleSaveToList}
									disabled={trackerSaving}
									class="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300 disabled:cursor-not-allowed disabled:opacity-60"
								>
									{#if trackerSaving}
										<div
											class="size-4 animate-spin rounded-full border-2 border-slate-200 border-t-slate-500"
										></div>
										Saving…
									{:else}
										<svg
											xmlns="http://www.w3.org/2000/svg"
											class="size-4"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											stroke-width="1.75"
										>
											<path d="M19 21l-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
										</svg>
										Save to my list
									{/if}
								</button>
							{:else}
								<!-- Status selector -->
								<div class="mb-3">
									<label for="cs-status" class="mb-1.5 block text-xs font-medium text-slate-500">
										Status
									</label>
									<select
										id="cs-status"
										value={localStatus}
										onchange={(e) =>
											handleStatusChange(
												(e.target as HTMLSelectElement).value as ShortlistStatus
											)}
										class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
									>
										{#each STATUSES as s (s.value)}
											<option value={s.value}>{s.label}</option>
										{/each}
									</select>
								</div>

								<!-- Notes textarea -->
								<div>
									<div class="mb-1.5 flex items-center justify-between">
										<label for="cs-notes" class="text-xs font-medium text-slate-500">
											Notes
										</label>
										{#if notesSaving}
											<span class="text-xs text-slate-400">Saving…</span>
										{:else if notesSaved}
											<span class="text-xs text-teal-600">Saved</span>
										{/if}
									</div>
									<textarea
										id="cs-notes"
										bind:value={localNotes}
										onblur={handleNotesBlur}
										placeholder="e.g. Said to call back in March, only takes UCare not Hennepin Health"
										rows={3}
										class="w-full resize-none rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-teal-400 focus:ring-2 focus:ring-teal-200 focus:outline-none"
									></textarea>
									<p class="mt-1 text-xs text-slate-400">
										Saved automatically when you click away.
									</p>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Actions -->
					<div class="flex gap-2">
						<button
							onclick={copyToClipboard}
							class="flex-1 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
						>
							{copied ? 'Copied!' : 'Copy to Clipboard'}
						</button>
						<button
							onclick={generateAgain}
							class="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-300"
						>
							Generate Again
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
