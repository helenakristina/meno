import { writable, derived } from 'svelte/store';

/**
 * Global app state for UI-level feedback
 *
 * Tracks:
 * - isLoading: Global loading state (multiple operations can increment this)
 * - error: Global error message to display in error banner
 * - notification: Temporary success/info message
 * - toasts: Multiple notifications (for toast system in future)
 */

export interface Notification {
	id: string;
	type: 'success' | 'error' | 'info';
	message: string;
	dismissible?: boolean;
}

export interface AppState {
	isLoading: number; // Counter: 0 = not loading, >0 = loading
	error: string | null;
	notification: Notification | null;
}

const initialState: AppState = {
	isLoading: 0,
	error: null,
	notification: null
};

// Main app state store
const createAppStore = () => {
	const { subscribe, set, update } = writable<AppState>(initialState);

	return {
		subscribe,

		/**
		 * Set a global error message
		 * Automatically clears after 5 seconds if not dismissed
		 */
		setError: (message: string, autoDismissMs = 5000) => {
			update((state) => ({
				...state,
				error: message
			}));

			if (autoDismissMs > 0) {
				setTimeout(() => {
					update((state) => (state.error === message ? { ...state, error: null } : state));
				}, autoDismissMs);
			}
		},

		/**
		 * Clear the error message
		 */
		clearError: () => {
			update((state) => ({
				...state,
				error: null
			}));
		},

		/**
		 * Show a temporary notification
		 * Automatically dismisses after duration
		 */
		showNotification: (
			message: string,
			type: 'success' | 'info' = 'success',
			durationMs = 3000
		) => {
			const id = `notif-${Date.now()}`;
			update((state) => ({
				...state,
				notification: {
					id,
					type,
					message,
					dismissible: true
				}
			}));

			if (durationMs > 0) {
				setTimeout(() => {
					update((state) =>
						state.notification?.id === id ? { ...state, notification: null } : state
					);
				}, durationMs);
			}
		},

		/**
		 * Clear notification
		 */
		clearNotification: () => {
			update((state) => ({
				...state,
				notification: null
			}));
		},

		/**
		 * Increment loading counter (for multiple async operations)
		 */
		startLoading: () => {
			update((state) => ({
				...state,
				isLoading: state.isLoading + 1
			}));
		},

		/**
		 * Decrement loading counter
		 */
		stopLoading: () => {
			update((state) => ({
				...state,
				isLoading: Math.max(0, state.isLoading - 1)
			}));
		},

		/**
		 * Reset app state
		 */
		reset: () => {
			set(initialState);
		}
	};
};

export const appStore = createAppStore();

/**
 * Derived store: is app globally loading?
 */
export const isAppLoading = derived(appStore, ($appStore) => $appStore.isLoading > 0);

/**
 * Helper function for using loading state in async operations
 *
 * @example
 * const result = await withLoading(async () => {
 *   return await someAsyncOperation();
 * });
 */
export async function withLoading<T>(fn: () => Promise<T>): Promise<T> {
	appStore.startLoading();
	try {
		return await fn();
	} finally {
		appStore.stopLoading();
	}
}
