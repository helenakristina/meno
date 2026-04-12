<script lang="ts">
	import logo from '$lib/assets/logo.png';
</script>

<svelte:head>
	<title>About - Meno</title>
	<meta name="description" content="Why Helena Lucia built Meno, and what it is for." />
</svelte:head>

<div class="min-h-screen bg-white">
	<!-- Nav -->
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
				&larr; Back
			</a>
		</div>
	</header>

	<!-- Content -->
	<div class="mx-auto max-w-3xl px-6 py-16">
		<div class="max-w-[65ch]">
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
					>Meno case study</a>.
				</p>
			</div>
		</div>
	</div>
</div>
