/**
 * Central export point for all frontend types
 * Import from $lib/types instead of $lib/types/[domain]
 */

export type { UserProfile, UserPreferences } from './user';
export type { Citation, Message, ChatApiResponse, ChatState } from './chat';
export type { Symptom, SymptomLog, SymptomSummary, SymptomState } from './symptoms';
export type { Provider, ProviderShortlistEntry, ProviderSearch, ProviderState } from './providers';
export type { ApiEndpoints, ApiMethod, ApiRequest, ApiResponse, ApiError } from './api';
export type { AppointmentContext, ScenarioCard, AppointmentPrepState } from './appointment';
export type { FlowLevel, PeriodLog } from './period';
export {
	AppointmentType,
	AppointmentGoal,
	DismissalExperience,
	APPOINTMENT_TYPE_LABELS,
	APPOINTMENT_GOAL_LABELS,
	DISMISSAL_EXPERIENCE_LABELS,
	DEFAULT_CONCERNS,
	STEP_TITLES
} from './appointment';
