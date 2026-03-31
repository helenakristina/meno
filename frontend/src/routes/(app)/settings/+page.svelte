<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { authState } from '$lib/stores/auth';
	import { userSettings, type UserSettings } from '$lib/stores/settings';

	type JourneyStage = 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';

	let settings = $state<UserSettings | null>(null);

	let loadError = $state<string | null>(null);

	// Section-level save states
	let journeySaving = $state(false);
	let journeySaved = $state(false);
	let journeyError = $state<string | null>(null);

	let cycleSaving = $state(false);
	let cycleError = $state<string | null>(null);

	let mhtSaving = $state(false);
	let mhtError = $state<string | null>(null);

	let anatomySaving = $state(false);
	let anatomyError = $state<string | null>(null);

	const journeyStages: { value: JourneyStage; label: string; description: string }[] = [
		{
			value: 'perimenopause',
			label: 'Perimenopause',
			description: 'Hormonal changes have begun; periods may be irregular'
		},
		{
			value: 'menopause',
			label: 'Menopause',
			description: 'One year since your last period'
		},
		{
			value: 'post-menopause',
			label: 'Post-menopause',
			description: 'More than one year since your last period'
		},
		{
			value: 'unsure',
			label: "I'm not sure",
			description: 'You can update this any time as things become clearer'
		}
	];

	onMount(async () => {
		try {
			settings = await apiClient.get('/api/users/settings');
		} catch {
			loadError = 'Unable to load settings. Please refresh and try again.';
		}
	});

	async function saveJourneyStage() {
		if (!settings) return;
		journeySaving = true;
		journeyError = null;
		journeySaved = false;
		try {
			const updated = await apiClient.patch('/api/users/settings', {
				journey_stage: settings.journey_stage as JourneyStage
			});
			settings = { ...settings, ...updated };
			journeySaved = true;
			setTimeout(() => (journeySaved = false), 3000);
		} catch {
			journeyError = 'Failed to save. Please try again.';
		} finally {
			journeySaving = false;
		}
	}

	async function saveCycleTracking(enabled: boolean) {
		if (!settings) return;
		cycleSaving = true;
		cycleError = null;
		try {
			const updated = await apiClient.patch('/api/users/settings', {
				period_tracking_enabled: enabled
			});
			settings = { ...settings, ...updated };
			userSettings.set(settings);
		} catch {
			cycleError = 'Failed to save. Please try again.';
			// Revert optimistic update
			settings = { ...settings, period_tracking_enabled: !enabled };
		} finally {
			cycleSaving = false;
		}
	}

	async function saveMhtTracking(enabled: boolean) {
		if (!settings) return;
		mhtSaving = true;
		mhtError = null;
		try {
			const updated = await apiClient.patch('/api/users/settings', {
				mht_tracking_enabled: enabled
			});
			settings = { ...settings, ...updated };
			userSettings.set(settings);
		} catch {
			mhtError = 'Failed to save. Please try again.';
			settings = { ...settings, mht_tracking_enabled: !enabled };
		} finally {
			mhtSaving = false;
		}
	}

	async function saveHasUterus(value: boolean | null) {
		if (!settings) return;
		anatomySaving = true;
		anatomyError = null;
		try {
			const updated = await apiClient.patch('/api/users/settings', {
				has_uterus: value
			});
			settings = { ...settings, ...updated };
			userSettings.set(settings);
		} catch {
			anatomyError = 'Failed to save. Please try again.';
		} finally {
			anatomySaving = false;
		}
	}

	function getJourneyStageLabel(stage: string | null): string {
		return journeyStages.find((s) => s.value === stage)?.label ?? stage ?? 'Not set';
	}
</script>

<svelte:head>
	<title>Settings — Meno</title>
</svelte:head>

