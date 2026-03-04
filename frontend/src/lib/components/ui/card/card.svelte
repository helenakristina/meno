<script lang="ts">
	/**
	 * Card Component
	 *
	 * Container for card-based layouts with rounded corners, border, and shadow.
	 * Typically used with CardHeader, CardTitle, CardDescription, CardContent, and CardFooter.
	 * Provides consistent spacing and styling for grouped content.
	 *
	 * @component
	 * @example
	 * ```svelte
	 * <Card>
	 *   <CardHeader>
	 *     <CardTitle>Card Title</CardTitle>
	 *     <CardDescription>Subtitle or description</CardDescription>
	 *   </CardHeader>
	 *   <CardContent>Main card content</CardContent>
	 *   <CardFooter>
	 *     <Button>Action</Button>
	 *   </CardFooter>
	 * </Card>
	 * ```
	 *
	 * @prop {HTMLDivElement} [ref] - Reference to DOM element (bindable)
	 * @prop {string} [class] - Additional CSS classes to override defaults
	 *
	 * @accessibility
	 * - Semantic div with card styling
	 * - Use CardHeader with CardTitle for proper heading hierarchy
	 * - All interactive content should be buttons or links
	 */

	import type { HTMLAttributes } from "svelte/elements";
	import { cn, type WithElementRef } from "$lib/utils.js";

	let {
		ref = $bindable(null),
		class: className,
		children,
		...restProps
	}: WithElementRef<HTMLAttributes<HTMLDivElement>> = $props();
</script>

<div
	bind:this={ref}
	data-slot="card"
	class={cn(
		"bg-card text-card-foreground flex flex-col gap-6 rounded-xl border py-6 shadow-sm",
		className
	)}
	{...restProps}
>
	{@render children?.()}
</div>
