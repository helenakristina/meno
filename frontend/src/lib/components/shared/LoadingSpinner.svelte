<script lang="ts">
	/**
	 * LoadingSpinner Component
	 *
	 * Animated spinner to indicate loading/async operations
	 *
	 * @example
	 * <LoadingSpinner size="md" />
	 * <LoadingSpinner size="lg" label="Loading data..." />
	 */

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		label?: string;
	}

	let { size = 'md', label } = $props<Props>();

	const sizeClasses = {
		sm: 'h-4 w-4',
		md: 'h-6 w-6',
		lg: 'h-8 w-8',
	};
</script>

<div class="flex items-center gap-2">
	<div
		role="status"
		aria-live="polite"
		aria-label={label || 'Loading'}
		class="animate-spin rounded-full border-2 border-slate-300 border-t-slate-600 {sizeClasses[size]}"
	></div>
	{#if label}
		<span class="text-sm text-slate-500">{label}</span>
	{/if}
</div>

<style>
	div {
		/* Smooth animation */
		animation-duration: 1s;
	}
</style>
