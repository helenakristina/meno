<script lang="ts">
	import { onMount } from 'svelte';
	import { superForm } from 'sveltekit-superforms/client';
	import { zod4 } from 'sveltekit-superforms/adapters';
	import type { SuperValidated } from 'sveltekit-superforms';
	import { contextSchema } from '$lib/schemas/appointment';
	import {
		AppointmentType,
		AppointmentGoal,
		DismissalExperience,
		APPOINTMENT_TYPE_LABELS,
		APPOINTMENT_GOAL_LABELS,
		DISMISSAL_EXPERIENCE_LABELS
	} from '$lib/types/appointment';
	import type { AppointmentContext } from '$lib/types/appointment';
	import type { AppointmentContextForm } from '$lib/schemas/appointment';

	let {
		data,
		existingContext = null,
		onNext
	}: {
		data: SuperValidated<AppointmentContextForm>;
		existingContext: AppointmentContext | null;
		onNext: (context: AppointmentContext) => void;
	} = $props();

	const form = superForm(data, {
		validators: zod4(contextSchema),
		delayMs: 200
	});

	const { form: formData, errors } = form;

	onMount(() => {
		if (existingContext) {
			$formData.appointment_type = existingContext.appointment_type;
			$formData.goal = existingContext.goal;
			$formData.dismissed_before = existingContext.dismissed_before;
			$formData.urgent_symptom = existingContext.urgent_symptom ?? '';
		}
	});

	let showUrgentSymptomField = $derived($formData.goal === AppointmentGoal.urgent_symptom);

	let canSubmit = $derived(() => {
		const hasRequired =
			!!$formData.appointment_type && !!$formData.goal && !!$formData.dismissed_before;
		const urgentSymptomValid = showUrgentSymptomField ? !!$formData.urgent_symptom?.trim() : true;
		return hasRequired && urgentSymptomValid;
	});

	function handleNext() {
		if (!canSubmit()) return;
		onNext({
			appointment_type: $formData.appointment_type as AppointmentType,
			goal: $formData.goal as AppointmentGoal,
			dismissed_before: $formData.dismissed_before as DismissalExperience,
			urgent_symptom: $formData.urgent_symptom || null
		});
	}
</script>

<div class="mx-auto max-w-2xl space-y-8">
	<!-- Question 1: Appointment type -->
	<fieldset>
		<legend class="text-base font-semibold text-neutral-800">
			What type of appointment is this?
		</legend>
		<p class="mt-1 text-sm text-neutral-500">This helps us tailor the tone of your materials.</p>
		<div class="mt-3 space-y-3">
			{#each Object.values(AppointmentType) as value}
				<label
					class="flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-colors {$formData.appointment_type ===
					value
						? 'border-primary-400 bg-primary-50'
						: 'border-neutral-200 bg-white hover:border-neutral-300'}"
				>
					<input
						type="radio"
						name="appointment_type"
						{value}
						bind:group={$formData.appointment_type}
						class="h-4 w-4"
					/>
					<span class="text-sm font-medium text-neutral-700">{APPOINTMENT_TYPE_LABELS[value]}</span>
				</label>
			{/each}
		</div>
		{#if $errors.appointment_type}
			<p class="mt-1 text-sm text-danger" id="appt-type-error">{$errors.appointment_type}</p>
		{/if}
	</fieldset>

	<!-- Question 2: Goal -->
	<fieldset>
		<legend class="text-base font-semibold text-neutral-800">
			What is your primary goal for this appointment?
		</legend>
		<p class="mt-1 text-sm text-neutral-500">
			Your goal shapes the concerns and conversation starters we generate.
		</p>
		<div class="mt-3 space-y-3">
			{#each Object.values(AppointmentGoal) as value}
				<label
					class="flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-colors {$formData.goal ===
					value
						? 'border-primary-400 bg-primary-50'
						: 'border-neutral-200 bg-white hover:border-neutral-300'}"
				>
					<input type="radio" name="goal" {value} bind:group={$formData.goal} class="h-4 w-4" />
					<span class="text-sm font-medium text-neutral-700">{APPOINTMENT_GOAL_LABELS[value]}</span>
				</label>
			{/each}
		</div>
		{#if $errors.goal}
			<p class="mt-1 text-sm text-danger">{$errors.goal}</p>
		{/if}
	</fieldset>

	<!-- Question 3: Dismissal experience -->
	<fieldset>
		<legend class="text-base font-semibold text-neutral-800">
			Have you ever felt dismissed or not taken seriously by a healthcare provider?
		</legend>
		<p class="mt-1 text-sm text-neutral-500">
			If yes, we'll include practice scenarios to help you advocate for yourself.
		</p>
		<div class="mt-3 space-y-3">
			{#each Object.values(DismissalExperience) as value}
				<label
					class="flex cursor-pointer items-center gap-3 rounded-xl border p-4 transition-colors {$formData.dismissed_before ===
					value
						? 'border-primary-400 bg-primary-50'
						: 'border-neutral-200 bg-white hover:border-neutral-300'}"
				>
					<input
						type="radio"
						name="dismissed_before"
						{value}
						bind:group={$formData.dismissed_before}
						class="h-4 w-4"
					/>
					<span class="text-sm font-medium text-neutral-700"
						>{DISMISSAL_EXPERIENCE_LABELS[value]}</span
					>
				</label>
			{/each}
		</div>
		{#if $errors.dismissed_before}
			<p class="mt-1 text-sm text-danger">{$errors.dismissed_before}</p>
		{/if}
	</fieldset>

	<!-- CONDITIONAL: Urgent Symptom Text Field -->
	{#if showUrgentSymptomField}
		<fieldset class="rounded-xl border border-warning bg-warning-light p-4">
			<legend class="font-semibold text-warning-dark"> Which symptom is most urgent? </legend>
			<p class="mt-1 text-sm text-warning-dark">
				This helps us tailor your preparation materials to your most pressing concern.
			</p>
			<input
				type="text"
				name="urgent_symptom"
				placeholder="e.g., sleep disruption, hot flashes, anxiety, cognitive difficulties"
				bind:value={$formData.urgent_symptom}
				class="mt-3 w-full rounded-lg border border-warning px-3 py-2 text-neutral-800 focus:border-warning-dark focus:ring-2 focus:ring-warning-light focus:outline-none"
				aria-invalid={showUrgentSymptomField && !$formData.urgent_symptom?.trim()}
			/>
			{#if $errors.urgent_symptom}
				<p class="mt-1 text-sm text-danger">{$errors.urgent_symptom}</p>
			{/if}
		</fieldset>
	{/if}

	<button
		type="button"
		onclick={handleNext}
		disabled={!canSubmit()}
		class="w-full rounded-xl bg-primary-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-40"
		aria-disabled={!canSubmit()}
	>
		Next: Generate health picture
	</button>
</div>
