<script lang="ts">
	import type { Snippet } from 'svelte';
	import logo from '$lib/assets/logo.png';

	let { children }: { children: Snippet } = $props();
</script>

<div class="min-h-screen bg-white">
	<header class="border-b border-neutral-200 px-6 py-4">
		<div class="mx-auto flex max-w-3xl items-center justify-between">
			<a href="/" class="flex items-center gap-2.5">
				<img src={logo} alt="" class="h-8 w-8 rounded-lg" aria-hidden="true" />
				<span class="text-xl font-bold tracking-tight text-neutral-800">Meno</span>
			</a>
			<a
				href="/"
				class="text-sm font-medium text-neutral-500 transition-colors hover:text-neutral-700"
			>
				&larr; Back <span class="sr-only">to home</span>
			</a>
		</div>
	</header>

	<div class="mx-auto max-w-3xl px-6 py-16">
		<div class="max-w-[65ch]">
			{@render children()}
		</div>
	</div>
</div>
