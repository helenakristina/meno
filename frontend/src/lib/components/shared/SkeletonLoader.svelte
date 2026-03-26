<script lang="ts">
	/**
	 * SkeletonLoader Component
	 *
	 * Animated skeleton placeholder for loading states
	 * Helps users understand that content is loading
	 *
	 * @example
	 * <SkeletonLoader lines={3} />
	 * <SkeletonLoader variant="card" />
	 * <SkeletonLoader lines={5} variant="text" height="h-6" />
	 */

	interface Props {
		lines?: number;
		variant?: 'text' | 'card' | 'title';
		height?: string;
	}

	let { lines = 3, variant = 'text', height } = $props<Props>();

	// Determine height based on variant
	const heightClass = $derived(
		height ||
		{
			text: 'h-4',
			title: 'h-6',
			card: 'h-32',
		}[variant]
	);
</script>

<div class="space-y-2">
	{#each { length: variant === 'card' ? 1 : lines } as _}
		{#if variant === 'card'}
			<!-- Card skeleton -->
			<div class="space-y-3 rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
				<div class="h-6 w-2/3 animate-pulse rounded bg-neutral-200"></div>
				<div class="space-y-2">
					<div class="h-4 animate-pulse rounded bg-neutral-100"></div>
					<div class="h-4 w-5/6 animate-pulse rounded bg-neutral-100"></div>
				</div>
			</div>
		{:else}
			<!-- Text/title skeleton -->
			<div
				class="animate-pulse rounded {heightClass} {variant === 'title' ? 'bg-neutral-200' : 'bg-neutral-100'}"
			></div>
		{/if}
	{/each}
</div>

<style>
	/* Smooth pulse animation */
	:global(.animate-pulse) {
		animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
	}
</style>
