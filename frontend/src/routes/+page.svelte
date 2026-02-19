<script lang="ts">
	function scrollToFeatures(e: MouseEvent) {
		e.preventDefault();
		document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
	}
</script>

<svelte:head>
	<title>Meno — Understand Your Perimenopause and Menopause Symptoms</title>
	<meta
		name="description"
		content="Meno helps you track symptoms, discover patterns, and prepare for healthcare conversations with evidence-based insights."
	/>
</svelte:head>

<!-- ======================================================================
     Navigation
     ====================================================================== -->
<header class="sticky top-0 z-10 border-b border-slate-100 bg-white/90 backdrop-blur-sm">
	<div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
		<span class="text-xl font-bold tracking-tight text-teal-700">Meno</span>
		<a
			href="/login"
			class="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
		>
			Get Started
		</a>
	</div>
</header>

<!-- ======================================================================
     Hero
     ====================================================================== -->
<section
	class="relative overflow-hidden bg-gradient-to-b from-white via-teal-50/40 to-white px-6 py-24 sm:py-32"
>
	<!-- Subtle background accent -->
	<div
		class="pointer-events-none absolute -top-32 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-teal-100/50 blur-3xl"
		aria-hidden="true"
	></div>

	<div class="relative mx-auto max-w-3xl text-center">
		<p class="mb-4 text-sm font-medium uppercase tracking-widest text-teal-600">
			Symptom tracking &amp; pattern insight
		</p>

		<h1 class="text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
			Understand Your Perimenopause<br class="hidden sm:block" /> and Menopause Symptoms
		</h1>

		<p class="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
			Track symptoms, discover patterns, and prepare for healthcare conversations
			with evidence-based insights — all in one private, supportive space.
		</p>

		<div class="mt-10 flex flex-wrap items-center justify-center gap-4">
			<a
				href="/login"
				class="rounded-xl bg-teal-600 px-7 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
			>
				Get Started — it's free
			</a>
			<a
				href="#features"
				onclick={scrollToFeatures}
				class="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-7 py-3 text-base font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
			>
				Learn more
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="h-4 w-4"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M10 3a.75.75 0 01.75.75v10.638l3.96-4.158a.75.75 0 111.08 1.04l-5.25 5.5a.75.75 0 01-1.08 0l-5.25-5.5a.75.75 0 111.08-1.04l3.96 4.158V3.75A.75.75 0 0110 3z"
						clip-rule="evenodd"
					/>
				</svg>
			</a>
		</div>

		<!-- Social proof / reassurance line -->
		<p class="mt-10 text-sm text-slate-400">
			Private by design. Your data is yours — never sold, never shared.
		</p>
	</div>
</section>

<!-- ======================================================================
     Features
     ====================================================================== -->
<section id="features" class="px-6 py-24">
	<div class="mx-auto max-w-5xl">
		<div class="mb-16 text-center">
			<h2 class="text-3xl font-bold tracking-tight text-slate-900">
				Everything you need, nothing you don't
			</h2>
			<p class="mt-4 text-slate-500">
				Simple tools designed around what matters most during this transition.
			</p>
		</div>

		<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
			<!-- Feature 1: Track -->
			<div class="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-6 w-6 text-teal-600"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Track Daily Symptoms</h3>
				<p class="text-sm leading-relaxed text-slate-500">
					Simple, intuitive logging. Record how you feel each day and watch your experience
					take shape over time.
				</p>
			</div>

			<!-- Feature 2: Patterns -->
			<div class="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-6 w-6 text-teal-600"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M7.5 14.25v2.25m3-4.5v4.5m3-6.75v6.75m3-9v9M6 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25z"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Discover Patterns</h3>
				<p class="text-sm leading-relaxed text-slate-500">
					See which symptoms occur together and how often. Your experience is real — these
					connections matter and are worth understanding.
				</p>
			</div>

			<!-- Feature 3: Evidence -->
			<div class="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-6 w-6 text-teal-600"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Evidence-Based Information</h3>
				<p class="text-sm leading-relaxed text-slate-500">
					All information sourced from current research and trusted medical organizations,
					cited throughout. No outdated advice, no guesswork.
				</p>
			</div>

			<!-- Feature 4: Providers -->
			<div class="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-teal-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-6 w-6 text-teal-600"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
						/>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Find the Right Provider</h3>
				<p class="text-sm leading-relaxed text-slate-500">
					Connect with healthcare providers who specialize in menopause care and will
					take your symptoms seriously.
				</p>
			</div>
		</div>
	</div>
