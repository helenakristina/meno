/**
 * User form validation schemas
 */

import { z } from 'zod';

/**
 * Schema for user onboarding form
 *
 * Collects:
 * - Age (optional)
 * - Journey stage (perimenopause, menopause, etc.)
 * - Insurance provider (for reference)
 * - Newsletter opt-in
 */
export const onboardingSchema = z.object({
	age: z.coerce
		.number()
		.int()
		.min(18, 'Must be 18 or older')
		.max(120, 'Please enter a valid age')
		.optional(),
	journey_stage: z.enum(['premenopause', 'perimenopause', 'menopause', 'postmenopause']).optional(),
	insurance_provider: z
		.string()
		.max(200, 'Insurance provider name must be under 200 characters')
		.optional(),
	newsletter_opt_in: z.boolean().optional()
});

/**
 * Inferred TypeScript type
 */
export type Onboarding = z.infer<typeof onboardingSchema>;

/**
 * Schema for updating user profile
 */
export const profileUpdateSchema = z.object({
	age: z.coerce
		.number()
		.int()
		.min(18, 'Must be 18 or older')
		.max(120, 'Please enter a valid age')
		.optional(),
	journey_stage: z.enum(['premenopause', 'perimenopause', 'menopause', 'postmenopause']).optional(),
	insurance_provider: z.string().max(200).optional()
});

export type ProfileUpdate = z.infer<typeof profileUpdateSchema>;
