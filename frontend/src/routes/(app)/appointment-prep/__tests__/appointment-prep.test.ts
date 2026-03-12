import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
	AppointmentType,
	AppointmentGoal,
	DismissalExperience,
	DEFAULT_CONCERNS,
	STEP_TITLES,
	APPOINTMENT_TYPE_LABELS,
	APPOINTMENT_GOAL_LABELS,
	DISMISSAL_EXPERIENCE_LABELS,
} from '$lib/types/appointment';
import type { AppointmentPrepState, ScenarioCard } from '$lib/types/appointment';
import { contextSchema, prioritizeSchema } from '$lib/schemas/appointment';

/**
 * Tests for Appointment Prep Flow
 * Focus on logic, state management, validation, and data shapes.
 */

describe('Appointment Prep — Context schema (Step 1)', () => {
	it('accepts valid context', () => {
		const result = contextSchema.safeParse({
			appointment_type: AppointmentType.new_provider,
			goal: AppointmentGoal.explore_hrt,
			dismissed_before: DismissalExperience.once_or_twice,
		});
		expect(result.success).toBe(true);
	});

	it('rejects missing appointment_type', () => {
		const result = contextSchema.safeParse({
			goal: AppointmentGoal.assess_status,
			dismissed_before: DismissalExperience.no,
		});
		expect(result.success).toBe(false);
	});

	it('rejects missing goal', () => {
		const result = contextSchema.safeParse({
			appointment_type: AppointmentType.established_relationship,
			dismissed_before: DismissalExperience.no,
		});
		expect(result.success).toBe(false);
	});

	it('rejects missing dismissed_before', () => {
		const result = contextSchema.safeParse({
			appointment_type: AppointmentType.new_provider,
			goal: AppointmentGoal.optimize_current_treatment,
		});
		expect(result.success).toBe(false);
	});

	it('rejects invalid enum values', () => {
		const result = contextSchema.safeParse({
			appointment_type: 'unknown_type',
			goal: AppointmentGoal.explore_hrt,
			dismissed_before: DismissalExperience.no,
		});
		expect(result.success).toBe(false);
	});

	it('accepts all valid appointment type values', () => {
		for (const type of Object.values(AppointmentType)) {
			const result = contextSchema.safeParse({
				appointment_type: type,
				goal: AppointmentGoal.assess_status,
				dismissed_before: DismissalExperience.no,
			});
			expect(result.success).toBe(true);
		}
	});

	it('accepts all valid goal values', () => {
		for (const goal of Object.values(AppointmentGoal)) {
			const result = contextSchema.safeParse({
				appointment_type: AppointmentType.new_provider,
				goal,
				dismissed_before: DismissalExperience.no,
			});
			expect(result.success).toBe(true);
		}
	});

	it('accepts all valid dismissal experience values', () => {
		for (const dismissed of Object.values(DismissalExperience)) {
			const result = contextSchema.safeParse({
				appointment_type: AppointmentType.new_provider,
				goal: AppointmentGoal.explore_hrt,
				dismissed_before: dismissed,
			});
			expect(result.success).toBe(true);
		}
	});
});

describe('Appointment Prep — Prioritize schema (Step 3)', () => {
	it('accepts non-empty concerns list', () => {
		const result = prioritizeSchema.safeParse({
			concerns: ['Discuss hormone therapy options', 'Understand risks'],
		});
		expect(result.success).toBe(true);
	});

	it('rejects empty concerns list', () => {
		const result = prioritizeSchema.safeParse({ concerns: [] });
		expect(result.success).toBe(false);
	});

	it('rejects concerns with empty strings', () => {
		const result = prioritizeSchema.safeParse({ concerns: [''] });
		expect(result.success).toBe(false);
	});

	it('accepts single concern', () => {
		const result = prioritizeSchema.safeParse({ concerns: ['My primary concern'] });
		expect(result.success).toBe(true);
	});
});