</section>

<!-- ======================================================================
     How it works — brief three-step flow
     ====================================================================== -->
<section class="bg-teal-50/60 px-6 py-24">
	<div class="mx-auto max-w-3xl text-center">
		<h2 class="mb-16 text-3xl font-bold tracking-tight text-slate-900">
			From logging to understanding
		</h2>

		<div class="grid gap-10 sm:grid-cols-3">
			<div class="flex flex-col items-center">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-teal-600 text-sm font-bold text-white"
					aria-hidden="true"
				>
					1
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Log what you feel</h3>
				<p class="text-sm text-slate-500">
					Select from a curated symptom list or write in your own words — takes under a minute.
				</p>
			</div>

			<div class="flex flex-col items-center">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-teal-600 text-sm font-bold text-white"
					aria-hidden="true"
				>
					2
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">See the patterns</h3>
				<p class="text-sm text-slate-500">
					Your dashboard surfaces frequency trends and co-occurring symptoms automatically.
				</p>
			</div>

			<div class="flex flex-col items-center">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-teal-600 text-sm font-bold text-white"
					aria-hidden="true"
				>
					3
				</div>
				<h3 class="mb-2 font-semibold text-slate-900">Go to appointments informed</h3>
				<p class="text-sm text-slate-500">
					Bring concrete data and evidence-based questions to every healthcare conversation.
				</p>
			</div>
		</div>
	</div>
</section>

<!-- ======================================================================
     CTA band
     ====================================================================== -->
<section class="px-6 py-24">
	<div class="mx-auto max-w-2xl text-center">
		<h2 class="text-3xl font-bold tracking-tight text-slate-900">
			Your symptoms deserve to be understood.
		</h2>
		<p class="mt-4 text-lg text-slate-500">
			Start tracking today. It's free, private, and takes less than a minute to set up.
		</p>
		<a
			href="/login"
			class="mt-8 inline-block rounded-xl bg-teal-600 px-8 py-3.5 text-base font-semibold text-white shadow-sm transition-colors hover:bg-teal-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-400"
		>
			Create your free account
		</a>
	</div>
</section>

<!-- ======================================================================
     Disclaimer / Trust
     ====================================================================== -->
<section class="border-t border-slate-100 bg-slate-50 px-6 py-16">
	<div class="mx-auto max-w-2xl text-center">
		<p class="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
			A note about Meno
		</p>
		<p class="text-sm leading-relaxed text-slate-500">
			Meno provides educational information and symptom tracking. It is not a medical tool
			and cannot diagnose conditions or replace the advice of a healthcare provider.
			All information is sourced from peer-reviewed research and reputable medical
			organizations. Meno is designed to help you have more informed conversations
			with your doctor — not to replace them.
		</p>
	</div>
</section>

<!-- ======================================================================
     Footer
     ====================================================================== -->
<footer class="border-t border-slate-100 bg-white px-6 py-10">
	<div class="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
		<span class="text-sm font-semibold text-teal-700">Meno</span>

		<nav aria-label="Footer navigation">
			<ul class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-slate-400">
				<li><a href="/about" class="transition-colors hover:text-slate-600">About</a></li>
				<li><a href="/privacy" class="transition-colors hover:text-slate-600">Privacy</a></li>
				<li><a href="/contact" class="transition-colors hover:text-slate-600">Contact</a></li>
			</ul>
		</nav>

		<p class="text-xs text-slate-300">
			&copy; {new Date().getFullYear()} Meno. All rights reserved.
		</p>
	</div>
</footer>
