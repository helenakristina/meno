import { writable, derived } from 'svelte/store';
import { supabase } from '$lib/supabase/client';
import type { User } from '@supabase/supabase-js';

/**
 * Auth state store
 *
 * Tracks:
 * - user: Current authenticated user (null if logged out)
 * - isLoading: True while checking auth status
 * - error: Auth error message (null if no error)
 */
export interface AuthState {
	user: User | null;
	isLoading: boolean;
	error: string | null;
}

const initialState: AuthState = {
	user: null,
	isLoading: true, // Start with loading=true until we check session
	error: null,
};

// Main auth state store
export const authState = writable<AuthState>(initialState);

/**
 * Derived store: is user authenticated?
 * Useful for route guards and conditional rendering
 */
export const isAuthenticated = derived(authState, ($authState) => $authState.user !== null);

/**
 * Initialize auth state on app load
 */
async function initializeAuth() {
	try {
		const { data, error } = await supabase.auth.getSession();

		if (error) {
			authState.set({
				user: null,
				isLoading: false,
				error: error.message,
			});
			return;
		}

		authState.set({
			user: data.session?.user ?? null,
			isLoading: false,
			error: null,
		});
	} catch (error) {
		authState.set({
			user: null,
			isLoading: false,
			error: error instanceof Error ? error.message : 'Failed to initialize auth',
		});
	}
}

/**
 * Listen for auth state changes
 */
function setupAuthListener() {
	supabase.auth.onAuthStateChange((event, session) => {
		authState.set({
			user: session?.user ?? null,
			isLoading: false,
			error: null,
		});
	});
}

// Initialize on module load
initializeAuth();
setupAuthListener();