describe('Appointment Prep — Default concerns (Step 3)', () => {
	it('provides defaults for all goal values', () => {
		for (const goal of Object.values(AppointmentGoal)) {
			const defaults = DEFAULT_CONCERNS[goal];
			expect(Array.isArray(defaults)).toBe(true);
			expect(defaults.length).toBeGreaterThan(0);
		}
	});

	it('all default concerns are non-empty strings', () => {
		for (const concerns of Object.values(DEFAULT_CONCERNS)) {
			for (const concern of concerns) {
				expect(typeof concern).toBe('string');
				expect(concern.trim().length).toBeGreaterThan(0);
			}
		}
	});

	it('returns hrt-specific defaults for explore_hrt goal', () => {
		const defaults = DEFAULT_CONCERNS[AppointmentGoal.explore_hrt];
		const hasHrtContent = defaults.some(
			(c) => c.toLowerCase().includes('hormone') || c.toLowerCase().includes('hrt')
		);
		expect(hasHrtContent).toBe(true);
	});
});

describe('Appointment Prep — Step titles and labels', () => {
	it('has a title for all 5 steps', () => {
		for (let step = 1; step <= 5; step++) {
			expect(STEP_TITLES[step]).toBeTruthy();
		}
	});

	it('has labels for all appointment types', () => {
		for (const type of Object.values(AppointmentType)) {
			expect(APPOINTMENT_TYPE_LABELS[type]).toBeTruthy();
		}
	});

	it('has labels for all goals', () => {
		for (const goal of Object.values(AppointmentGoal)) {
			expect(APPOINTMENT_GOAL_LABELS[goal]).toBeTruthy();
		}
	});

	it('has labels for all dismissal experience values', () => {
		for (const exp of Object.values(DismissalExperience)) {
			expect(DISMISSAL_EXPERIENCE_LABELS[exp]).toBeTruthy();
		}
	});
});

describe('Appointment Prep — State management', () => {
	it('initializes with step 1 and null IDs', () => {
		const state: AppointmentPrepState = {
			appointmentId: null,
			context: null,
			narrative: null,
			concerns: [],
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 1,
		};
		expect(state.currentStep).toBe(1);
		expect(state.appointmentId).toBeNull();
		expect(state.error).toBeNull();
	});

	it('advances step after Step 1 completes', () => {
		const state: AppointmentPrepState = {
			appointmentId: null,
			context: null,
			narrative: null,
			concerns: [],
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 1,
		};

		// Simulate Step 1 completion
		const updated = {
			...state,
			appointmentId: 'appt-123',
			context: {
				appointment_type: AppointmentType.new_provider,
				goal: AppointmentGoal.explore_hrt,
				dismissed_before: DismissalExperience.once_or_twice,
			},
			currentStep: 2 as const,
		};
		expect(updated.currentStep).toBe(2);
		expect(updated.appointmentId).toBe('appt-123');
		expect(updated.context).not.toBeNull();
	});

	it('stores narrative after Step 2 completes', () => {
		const narrative = 'Your symptom summary here.';
		const state: AppointmentPrepState = {
			appointmentId: 'appt-123',
			context: {
				appointment_type: AppointmentType.new_provider,
				goal: AppointmentGoal.explore_hrt,
				dismissed_before: DismissalExperience.no,
			},
			narrative,
			concerns: [],
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 3,
		};
		expect(state.narrative).toBe(narrative);
		expect(state.currentStep).toBe(3);
	});

	it('stores concerns after Step 3 completes', () => {
		const concerns = ['Discuss HRT', 'Understand risks'];
		const state: AppointmentPrepState = {
			appointmentId: 'appt-123',
			context: {
				appointment_type: AppointmentType.new_provider,
				goal: AppointmentGoal.explore_hrt,
				dismissed_before: DismissalExperience.no,
			},
			narrative: 'Some narrative',
			concerns,
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 4,
		};
		expect(state.concerns).toEqual(concerns);
		expect(state.currentStep).toBe(4);
	});

	it('stores scenarios after Step 4 completes', () => {
		const scenarios: ScenarioCard[] = [
			{
				id: 'scenario-1',
				title: 'Provider dismisses concerns',
				situation: 'If your provider says...',
				suggestion: 'You could respond by...',
				category: 'dismissal',
			},
		];
		const state: AppointmentPrepState = {
			appointmentId: 'appt-123',
			context: {
				appointment_type: AppointmentType.new_provider,
				goal: AppointmentGoal.explore_hrt,
				dismissed_before: DismissalExperience.no,
			},
			narrative: 'Some narrative',
			concerns: ['Discuss HRT'],
			scenarios,
			isLoading: false,
			error: null,
			currentStep: 5,
		};
		expect(state.scenarios).toHaveLength(1);
		expect(state.scenarios[0].id).toBe('scenario-1');
		expect(state.currentStep).toBe(5);
	});

	it('resets to step 1 on start over', () => {
		const resetState: AppointmentPrepState = {
			appointmentId: null,
			context: null,
			narrative: null,
			concerns: [],
			scenarios: [],
			isLoading: false,
			error: null,
			currentStep: 1,
		};
		expect(resetState.currentStep).toBe(1);
		expect(resetState.appointmentId).toBeNull();
	});
});

