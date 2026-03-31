<script lang="ts" module>
	/**
	 * Button Component
	 *
	 * Reusable button component with multiple variants and sizes.
	 * Can render as <button> or <a> element depending on href prop.
	 * Fully accessible with proper ARIA attributes and keyboard support.
	 *
	 * @component
	 * @example
	 * ```svelte
	 * <Button onclick={handleClick}>Click me</Button>
	 * <Button variant="outline" size="sm">Small outline button</Button>
	 * <Button href="/path" variant="link">Link button</Button>
	 * <Button disabled>Disabled button</Button>
	 * ```
	 *
	 * Variants:
	 * - 'default' - Primary button with background color
	 * - 'destructive' - Red/danger button for destructive actions
	 * - 'outline' - Outlined button with border
	 * - 'secondary' - Secondary button
	 * - 'ghost' - Minimal button with hover effect only
	 * - 'link' - Text link style button
	 *
	 * Sizes:
	 * - 'default' - Standard button height (h-9)
	 * - 'sm' - Small button (h-8)
	 * - 'lg' - Large button (h-10)
	 * - 'icon' - Icon button (square, size 36px)
	 * - 'icon-sm' - Small icon button (size 32px)
	 * - 'icon-lg' - Large icon button (size 40px)
	 *
	 * @accessibility
	 * - Supports disabled state with aria-disabled
	 * - When disabled and href provided, link is not clickable
	 * - Keyboard focus visible with ring indicator
	 * - Icon buttons should include aria-label prop
	 */

	import { cn, type WithElementRef } from '$lib/utils.js';
	import type { HTMLAnchorAttributes, HTMLButtonAttributes } from 'svelte/elements';
	import { type VariantProps, tv } from 'tailwind-variants';

	export const buttonVariants = tv({
		base: "focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive inline-flex shrink-0 items-center justify-center gap-2 rounded-md text-sm font-medium whitespace-nowrap transition-all outline-none focus-visible:ring-[3px] disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
		variants: {
			variant: {
				default: 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs',
				destructive:
					'bg-destructive hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60 text-white shadow-xs',
				outline:
					'bg-background hover:bg-accent hover:text-accent-foreground dark:bg-input/30 dark:border-input dark:hover:bg-input/50 border shadow-xs',
				secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80 shadow-xs',
				ghost: 'hover:bg-accent hover:text-accent-foreground dark:hover:bg-accent/50',
				link: 'text-primary underline-offset-4 hover:underline'
			},
			size: {
				default: 'h-9 px-4 py-2 has-[>svg]:px-3',
				sm: 'h-8 gap-1.5 rounded-md px-3 has-[>svg]:px-2.5',
				lg: 'h-10 rounded-md px-6 has-[>svg]:px-4',
				icon: 'size-9',
				'icon-sm': 'size-8',
				'icon-lg': 'size-10'
			}
		},
		defaultVariants: {
			variant: 'default',
			size: 'default'
		}
	});

	export type ButtonVariant = VariantProps<typeof buttonVariants>['variant'];
	export type ButtonSize = VariantProps<typeof buttonVariants>['size'];

	export type ButtonProps = WithElementRef<HTMLButtonAttributes> &
		WithElementRef<HTMLAnchorAttributes> & {
			variant?: ButtonVariant;
			size?: ButtonSize;
		};
</script>

<script lang="ts">
	let {
		class: className,
		variant = 'default',
		size = 'default',
		ref = $bindable(null),
		href = undefined,
		type = 'button',
		disabled,
		children,
		...restProps
	}: ButtonProps = $props();
</script>

{#if href}
	<a
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		href={disabled ? undefined : href}
		aria-disabled={disabled}
		role={disabled ? 'link' : undefined}
		tabindex={disabled ? -1 : undefined}
		{...restProps}
	>
		{@render children?.()}
	</a>
{:else}
	<button
		bind:this={ref}
		data-slot="button"
		class={cn(buttonVariants({ variant, size }), className)}
		{type}
		{disabled}
		{...restProps}
	>
		{@render children?.()}
	</button>
{/if}
