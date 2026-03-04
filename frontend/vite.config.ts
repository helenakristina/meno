import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	ssr: {
		// Allow .svelte files in node_modules (needed for sveltekit-superforms)
		noExternal: ['sveltekit-superforms']
	},
	test: {
		expect: { requireAssertions: true },
		environment: 'jsdom',
		globals: true,
		exclude: ['node_modules', 'dist', 'tests/**']
	}
});
