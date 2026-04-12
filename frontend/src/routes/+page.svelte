<script lang="ts">
	import logo from '$lib/assets/logo.png';
</script>

<svelte:head>
	<title>Meno: Perimenopause and Menopause Support</title>
	<meta
		name="description"
		content="Find a specialist who knows menopause, track your symptoms, and walk into every appointment knowing exactly what to say."
	/>
</svelte:head>

<!-- ======================================================================
     Navigation
     ====================================================================== -->
<header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/90 backdrop-blur-sm">
	<div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
		<div class="flex items-center gap-2.5">
			<img src={logo} alt="" class="h-8 w-8 rounded-lg" aria-hidden="true" />
			<span class="text-xl font-bold tracking-tight text-neutral-800">Meno</span>
		</div>
		<a
			href="/login"
			class="rounded-md border border-neutral-300 px-4 py-2 text-sm font-semibold text-neutral-700 transition-colors hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
		>
			Sign in
		</a>
	</div>
</header>

<!-- ======================================================================
     Hero
     ====================================================================== -->
<section class="px-6 py-24 sm:py-32">
	<div class="mx-auto max-w-3xl text-center">
		<p class="mb-5 text-xs font-semibold tracking-widest text-primary-500 uppercase">
			Perimenopause and menopause support
		</p>

		<h1 class="text-4xl leading-tight font-bold tracking-tight text-neutral-800 sm:text-5xl">
			Your doctor has ten minutes.<br />
			<span class="text-primary-500">Make them count.</span>
		</h1>

		<p class="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-neutral-500">
			Find a specialist who knows menopause, track your symptoms, and walk into every appointment
			knowing exactly what to say.
		</p>

		<div class="mt-8 flex flex-wrap items-center justify-center gap-3">
			<span
				class="rounded-full border border-neutral-200 bg-white px-4 py-1.5 text-sm text-neutral-500"
			>
				Currently in private beta
			</span>
		</div>

		<p class="mt-6 text-sm text-neutral-400">
			Private by design. Your data is yours, never sold, never shared.
		</p>
	</div>
</section>

<!-- ======================================================================
     Feature cards
     ====================================================================== -->
<section class="px-6 py-16">
	<div class="mx-auto max-w-3xl">
		<div class="grid gap-6 sm:grid-cols-2">
			<!-- Ask Meno -->
			<div class="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-5 w-5 text-primary-500"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-neutral-800">Ask Meno</h3>
				<p class="text-sm leading-relaxed text-neutral-500">
					Evidence-based answers to the questions your doctor didn't have time for. Sourced from
					peer-reviewed research, cited at the paragraph level.
				</p>
			</div>

			<!-- Appointment prep -->
			<div class="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-5 w-5 text-primary-500"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-neutral-800">Appointment prep</h3>
				<p class="text-sm leading-relaxed text-neutral-500">
					Walk in with a provider summary written in your words, your concerns prioritized, and
					evidence-based responses ready if things go sideways.
				</p>
			</div>

			<!-- Symptom tracking -->
			<div class="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-5 w-5 text-primary-500"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 12h2.25l2.25-6 3 12 3-9 2.25 6H21"
						/>
					</svg>
				</div>
				<h3 class="mb-2 font-semibold text-neutral-800">Symptom tracking</h3>
				<p class="text-sm leading-relaxed text-neutral-500">
					Log how you feel each day and watch patterns emerge over time. Your experience is real and
					worth understanding.
				</p>
			</div>

			<!-- Provider finder -->
			<div class="rounded-2xl border border-neutral-200 bg-white p-6 shadow-sm">
				<div
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-primary-50"
					aria-hidden="true"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="h-5 w-5 text-primary-500"
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
				<h3 class="mb-2 font-semibold text-neutral-800">Provider finder</h3>
				<p class="text-sm leading-relaxed text-neutral-500">
					Search NAMS-certified menopause specialists by state, provider type, and insurance. Track
					who you've called, who called back, and who you've booked.
				</p>
			</div>
		</div>
	</div>
</section>

<!-- ======================================================================
     Pullquote
     ====================================================================== -->
<section class="bg-neutral-50 px-6 py-20">
	<div class="mx-auto max-w-2xl">
		<blockquote>
			<p class="text-lg leading-relaxed text-neutral-700">
				"One appointment with someone who actually knew menopause changed everything. Most women
				don't know they can navigate around a system that isn't working for them. That's what Meno
				is for."
			</p>
			<footer class="mt-6 text-sm text-neutral-400">
				<a
					href="https://helena-lucia.vercel.app/meno"
					target="_blank"
					rel="noopener noreferrer"
					class="underline underline-offset-2 transition-colors hover:text-neutral-600"
				>
					Helena Lucia, founder and developer.
				</a>
			</footer>
		</blockquote>
	</div>
</section>

<!-- ======================================================================
     CTA
     ====================================================================== -->
<section class="px-6 py-24">
	<div class="mx-auto max-w-2xl text-center">
		<span
			class="inline-block rounded-full bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-600"
		>
			Private beta
		</span>
		<h2 class="mt-5 text-3xl font-bold tracking-tight text-neutral-800">
			Your symptoms deserve to be understood.
		</h2>
		<p class="mt-4 text-neutral-500">Meno is currently available to invited users only.</p>
		<a
			href="/login"
			class="mt-8 inline-block rounded-xl bg-primary-500 px-8 py-3.5 text-base font-semibold text-white shadow-sm transition-colors hover:bg-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
		>
			Sign in to your account
		</a>
	</div>
</section>

<!-- ======================================================================
     Disclaimer
     ====================================================================== -->
<section class="border-t border-neutral-100 bg-neutral-50 px-6 py-16">
	<div class="mx-auto max-w-2xl text-center">
		<p class="mb-3 text-xs font-semibold tracking-widest text-neutral-400 uppercase">
			A note about Meno
		</p>
		<p class="text-sm leading-relaxed text-neutral-500">
			Meno provides educational information and symptom tracking. It is not a medical tool and
			cannot diagnose conditions or replace the advice of a healthcare provider. All information is
			sourced from peer-reviewed research and reputable medical organizations. Meno is designed to
			help you have more informed conversations with your doctor, not to replace them.
		</p>
	</div>
</section>

<!-- ======================================================================
     Footer
     ====================================================================== -->
<footer class="border-t border-neutral-100 bg-white px-6 py-10">
	<div class="mx-auto flex max-w-5xl flex-col items-center gap-4 sm:flex-row sm:justify-between">
		<span class="text-sm font-bold tracking-tight text-neutral-800">Meno</span>

		<nav aria-label="Footer navigation">
			<ul class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-neutral-400">
				<li><a href="/about" class="transition-colors hover:text-neutral-600">About</a></li>
				<li><a href="/privacy" class="transition-colors hover:text-neutral-600">Privacy</a></li>
				<li><a href="/contact" class="transition-colors hover:text-neutral-600">Contact</a></li>
			</ul>
		</nav>

		<p class="text-xs text-neutral-300">
			&copy; {new Date().getFullYear()} Meno. All rights reserved.
		</p>
	</div>
</footer>
