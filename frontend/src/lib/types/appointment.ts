/**
 * Appointment Prep Flow Types
 *
 * Mirrors backend app/models/appointment.py
 */

export enum AppointmentType {
	new_provider = 'new_provider',
	established_relationship = 'established_relationship',
}

export enum AppointmentGoal {
	understand_where_i_am = 'understand_where_i_am',
	discuss_starting_hrt = 'discuss_starting_hrt',
	evaluate_current_treatment = 'evaluate_current_treatment',
	address_specific_symptom = 'address_specific_symptom',
}

export enum DismissalExperience {
	no = 'no',
	once_or_twice = 'once_or_twice',
	multiple_times = 'multiple_times',
}

export interface AppointmentContext {
	appointment_type: AppointmentType;
	goal: AppointmentGoal;
	dismissed_before: DismissalExperience;
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
	[AppointmentType.established_relationship]: 'Established relationship',
};

export const APPOINTMENT_GOAL_LABELS: Record<AppointmentGoal, string> = {
	[AppointmentGoal.understand_where_i_am]: 'Understand where I am in my journey',
	[AppointmentGoal.discuss_starting_hrt]: 'Discuss starting hormone therapy',
	[AppointmentGoal.evaluate_current_treatment]: 'Evaluate my current treatment',
	[AppointmentGoal.address_specific_symptom]: 'Address a specific symptom',
};

export const DISMISSAL_EXPERIENCE_LABELS: Record<DismissalExperience, string> = {
	[DismissalExperience.no]: 'No, I have not',
	[DismissalExperience.once_or_twice]: 'Once or twice',
	[DismissalExperience.multiple_times]: 'Multiple times',
};

/** Default concerns per goal for Step 3 */
export const DEFAULT_CONCERNS: Record<AppointmentGoal, string[]> = {
	[AppointmentGoal.understand_where_i_am]: [
		'Understand if my symptoms are related to perimenopause',
		'Learn what to expect as my hormones change',
		'Discuss whether testing is appropriate for me',
		'Get guidance on tracking my symptoms',
	],
	[AppointmentGoal.discuss_starting_hrt]: [
		'Discuss hormone therapy options available to me',
		'Understand the risks and benefits of hormone therapy',
		'Learn what to expect if I start hormone therapy',
		'Ask about non-hormonal alternatives',
	],
	[AppointmentGoal.evaluate_current_treatment]: [
		'Review how my current treatment is working',
		'Discuss adjusting my current approach',
		'Ask about trying different options',
		'Understand what the next steps should be',
	],
	[AppointmentGoal.address_specific_symptom]: [
		'Describe my most disruptive symptoms clearly',
		'Ask for evidence-based treatment options',
		'Understand the root cause of this symptom',
		'Discuss a plan to track and manage this symptom',
	],
};

export const STEP_TITLES: Record<number, string> = {
	1: 'About your appointment',
	2: 'Your symptom summary',
	3: 'Prioritize concerns',
	4: 'Practice scenarios',
	5: 'Get your materials',
};
