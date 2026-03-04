<script lang="ts">
	/**
	 * Input Component
	 *
	 * Flexible input field component supporting text, email, password, number, and other types.
	 * Also supports file upload input.
	 * Includes focus styles, error states, and disabled states.
	 *
	 * @component
	 * @example
	 * ```svelte
	 * <Input type="text" placeholder="Enter text..." bind:value={inputValue} />
	 * <Input type="email" bind:value={email} />
	 * <Input type="password" bind:value={password} />
	 * <Input type="number" min="0" max="100" bind:value={age} />
	 * <Input type="file" bind:files />
	 * <Input disabled placeholder="Disabled input..." />
	 * <Input aria-invalid={hasError} aria-describedby="error-msg" />
	 * ```
	 *
	 * @prop {string} [type="text"] - Input type (text, email, password, number, url, tel, date, etc.)
	 * @prop {*} [value] - Input value (bindable)
	 * @prop {FileList} [files] - File list for file input (bindable)
	 * @prop {string} [placeholder] - Placeholder text
	 * @prop {boolean} [disabled] - Whether input is disabled
	 * @prop {string} [class] - Additional CSS classes
	 * @prop {HTMLInputElement} [ref] - Reference to DOM element (bindable)
	 *
	 * @accessibility
	 * - Use with <Label> component for proper form association
	 * - aria-invalid for validation errors
	 * - aria-describedby to link to error messages
	 * - Focus indicator always visible
	 * - Error state indicated by red ring when aria-invalid="true"
	 */

	import type { HTMLInputAttributes, HTMLInputTypeAttribute } from "svelte/elements";
	import { cn, type WithElementRef } from "$lib/utils.js";

	type InputType = Exclude<HTMLInputTypeAttribute, "file">;

	type Props = WithElementRef<
		Omit<HTMLInputAttributes, "type"> &
			({ type: "file"; files?: FileList } | { type?: InputType; files?: undefined })
	>;

	let {
		ref = $bindable(null),
		value = $bindable(),
		type,
		files = $bindable(),
		class: className,
		"data-slot": dataSlot = "input",
		...restProps
	}: Props = $props();
</script>

{#if type === "file"}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		class={cn(
			"selection:bg-primary dark:bg-input/30 selection:text-primary-foreground border-input ring-offset-background placeholder:text-muted-foreground flex h-9 w-full min-w-0 rounded-md border bg-transparent px-3 pt-1.5 text-sm font-medium shadow-xs transition-[color,box-shadow] outline-none disabled:cursor-not-allowed disabled:opacity-50",
			"focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
			"aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
			className
		)}
		type="file"
		bind:files
		bind:value
		{...restProps}
	/>
{:else}
	<input
		bind:this={ref}
		data-slot={dataSlot}
		class={cn(
			"border-input bg-background selection:bg-primary dark:bg-input/30 selection:text-primary-foreground ring-offset-background placeholder:text-muted-foreground flex h-9 w-full min-w-0 rounded-md border px-3 py-1 text-base shadow-xs transition-[color,box-shadow] outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
			"focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
			"aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
			className
		)}
		{type}
		bind:value
		{...restProps}
	/>
{/if}
