<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { authState } from '$lib/stores/auth';

	type JourneyStage = 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';

	let settings = $state<{
		period_tracking_enabled: boolean;
		has_uterus: boolean | null;
		journey_stage: string | null;
	} | null>(null);

	let loadError = $state<string | null>(null);

	// Section-level save states
	let journeySaving = $state(false);
	let journeySaved = $state(false);
	let journeyError = $state<string | null>(null);

	let cycleSaving = $state(false);
	let cycleError = $state<string | null>(null);

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
			description: "You can update this any time as things become clearer"
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
		} catch {
			cycleError = 'Failed to save. Please try again.';
			// Revert optimistic update
			settings = { ...settings, period_tracking_enabled: !enabled };
		} finally {
			cycleSaving = false;
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
	<h1 class="mb-8 text-2xl font-bold text-slate-900">Settings</h1>

	{#if loadError}
		<div class="rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">
			{loadError}
		</div>
	{:else if !settings}
		<div class="text-slate-600">Loading settings…</div>
	{:else}
		<!-- ================================================================
		     Journey Stage
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-slate-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-slate-900">Journey Stage</h2>
			<p class="mb-4 text-sm text-slate-600">
				Where are you in your menopause journey? This helps Meno personalise your experience.
			</p>

			<fieldset class="space-y-2">
				<legend class="sr-only">Select your journey stage</legend>
				{#each journeyStages as stage}
					<label
						class="flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors {settings.journey_stage === stage.value
							? 'border-slate-700 bg-slate-50'
							: 'border-slate-200 hover:border-slate-300'}"
					>
						<input
							type="radio"
							name="journey_stage"
							value={stage.value}
							bind:group={settings.journey_stage}
							class="mt-0.5 h-4 w-4 accent-slate-800"
						/>
						<div>
							<div class="text-sm font-medium text-slate-900">{stage.label}</div>
							<div class="text-xs text-slate-500">{stage.description}</div>
						</div>
					</label>
				{/each}
			</fieldset>

			{#if journeyError}
				<p class="mt-3 text-sm text-red-600" role="alert">{journeyError}</p>
			{/if}

			<div class="mt-4 flex items-center gap-3">
				<button
					onclick={saveJourneyStage}
					disabled={journeySaving}
					class="rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
				>
					{journeySaving ? 'Saving…' : 'Save'}
				</button>
				{#if journeySaved}
					<span class="text-sm text-green-600">Saved!</span>
				{/if}
			</div>
		</section>

		<!-- ================================================================
		     Cycle Tracking
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-slate-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-slate-900">Cycle Tracking</h2>
			<p class="mb-4 text-sm text-slate-600">
				Track your periods to help Meno understand your cycle patterns and journey stage over time.
				You can turn this off at any time.
			</p>

			<label class="flex cursor-pointer items-center gap-3">
				<button
					role="switch"
					aria-checked={settings.period_tracking_enabled}
					onclick={() => saveCycleTracking(!settings!.period_tracking_enabled)}
					disabled={cycleSaving}
					class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-1 disabled:opacity-50 {settings.period_tracking_enabled
						? 'bg-slate-800'
						: 'bg-slate-300'}"
					aria-label="Enable cycle tracking"
				>
					<span
						class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform {settings.period_tracking_enabled
							? 'translate-x-6'
							: 'translate-x-1'}"
					></span>
				</button>
				<span class="text-sm font-medium text-slate-900">
					{settings.period_tracking_enabled ? 'Enabled' : 'Disabled'}
				</span>
			</label>

			{#if cycleError}
				<p class="mt-2 text-sm text-red-600" role="alert">{cycleError}</p>
			{/if}
		</section>

		<!-- ================================================================
		     Anatomy
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-slate-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-slate-900">Anatomy</h2>
			<p class="mb-4 text-sm text-slate-600">
				This information helps us show or hide features that may not apply to you.
			</p>

			<fieldset class="space-y-2">
				<legend class="text-sm font-medium text-slate-700 mb-2">Do you have a uterus?</legend>

				<label class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus === true ? 'border-slate-700 bg-slate-50' : 'border-slate-200 hover:border-slate-300'}">
					<input
						type="radio"
						name="has_uterus"
						value="yes"
						checked={settings.has_uterus === true}
						onchange={() => saveHasUterus(true)}
						class="h-4 w-4 accent-slate-800"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-slate-900">Yes</span>
				</label>

				<label class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus === false ? 'border-slate-700 bg-slate-50' : 'border-slate-200 hover:border-slate-300'}">
					<input
						type="radio"
						name="has_uterus"
						value="no"
						checked={settings.has_uterus === false}
						onchange={() => saveHasUterus(false)}
						class="h-4 w-4 accent-slate-800"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-slate-900">No</span>
				</label>

				<label class="flex cursor-pointer items-center gap-3 rounded-md border p-3 transition-colors {settings.has_uterus === null ? 'border-slate-700 bg-slate-50' : 'border-slate-200 hover:border-slate-300'}">
					<input
						type="radio"
						name="has_uterus"
						value="prefer_not"
						checked={settings.has_uterus === null}
						onchange={() => saveHasUterus(null)}
						class="h-4 w-4 accent-slate-800"
						disabled={anatomySaving}
					/>
					<span class="text-sm text-slate-900">Prefer not to say</span>
				</label>
			</fieldset>

			{#if settings.has_uterus === false}
				<p class="mt-3 text-sm text-slate-600">
					Since you don't have a uterus, period tracking has been turned off.
					You can still turn it on manually using the Cycle Tracking toggle above.
				</p>
			{/if}

			{#if anatomyError}
				<p class="mt-2 text-sm text-red-600" role="alert">{anatomyError}</p>
			{/if}
		</section>

		<!-- ================================================================
		     Account
		     ================================================================ -->
		<section class="mb-8 rounded-lg border border-slate-200 bg-white p-6">
			<h2 class="mb-1 text-base font-semibold text-slate-900">Account</h2>
			<dl class="space-y-3 text-sm">
				<div class="flex items-center gap-4">
					<dt class="w-24 text-slate-500">Email</dt>
					<dd class="text-slate-900">{$authState.user?.email ?? '—'}</dd>
				</div>
			</dl>
		</section>
	{/if}
</div>
