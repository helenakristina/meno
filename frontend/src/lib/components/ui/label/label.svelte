<script lang="ts">
	/**
	 * Label Component
	 *
	 * Form label element with semantic HTML and proper styling.
	 * Should be paired with form inputs using for/id attributes.
	 * Handles disabled and error states visually.
	 *
	 * @component
	 * @example
	 * ```svelte
	 * <Label for="email">Email Address</Label>
	 * <Input id="email" type="email" bind:value={email} />
	 *
	 * <Label for="password" class="text-red-600">Password (required)</Label>
	 * <Input id="password" type="password" bind:value={password} aria-invalid={hasError} />
	 * ```
	 *
	 * @prop {string} [for] - ID of associated form element
	 * @prop {string} [class] - Additional CSS classes
	 * @prop {HTMLLabelElement} [ref] - Reference to DOM element (bindable)
	 *
	 * @accessibility
	 * - Use for/id to associate with form inputs
	 * - Ensures screen readers announce label with input
	 * - Clicking label focuses associated input
	 * - Works with disabled form controls
	 */

	import { Label as LabelPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';

	let {
		ref = $bindable(null),
		class: className,
		...restProps
	}: LabelPrimitive.RootProps = $props();
</script>

<LabelPrimitive.Root
	bind:ref
	data-slot="label"
	class={cn(
		'flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
		className
	)}
	{...restProps}
/>