<div class="mx-auto max-w-2xl">
	<h1 class="mb-8 text-2xl font-bold text-neutral-800">Settings</h1>

	{#if loadError}
		<div class="rounded-md bg-danger-light p-4 text-sm text-danger-dark" role="alert">
			{loadError}
		</div>
	{:else if !settings}
		<div class="text-neutral-600">Loading settings…</div>
	{:else}
		<!-- ================================================================
		     Journey Stage
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-neutral-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-neutral-800">Journey Stage</h2>
			<p class="mb-4 text-sm text-neutral-600">
				Where are you in your menopause journey? This helps Meno personalise your experience.

			</p>

			<fieldset class="space-y-2">
				<legend class="sr-only">Select your journey stage</legend>
				{#each journeyStages as stage}
					<label
						class="flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors {settings.journey_stage ===
						stage.value
							? 'border-neutral-700 bg-neutral-50'
							: 'border-neutral-200 hover:border-neutral-300'}"
					>
						<input
							type="radio"
							name="journey_stage"
							value={stage.value}
							bind:group={settings.journey_stage}
							class="mt-0.5 h-4 w-4 accent-primary-500"
						/>
						<div>
							<div class="text-sm font-medium text-neutral-800">{stage.label}</div>
							<div class="text-xs text-neutral-500">{stage.description}</div>
						</div>
					</label>
				{/each}
			</fieldset>

			{#if journeyError}
				<p class="mt-3 text-sm text-danger" role="alert">{journeyError}</p>
			{/if}

			<div class="mt-4 flex items-center gap-3">
				<button
					onclick={saveJourneyStage}
					disabled={journeySaving}
					class="rounded-md bg-primary-500 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
				>
					{journeySaving ? 'Saving…' : 'Save'}
				</button>
				{#if journeySaved}
					<span class="text-sm text-success">Saved!</span>
				{/if}
			</div>
		</section>

		<!-- ================================================================
		     Cycle Tracking
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-neutral-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-neutral-800">Cycle Tracking</h2>
			<p class="mb-4 text-sm text-neutral-600">
				Track your periods to help Meno understand your cycle patterns and journey stage over time.
				You can turn this off at any time.
			</p>

			<div class="flex cursor-pointer items-center gap-3">
				<button
					role="switch"
					aria-checked={settings.period_tracking_enabled}
					onclick={() => saveCycleTracking(!settings!.period_tracking_enabled)}
					disabled={cycleSaving}
					class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 focus:outline-none disabled:opacity-50 {settings.period_tracking_enabled
						? 'bg-primary-500'
						: 'bg-neutral-300'}"
					aria-label="Enable cycle tracking"
				>
					<span
						class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform {settings.period_tracking_enabled
							? 'translate-x-6'
							: 'translate-x-1'}"
					></span>
				</button>
				<span class="text-sm font-medium text-neutral-800">
					{settings.period_tracking_enabled ? 'Enabled' : 'Disabled'}
				</span>
			</div>

			{#if cycleError}
				<p class="mt-2 text-sm text-danger" role="alert">{cycleError}</p>
			{/if}
		</section>

		<!-- ================================================================
		     MHT Tracking
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-neutral-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-neutral-800">MHT Tracking</h2>
			<p class="mb-4 text-sm text-neutral-600">
				Track your Menopausal Hormone Therapy (MHT) medications to understand how they affect your
				symptoms over time. You can turn this off at any time.
			</p>

			<div class="flex cursor-pointer items-center gap-3">
				<button
					role="switch"
					aria-checked={settings.mht_tracking_enabled}
					onclick={() => saveMhtTracking(!settings!.mht_tracking_enabled)}
					disabled={mhtSaving}
					class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 focus:outline-none disabled:opacity-50 {settings.mht_tracking_enabled
						? 'bg-primary-500'
						: 'bg-neutral-300'}"
					aria-label="Enable MHT tracking"
				>
					<span
						class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform {settings.mht_tracking_enabled
							? 'translate-x-6'
							: 'translate-x-1'}"
					></span>
				</button>
				<span class="text-sm font-medium text-neutral-800">
					{settings.mht_tracking_enabled ? 'Enabled' : 'Disabled'}
				</span>
			</div>

			{#if mhtError}
				<p class="mt-2 text-sm text-danger" role="alert">{mhtError}</p>
			{/if}
		</section>

		<!-- ================================================================
		     Anatomy
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-neutral-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-neutral-800">Anatomy</h2>
			<p class="mb-4 text-sm text-neutral-600">
				This information helps us show or hide features that may not apply to you.
			</p>

			<fieldset class="space-y-2">
				<legend class="mb-2 text-sm font-medium text-neutral-700">Do you have a uterus?</legend>

				<label
					class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus ===
					true
						? 'border-neutral-700 bg-neutral-50'
						: 'border-neutral-200 hover:border-neutral-300'}"
				>
					<input
						type="radio"
						name="has_uterus"
						value="yes"
						checked={settings.has_uterus === true}
						onchange={() => saveHasUterus(true)}
						class="h-4 w-4 accent-primary-500"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-neutral-800">Yes</span>
				</label>

				<label
					class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus ===
					false
						? 'border-neutral-700 bg-neutral-50'
						: 'border-neutral-200 hover:border-neutral-300'}"
				>
					<input
						type="radio"
						name="has_uterus"
						value="no"
						checked={settings.has_uterus === false}
						onchange={() => saveHasUterus(false)}
						class="h-4 w-4 accent-primary-500"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-neutral-800">No</span>
				</label>

				<label
					class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus ===
					null
						? 'border-neutral-700 bg-neutral-50'
						: 'border-neutral-200 hover:border-neutral-300'}"
				>
					<input
						type="radio"
						name="has_uterus"
						value="prefer_not"
						checked={settings.has_uterus === null}
						onchange={() => saveHasUterus(null)}
						class="h-4 w-4 accent-primary-500"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-neutral-800">Prefer not to say</span>
				</label>
			</fieldset>

			{#if settings.has_uterus === false}
				<p class="mt-3 text-sm text-neutral-600">
					Since you don't have a uterus, period tracking has been turned off.
					You can still turn it on manually using the Cycle Tracking toggle above.
				</p>
			{/if}

			{#if anatomyError}
				<p class="mt-2 text-sm text-danger" role="alert">{anatomyError}</p>
			{/if}
		</section>

		<!-- ================================================================
		     Account
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-neutral-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-neutral-800">Account</h2>
			<dl class="space-y-3 text-sm">
				<div class="flex items-center gap-4">
					<dt class="w-24 text-neutral-500">Email</dt>
					<dd class="text-neutral-800">{$authState.user?.email ?? '—'}</dd>
				</div>
			</dl>
		</section>
	{/if}
</div>
