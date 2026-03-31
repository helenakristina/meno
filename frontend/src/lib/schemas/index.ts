/**
 * Central export point for all Zod validation schemas
 * Import from $lib/schemas instead of $lib/schemas/[domain]
 */

export { chatMessageSchema, type ChatMessage } from './chat';
export { onboardingSchema, type Onboarding, profileUpdateSchema, type ProfileUpdate } from './user';
export {
	symptomLogSchema,
	type SymptomLog,
	symptomFilterSchema,
	type SymptomFilter
} from './symptoms';
export {
	providerSearchSchema,
	type ProviderSearch,
	addToShortlistSchema,
	type AddToShortlist,
	updateShortlistSchema,
	type UpdateShortlist,
	callingScriptSchema,
	type CallingScript
} from './providers';
export {
	contextSchema,
	type AppointmentContextForm,
	prioritizeSchema,
	type PrioritizeForm
} from './appointment';
