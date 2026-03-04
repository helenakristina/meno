import type { User } from '@supabase/supabase-js';

declare global {
	namespace App {
		/**
		 * Error object passed to error pages (+error.svelte).
		 * Thrown when a route handler encounters an error.
		 */
		interface Error {
			message: string;
			code?: string;
			details?: Record<string, unknown>;
		}

		/**
		 * Server-side context available in hooks and server routes.
		 * Populated in +layout.server.ts or hooks.ts.
		 */
		interface Locals {
			user?: {
				id: string;
				email: string;
			};
		}

		/**
		 * Base type for all page data.
		 * Each route can extend this with specific data via route's PageData type.
		 */
		interface PageData {
			user?: User | null;
			[key: string]: unknown;
		}

		/**
		 * Client-only state that persists across navigation.
		 * Used for form state, scroll position, etc.
		 */
		interface PageState {
			formState?: Record<string, unknown>;
			scrollPosition?: number;
		}
	}
}

export {};
