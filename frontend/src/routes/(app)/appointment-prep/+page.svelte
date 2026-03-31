<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type {
		AppointmentContext,
		ScenarioCard,
		AppointmentPrepState
	} from '$lib/types/appointment';
	import { STEP_TITLES } from '$lib/types/appointment';
	import type { ApiError } from '$lib/types';
	import Step1Context from './Step1Context.svelte';
	import Step2Narrative from './Step2Narrative.svelte';
	import Step3Prioritize from './Step3Prioritize.svelte';
	import Step4Scenarios from './Step4Scenarios.svelte';
	import Step5Generate from './Step5Generate.svelte';

	let { data } = $props();

	// =========================================================================
	// State
	// =========================================================================

	let state = $state<AppointmentPrepState>({
		appointmentId: null,
		context: null,
		narrative: null,
		concerns: [],
		scenarios: [],
		isLoading: false,
		error: null,
		currentStep: 1
	});

	let savedStateExists = $state(false);

	let progressPercent = $derived((state.currentStep / 5) * 100);

	// =========================================================================
	// State persistence
	// =========================================================================

	// Load saved state from sessionStorage on mount
	$effect(() => {
		const saved = sessionStorage.getItem('appointmentPrepState');
		if (saved) {
			try {
				const parsed = JSON.parse(saved);
				state = parsed;
				savedStateExists = true;
			} catch (e) {
				console.error('Failed to restore appointment prep state:', e);
				savedStateExists = false;
			}
		}
	});

	// Save state to sessionStorage whenever it changes
	$effect(() => {
		sessionStorage.setItem('appointmentPrepState', JSON.stringify(state));
	});

	// =========================================================================
	// Step handlers
	// =========================================================================

	async function handleStep1(context: AppointmentContext) {
		state.isLoading = true;
		state.error = null;
		try {
			const res = await apiClient.post('/api/appointment-prep/context', {
				appointment_type: context.appointment_type,
				goal: context.goal,
				dismissed_before: context.dismissed_before,
				urgent_symptom: context.urgent_symptom || null
			});
			state.appointmentId = res.appointment_id;
			state.context = context;
			state.currentStep = 2;
		} catch (e) {
			state.error =
				e instanceof Error && 'detail' in e
					? (e as ApiError).detail
					: 'Failed to save your selections. Please try again.';
		} finally {
			state.isLoading = false;
		}
	}

	function handleStep2(narrative: string) {
		state.narrative = narrative;
		state.currentStep = 3;
	}

	function handleStep3(concerns: string[]) {
		state.concerns = concerns;
		state.currentStep = 4;
	}

	function handleStep4(scenarios: ScenarioCard[]) {
		state.scenarios = scenarios;
		state.currentStep = 5;
	}

	function handleStepError(msg: string) {
		state.error = msg;
	}

	function goBack() {
		if (state.currentStep > 1) {
			state.error = null;
			state.currentStep = (state.currentStep - 1) as 1 | 2 | 3 | 4 | 5;
		}
	}

	function startOver() {
		state = {
			appointmentId: null,
			context: null,
			narrative: null,
			concerns: [],
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 1
		};
		sessionStorage.removeItem('appointmentPrepState');
	}
</script>

<div class="flex flex-col" style="height: calc(100vh - 7rem);">
	<!-- Header with step indicator -->
	<div class="flex-shrink-0 border-b border-neutral-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold text-neutral-800">Appointment Prep</h1>
				<p class="mt-0.5 text-sm text-neutral-500">
					Step {state.currentStep} of 5: {STEP_TITLES[state.currentStep]}
				</p>
			</div>
			{#if state.currentStep > 1}
				<button
					type="button"
					onclick={goBack}
					class="rounded-lg px-3 py-2 text-sm text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-700"
					aria-label="Go back to previous step"
				>
					← Back
				</button>
			{/if}
		</div>

		<!-- Progress bar -->
		<div
			class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-neutral-100"
			role="progressbar"
			aria-valuenow={state.currentStep}
			aria-valuemin={1}
			aria-valuemax={5}
			aria-label="Step {state.currentStep} of 5"
		>
			<div
				class="h-full rounded-full bg-primary-500 transition-all duration-500"
				style="width: {progressPercent}%"
			></div>
		</div>
	</div>

	<!-- Error banner -->
	{#if state.error}
		<div
			class="flex-shrink-0 border-b border-danger-light bg-danger-light px-4 py-3 sm:px-6 lg:px-8"
			role="alert"
		>
			<div class="flex items-center justify-between text-sm text-danger-dark">
				<span>{state.error}</span>
				<button
					type="button"
					onclick={() => (state.error = null)}
					class="ml-4 font-medium underline hover:no-underline"
				>
					Dismiss
				</button>
			</div>
		</div>
	{/if}

	<!-- Loading overlay -->
	{#if state.isLoading}
		<div
			class="flex-shrink-0 border-b border-primary-100 bg-primary-50 px-4 py-3 sm:px-6 lg:px-8"
			role="status"
			aria-live="polite"
			aria-busy="true"
		>
			<p class="text-sm text-primary-700">Saving your selections…</p>
		</div>
	{/if}

	<!-- Step content -->
	<main
		class="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8"
		aria-label="Appointment prep step {state.currentStep}"
	>
		{#if savedStateExists && state.currentStep > 1}
			<div role="dialog" class="mb-6 rounded-lg border border-primary-200 bg-primary-50 p-4">
				<div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
					<div>
						<h3 class="font-semibold text-primary-900">Resume Previous Session?</h3>
						<p class="mt-1 text-sm text-primary-700">
							We found your previous appointment prep session at Step {state.currentStep}. You can
							continue where you left off or start fresh.
						</p>
					</div>
					<div class="flex flex-shrink-0 gap-2">
						<button
							type="button"
							onclick={() => (savedStateExists = false)}
							class="rounded-lg bg-primary-500 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-600"
						>
							Resume
						</button>
						<button
							type="button"
							onclick={() => {
								sessionStorage.removeItem('appointmentPrepState');
								startOver();
								savedStateExists = false;
							}}
							class="rounded-lg border border-primary-500 px-3 py-2 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50"
						>
							Start Fresh
						</button>
					</div>
				</div>
			</div>
		{/if}

		{#if state.currentStep === 1}
			<Step1Context data={data.form} onNext={handleStep1} />
		{:else if state.currentStep === 2 && state.appointmentId}
			<Step2Narrative appointmentId={state.appointmentId} onNext={handleStep2} />
		{:else if state.currentStep === 3 && state.appointmentId && state.context}
			<Step3Prioritize
				appointmentId={state.appointmentId}
				context={state.context}
				onNext={handleStep3}
				onError={handleStepError}
			/>
		{:else if state.currentStep === 4 && state.appointmentId}
			<Step4Scenarios appointmentId={state.appointmentId} onNext={handleStep4} />
		{:else if state.currentStep === 5 && state.appointmentId}
			<Step5Generate
				appointmentId={state.appointmentId}
				onStartOver={startOver}
				onError={handleStepError}
			/>
		{/if}
	</main>
</div>
