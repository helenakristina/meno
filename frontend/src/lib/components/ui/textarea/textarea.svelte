<script lang="ts">
	/**
	 * Textarea Component
	 *
	 * Multi-line text input field with auto-sizing and error states.
	 * Adjusts height based on content with CSS field-sizing.
	 * Includes focus styles and disabled states.
	 *
	 * @component
	 * @example
	 * ```svelte
	 * <Textarea placeholder="Enter your comments..." bind:value={comments} />
	 * <Textarea
	 *   rows="5"
	 *   maxlength="500"
	 *   aria-invalid={hasError}
	 *   aria-describedby="error-msg"
	 *   bind:value={description}
	 * />
	 * ```
	 *
	 * @prop {string} [value] - Textarea value (bindable)
	 * @prop {number} [rows] - Number of visible rows (default: auto-sized)
	 * @prop {number} [cols] - Number of visible columns
	 * @prop {number} [maxlength] - Maximum character count
	 * @prop {boolean} [disabled] - Whether textarea is disabled
	 * @prop {string} [placeholder] - Placeholder text
	 * @prop {string} [class] - Additional CSS classes
	 * @prop {HTMLTextAreaElement} [ref] - Reference to DOM element (bindable)
	 *
	 * @accessibility
	 * - Pair with <Label> using for/id
	 * - aria-invalid for validation errors
	 * - aria-describedby to link to error messages or help text
	 * - Character count announced with aria-live if implementing character limit UI
	 */

	import { cn, type WithElementRef, type WithoutChildren } from '$lib/utils.js';
	import type { HTMLTextareaAttributes } from 'svelte/elements';

	let {
		ref = $bindable(null),
		value = $bindable(),
		class: className,
		'data-slot': dataSlot = 'textarea',
		...restProps
	}: WithoutChildren<WithElementRef<HTMLTextareaAttributes>> = $props();
</script>

<textarea
	bind:this={ref}
	data-slot={dataSlot}
	class={cn(
		'flex field-sizing-content min-h-16 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-xs transition-[color,box-shadow] outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/20 md:text-sm dark:bg-input/30 dark:aria-invalid:ring-destructive/40',
		className
	)}
	bind:value
	{...restProps}
></textarea>
