/**
 * Appointment Prep Flow Types
 *
 * Mirrors backend app/models/appointment.py
 */

export enum AppointmentType {
	new_provider = 'new_provider',
	established_relationship = 'established_relationship'
}

export enum AppointmentGoal {
	assess_status = 'assess_status',
	explore_hrt = 'explore_hrt',
	optimize_current_treatment = 'optimize_current_treatment',
	urgent_symptom = 'urgent_symptom'
}

export enum DismissalExperience {
	no = 'no',
	once_or_twice = 'once_or_twice',
	multiple_times = 'multiple_times'
}

export interface AppointmentContext {
	appointment_type: AppointmentType;
	goal: AppointmentGoal;
	dismissed_before: DismissalExperience;
	urgent_symptom?: string | null;
}

export interface ScenarioCard {
	id: string;
	title: string;
	situation: string;
	suggestion: string;
	category: string;
}

export interface AppointmentPrepState {
	appointmentId: string | null;
	context: AppointmentContext | null;
	narrative: string | null;
	concerns: string[];
	scenarios: ScenarioCard[];
	isLoading: boolean;
	error: string | null;
	currentStep: 1 | 2 | 3 | 4 | 5;
}

/** Human-readable labels for enums */
export const APPOINTMENT_TYPE_LABELS: Record<AppointmentType, string> = {
	[AppointmentType.new_provider]: 'New provider',
	[AppointmentType.established_relationship]: 'Established relationship'
};

export const APPOINTMENT_GOAL_LABELS: Record<AppointmentGoal, string> = {
	[AppointmentGoal.assess_status]: 'Understand my perimenopause/menopause status',
	[AppointmentGoal.explore_hrt]: 'Explore hormone therapy options',
	[AppointmentGoal.optimize_current_treatment]: 'Optimize my current treatment',
	[AppointmentGoal.urgent_symptom]: 'Get help with an urgent symptom'
};

export const DISMISSAL_EXPERIENCE_LABELS: Record<DismissalExperience, string> = {
	[DismissalExperience.no]: 'No, I have not',
	[DismissalExperience.once_or_twice]: 'Once or twice',
	[DismissalExperience.multiple_times]: 'Multiple times'
};

/** Default concerns per goal for Step 3 */
export const DEFAULT_CONCERNS: Record<AppointmentGoal, string[]> = {
	[AppointmentGoal.assess_status]: [
		'Confirm whether my symptoms indicate perimenopause or menopause',
		'Learn what self-tracking can tell me about my patterns',
		'Understand the progression and timeline',
		'Get evidence-based information about my stage'
	],
	[AppointmentGoal.explore_hrt]: [
		'Understand the types of hormone therapy available',
		'Learn the benefits and potential risks',
		'Discuss whether HRT is right for me',
		'Explore timing and dosing options'
	],
	[AppointmentGoal.optimize_current_treatment]: [
		'Assess whether my current treatment is working',
		'Discuss dose or timing adjustments',
		'Explore alternative approaches if needed',
		'Plan next steps based on my response'
	],
	[AppointmentGoal.urgent_symptom]: [
		'Clearly describe this symptom and its impact',
		'Understand the root cause',
		'Get targeted treatment options',
		'Create a plan to track and manage it'
	]
};

export const STEP_TITLES: Record<number, string> = {
	1: 'About your appointment',
	2: 'Your symptom summary',
	3: 'Prioritize concerns',
	4: 'Practice scenarios',
	5: 'Get your materials'
};

/** History and persistence types */

export interface AppointmentPrepHistory {
	id: string;
	appointment_id: string;
	generated_at: string; // ISO datetime
	provider_summary_path: string; // Signed URL
	personal_cheatsheet_path: string; // Signed URL
}

export interface AppointmentPrepHistoryResponse {
	preps: AppointmentPrepHistory[];
	total: number;
}
