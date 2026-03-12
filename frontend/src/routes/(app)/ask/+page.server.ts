/**
 * Server-side logic for Ask Meno page
 *
 * Handles:
 * - Form validation with Superforms + Zod
 * - API calls to backend chat endpoint
 * - Error handling and user feedback
 */

import { fail, type Actions } from '@sveltejs/kit';
import { superValidate } from 'sveltekit-superforms';
import { zod4 } from 'sveltekit-superforms/adapters';
import { chatMessageSchema } from '$lib/schemas/chat';

/**
 * Load function runs before page renders
 * Initialize empty form for progressive enhancement
 * Handle resume parameter from history page
 */
export async function load({ url }) {
  const form = await superValidate(zod4(chatMessageSchema));
  const resumeId = url.searchParams.get('resume');

  return {
    form,
    resumeId,
  };
}

/**
 * Actions handle form submissions
 */
export const actions: Actions = {
  /**
   * Handle chat message submission
   *
   * Process:
   * 1. Validate request data on server
   * 2. Return validated form (client will make API call with auth token)
   */
  async chat({ request }) {
    // Validate form data against schema
    const form = await superValidate(request, zod4(chatMessageSchema));

    // Return validation result (client handles API call)
    return { form };
  },
};