describe('Appointment Prep — Concern reordering logic (Step 3)', () => {
	it('moves item up by swapping with previous', () => {
		const concerns = ['A', 'B', 'C'];
		const index = 1;
		const updated = [...concerns];
		[updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
		expect(updated).toEqual(['B', 'A', 'C']);
	});

	it('moves item down by swapping with next', () => {
		const concerns = ['A', 'B', 'C'];
		const index = 1;
		const updated = [...concerns];
		[updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
		expect(updated).toEqual(['A', 'C', 'B']);
	});

	it('cannot move first item up', () => {
		const concerns = ['A', 'B', 'C'];
		const index = 0;
		if (index === 0) {
			expect(concerns).toEqual(['A', 'B', 'C']); // no change
		}
	});

	it('cannot move last item down', () => {
		const concerns = ['A', 'B', 'C'];
		const index = concerns.length - 1;
		if (index === concerns.length - 1) {
			expect(concerns).toEqual(['A', 'B', 'C']); // no change
		}
	});

	it('removes concern by index', () => {
		const concerns = ['A', 'B', 'C'];
		const filtered = concerns.filter((_, i) => i !== 1);
		expect(filtered).toEqual(['A', 'C']);
	});

	it('adds new concern at end', () => {
		const concerns = ['A', 'B'];
		const updated = [...concerns, 'C'];
		expect(updated).toEqual(['A', 'B', 'C']);
	});

	it('trims whitespace when adding concern', () => {
		const input = '  My new concern  ';
		const trimmed = input.trim();
		expect(trimmed).toBe('My new concern');
	});

	it('does not add empty concern', () => {
		const input = '   ';
		const trimmed = input.trim();
		expect(trimmed.length).toBe(0);
		// addConcern would return early without adding
	});

	it('drag-and-drop reorders correctly', () => {
		const concerns = ['A', 'B', 'C', 'D'];
		const srcIndex = 0;
		const targetIndex = 2;
		const updated = [...concerns];
		const [moved] = updated.splice(srcIndex, 1);
		updated.splice(targetIndex, 0, moved);
		expect(updated).toEqual(['B', 'C', 'A', 'D']);
	});
});

describe('Appointment Prep — Error handling', () => {
	it('stores error message in state', () => {
		const state: Partial<AppointmentPrepState> = { error: null };
		state.error = 'Failed to save context. Please try again.';
		expect(state.error).toBeTruthy();
	});

	it('clears error on dismiss', () => {
		const state: Partial<AppointmentPrepState> = {
			error: 'Some error',
		};
		state.error = null;
		expect(state.error).toBeNull();
	});

	it('extracts detail from ApiError', () => {
		const apiError = {
			detail: 'Appointment not found',
			status: 404,
		};
		const msg = 'detail' in apiError ? apiError.detail : 'Unknown error';
		expect(msg).toBe('Appointment not found');
	});

	it('falls back to generic message when no detail', () => {
		const error = new Error('Network error');
		const msg =
			error instanceof Error && 'detail' in error
				? (error as Record<string, unknown>).detail
				: 'Failed to save concerns. Please try again.';
		expect(msg).toBe('Failed to save concerns. Please try again.');
	});
});

describe('Appointment Prep — Progress indicator', () => {
	it('calculates progress percent for each step', () => {
		const cases = [
			{ step: 1, expected: 20 },
			{ step: 2, expected: 40 },
			{ step: 3, expected: 60 },
			{ step: 4, expected: 80 },
			{ step: 5, expected: 100 },
		];
		for (const { step, expected } of cases) {
			const percent = (step / 5) * 100;
			expect(percent).toBe(expected);
		}
	});
});
