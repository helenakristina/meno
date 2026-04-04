/**
 * Appointment Prep Flow validation schemas
 */

import { z } from 'zod';
import { AppointmentType, AppointmentGoal, DismissalExperience } from '$lib/types/appointment';

export const contextSchema = z.object({
	appointment_type: z.nativeEnum(AppointmentType),
	goal: z.nativeEnum(AppointmentGoal),
	dismissed_before: z.nativeEnum(DismissalExperience),
	urgent_symptom: z.string().optional().nullable()
});

export type AppointmentContextForm = z.infer<typeof contextSchema>;

export const concernSchema = z.object({
	text: z.string().min(1),
	comment: z.string().max(200).optional()
});

export const prioritizeSchema = z.object({
	concerns: z.array(concernSchema).min(1, 'At least one concern is required')
});

export type PrioritizeForm = z.infer<typeof prioritizeSchema>;
