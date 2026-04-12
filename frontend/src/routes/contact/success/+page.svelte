<script lang="ts">
	import PublicPageShell from '$lib/components/shared/PublicPageShell.svelte';
</script>

<svelte:head>
	<title>Message sent - Meno</title>
	<meta name="description" content="Your message has been received." />
</svelte:head>

<PublicPageShell>
	<h1 class="mb-4 text-3xl font-bold tracking-tight text-neutral-800">Message sent</h1>
	<p class="mb-8 text-base leading-relaxed text-neutral-600">
		Thanks for reaching out. I'll get back to you as soon as I can.
	</p>
	<a
		href="/"
		class="inline-block rounded-md border border-neutral-300 px-4 py-2 text-sm font-semibold text-neutral-700 transition-colors hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2"
	>
		Back to home
	</a>
</PublicPageShell>
