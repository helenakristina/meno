/**
 * Symptom logging form validation schemas
 */

import { z } from 'zod';

/**
 * Schema for creating a symptom log entry
 *
 * Constraints:
 * - Either symptoms (cards) or free_text_entry (text) or both
 * - Symptoms are UUIDs from the symptoms_reference table
 * - Free text entry is optional notes
 * - Source indicates how the log was created
 * - logged_at is optional (defaults to now)
 */
export const symptomLogSchema = z
	.object({
		symptoms: z
			.array(z.string().uuid('Invalid symptom ID'))
			.default([])
			.describe('Array of symptom UUIDs'),
		free_text_entry: z.string().max(2000, 'Notes must be under 2000 characters').optional(),
		source: z.enum(['cards', 'text', 'both']).describe('How the log was created'),
		logged_at: z.coerce.date().optional()
	})
	.refine(
		(data) => {
			// Either symptoms or free_text_entry must be provided
			return (
				data.symptoms.length > 0 || (data.free_text_entry && data.free_text_entry.trim().length > 0)
			);
		},
		{
			message: 'Please select at least one symptom or add notes',
			path: ['symptoms'] // Show error on symptoms field
		}
	)
	.refine(
		(data) => {
			// If source is 'cards', symptoms must have entries
			if (data.source === 'cards' || data.source === 'both') {
				return data.symptoms.length > 0;
			}
			return true;
		},
		{
			message: 'Please select at least one symptom',
			path: ['symptoms']
		}
	)
	.refine(
		(data) => {
			// If source is 'text', free_text_entry must have content
			if (data.source === 'text' || data.source === 'both') {
				return data.free_text_entry && data.free_text_entry.trim().length > 0;
			}
			return true;
		},
		{
			message: 'Please add some notes',
			path: ['free_text_entry']
		}
	);

/**
 * Inferred TypeScript type
 */
export type SymptomLog = z.infer<typeof symptomLogSchema>;

/**
 * Schema for symptom log search/filter form
 */
export const symptomFilterSchema = z.object({
	start_date: z.coerce.date().optional(),
	end_date: z.coerce.date().optional(),
	limit: z.coerce.number().int().min(1).max(100).default(50)
});

export type SymptomFilter = z.infer<typeof symptomFilterSchema>;
