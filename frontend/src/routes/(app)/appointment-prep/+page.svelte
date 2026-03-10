<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { AppointmentContext, ScenarioCard, AppointmentPrepState } from '$lib/types/appointment';
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
		currentStep: 1,
	});

	let progressPercent = $derived((state.currentStep / 5) * 100);

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
				urgent_symptom: context.urgent_symptom || null,
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
			currentStep: 1,
		};
	}
</script>

<div class="flex flex-col" style="height: calc(100vh - 7rem);">
	<!-- Header with step indicator -->
	<div class="flex-shrink-0 border-b border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold text-slate-900">Appointment Prep</h1>
				<p class="mt-0.5 text-sm text-slate-500">
					Step {state.currentStep} of 5: {STEP_TITLES[state.currentStep]}
				</p>
			</div>
			{#if state.currentStep > 1}
				<button
					type="button"
					onclick={goBack}
					class="rounded-lg px-3 py-2 text-sm text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
					aria-label="Go back to previous step"
				>
					← Back
				</button>
			{/if}
		</div>

		<!-- Progress bar -->
		<div
			class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
			role="progressbar"
			aria-valuenow={state.currentStep}
			aria-valuemin={1}
			aria-valuemax={5}
			aria-label="Step {state.currentStep} of 5"
		>
			<div
				class="h-full rounded-full bg-teal-500 transition-all duration-500"
				style="width: {progressPercent}%"
			></div>
		</div>
	</div>

	<!-- Error banner -->
	{#if state.error}
		<div
			class="flex-shrink-0 border-b border-red-200 bg-red-50 px-4 py-3 sm:px-6 lg:px-8"
			role="alert"
		>
			<div class="flex items-center justify-between text-sm text-red-700">
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
			class="flex-shrink-0 border-b border-teal-100 bg-teal-50 px-4 py-3 sm:px-6 lg:px-8"
			role="status"
			aria-live="polite"
			aria-busy="true"
		>
			<p class="text-sm text-teal-700">Saving your selections…</p>
		</div>
	{/if}

	<!-- Step content -->
	<main
		class="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8"
		aria-label="Appointment prep step {state.currentStep}"
	>
		{#if state.currentStep === 1}
			<Step1Context data={data.form} onNext={handleStep1} />
		{:else if state.currentStep === 2 && state.appointmentId}
			<Step2Narrative
				appointmentId={state.appointmentId}
				onNext={handleStep2}
				onError={handleStepError}
			/>
		{:else if state.currentStep === 3 && state.appointmentId && state.context}
			<Step3Prioritize
				appointmentId={state.appointmentId}
				context={state.context}
				onNext={handleStep3}
				onError={handleStepError}
			/>
		{:else if state.currentStep === 4 && state.appointmentId}
			<Step4Scenarios
				appointmentId={state.appointmentId}
				onNext={handleStep4}
				onError={handleStepError}
			/>
		{:else if state.currentStep === 5 && state.appointmentId}
			<Step5Generate
				appointmentId={state.appointmentId}
				onStartOver={startOver}
				onError={handleStepError}
			/>
		{/if}
	</main>
</div>
