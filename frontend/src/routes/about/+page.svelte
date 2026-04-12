<script lang="ts">
	import PublicPageShell from '$lib/components/shared/PublicPageShell.svelte';
</script>

<svelte:head>
	<title>About - Meno</title>
	<meta name="description" content="Why Helena Lucia built Meno, and what it is for." />
</svelte:head>

<PublicPageShell>
	<h1 class="mb-10 text-3xl font-bold tracking-tight text-neutral-800">About Meno</h1>

	<div class="space-y-6 text-base leading-relaxed text-neutral-600">
		<p>I built Meno because I needed it.</p>

		<p>
			I walked into a doctor's appointment prepared. I had done the research, written the email,
			gotten a yes. My doctor would discuss hormone therapy. She had never prescribed an estrogen
			patch. She offered birth control instead. When I asked about vaginal estrogen, she suggested
			lube. I left without the care I came for, found a NAMS-certified menopause specialist
			myself, and scheduled directly. Within a month of seeing someone who actually knew
			menopause, my sleep was better, my hot flashes were easing, and my bladder was improving.
		</p>

		<p>
			One appointment with the right provider changed everything. Most women don't know they can
			do that, or don't have the energy to try.
		</p>

		<p>
			I'm a software engineer. Before that appointment I spent hours researching the evidence,
			logging my symptoms, and preparing a document: prioritized concerns, scripted opening
			statement, questions grouped by topic. I walked in knowing exactly what to ask for and why.
			It worked. But I had time, research skills, and the stubbornness to navigate around a
			system that wasn't working for me. Most women don't have that combination.
		</p>

		<p>
			Meno is what I wished had existed. A place to track your symptoms, find a provider who
			actually knows this transition, and walk into every appointment prepared. The full story of
			why I built it, and how, is on the
			<a
				href="https://helena-lucia.vercel.app/meno"
				target="_blank"
				rel="noopener noreferrer"
				class="text-primary-600 underline underline-offset-2 hover:text-primary-700"
			>Meno case study<span class="sr-only"> (opens in new tab)</span></a>.
		</p>
	</div>
</PublicPageShell>
