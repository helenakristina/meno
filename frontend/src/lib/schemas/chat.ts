/**
 * Chat/Ask Meno form validation schemas
 */

import { z } from 'zod';

/**
 * Schema for sending a message to Ask Meno
 *
 * Constraints:
 * - Message must be 1-2000 characters
 * - Conversation ID is optional UUID
 */
export const chatMessageSchema = z.object({
	message: z
		.string()
		.min(1, 'Message cannot be empty')
		.max(2000, 'Message must be under 2000 characters')
		.trim(),
	conversation_id: z.string().uuid().optional()
});

/**
 * Inferred TypeScript type from schema
 */
export type ChatMessage = z.infer<typeof chatMessageSchema>;
