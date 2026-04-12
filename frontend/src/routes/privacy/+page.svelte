<script lang="ts">
	import logo from '$lib/assets/logo.png';
</script>

<svelte:head>
	<title>Privacy - Meno</title>
	<meta name="description" content="How Meno handles your data." />
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
			<h1 class="mb-10 text-3xl font-bold tracking-tight text-neutral-800">Privacy Policy</h1>

			<div class="space-y-8 text-base leading-relaxed text-neutral-600">

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">What Meno collects</h2>
					<p>
						The information you enter: symptoms, cycle data, medications, and appointment notes.
						Your email address for authentication. Nothing else.
					</p>
				</section>

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">How it's stored</h2>
					<p>
						Your data is stored in a secure database with row-level security, meaning no other user
						can access your data. Authentication is handled by Supabase.
					</p>
				</section>

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">What Meno does not do</h2>
					<p>
						Meno does not sell your data. Meno does not share your data with third parties. Meno
						does not use third-party analytics.
					</p>
				</section>

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">AI and your data</h2>
					<p>
						Meno uses an AI model in two places: to answer questions in Ask Meno, and to generate
						content in the appointment prep flow. In both cases, requests are sent to an external
						API. Your name, email address, and user ID are never included in those requests. User
						IDs are hashed in application logs. No personally identifiable information leaves Meno's
						systems.
					</p>
				</section>

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">Research</h2>
					<p>
						Meno does not currently share data with any third parties. Any future research
						partnerships would require explicit opt-in consent from you and would involve only
						anonymized data.
					</p>
				</section>

				<section>
					<h2 class="mb-2 font-semibold text-neutral-800">Contact</h2>
					<p>
						Questions about privacy? Reach out via the
						<a
							href="/contact"
							class="text-primary-600 underline underline-offset-2 hover:text-primary-700"
						>contact page</a>.
					</p>
				</section>

			</div>
		</div>
	</div>
</div>
