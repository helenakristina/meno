/**
 * Provider search and management form validation schemas
 */

import { z } from 'zod';

/**
 * Schema for provider directory search form
 *
 * At least one of state or zip_code must be provided
 */
export const providerSearchSchema = z
  .object({
    state: z
      .string()
      .length(2, 'State must be 2 letters')
      .optional(),
    city: z
      .string()
      .max(100, 'City name must be under 100 characters')
      .optional(),
    zip_code: z
      .string()
      .regex(/^\d{5}(-\d{4})?$/, 'Invalid ZIP code format')
      .optional(),
    nams_only: z.boolean().default(true),
    provider_type: z
      .enum(['ob_gyn', 'internal_medicine', 'np_pa', 'integrative_medicine', 'other'])
      .optional(),
    insurance: z
      .string()
      .max(100)
      .optional(),
    page: z.coerce
      .number()
      .int()
      .min(1)
      .default(1),
    page_size: z.coerce
      .number()
      .int()
      .min(1)
      .max(50)
      .default(20),
  })
  .refine(
    (data) => {
      // At least state or zip_code required
      return (data.state && data.state.length > 0) || (data.zip_code && data.zip_code.length > 0);
    },
    {
      message: 'Please enter a state or ZIP code',
      path: ['state'],
    }
  );

/**
 * Inferred TypeScript type
 */
export type ProviderSearch = z.infer<typeof providerSearchSchema>;

/**
 * Schema for adding provider to shortlist
 */
export const addToShortlistSchema = z.object({
  provider_id: z.string().uuid('Invalid provider ID'),
});

export type AddToShortlist = z.infer<typeof addToShortlistSchema>;

/**
 * Schema for updating shortlist entry (status and notes)
 */
export const updateShortlistSchema = z.object({
  provider_id: z.string().uuid('Invalid provider ID'),
  status: z
    .enum(['contact_pending', 'contacted', 'completed', 'other'])
    .describe('Call status'),
  notes: z
    .string()
    .max(500, 'Notes must be under 500 characters')
    .optional(),
});

export type UpdateShortlist = z.infer<typeof updateShortlistSchema>;

/**
 * Schema for calling script request
 */
export const callingScriptSchema = z.object({
  provider_id: z.string().uuid('Invalid provider ID'),
  questions: z
    .array(z.string())
    .default([])
    .describe('Custom questions to include in script'),
});

export type CallingScript = z.infer<typeof callingScriptSchema>;
