/**
 * Server-side logic for Appointment Prep page
 *
 * Initializes the Superforms form for Step 1 (context selection).
 * Steps 2–5 use apiClient calls directly from the client.
 */

import { fail, type Actions } from '@sveltejs/kit';
import { superValidate } from 'sveltekit-superforms';
import { zod4 } from 'sveltekit-superforms/adapters';
import { contextSchema } from '$lib/schemas/appointment';

export async function load() {
  const form = await superValidate(zod4(contextSchema));
  return { form };
}

export const actions: Actions = {
  async context({ request }) {
    const form = await superValidate(request, zod4(contextSchema));
    if (!form.valid) return fail(400, { form });
    return { form };
  },
};
