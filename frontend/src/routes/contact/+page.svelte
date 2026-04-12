<script lang="ts">
	import logo from '$lib/assets/logo.png';
</script>

<svelte:head>
	<title>Contact - Meno</title>
	<meta name="description" content="Get in touch with Meno." />
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
			<h1 class="mb-3 text-3xl font-bold tracking-tight text-neutral-800">Contact</h1>
			<p class="mb-10 text-base leading-relaxed text-neutral-500">
				Have a question or want to get in touch? Send a message and I'll get back to you.
			</p>

			<form
				method="POST"
				action="https://formspree.io/f/xlgarrdl"
				class="space-y-5"
			>
				<input type="hidden" name="_replyto" value="helenalucia@fastmail.com" />
				<input type="hidden" name="_next" value="/" />

				<div>
					<label for="name" class="mb-1 block text-sm font-medium text-neutral-700">Name</label>
					<input
						type="text"
						id="name"
						name="name"
						required
						class="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none"
						placeholder="Your name"
					/>
				</div>

				<div>
					<label for="email" class="mb-1 block text-sm font-medium text-neutral-700">Email</label>
					<input
						type="email"
						id="email"
						name="email"
						required
						class="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none"
						placeholder="you@example.com"
					/>
				</div>

				<div>
					<label for="message" class="mb-1 block text-sm font-medium text-neutral-700"
						>Message</label
					>
					<textarea
						id="message"
						name="message"
						required
						rows={5}
						class="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none"
						placeholder="Your message"
					></textarea>
				</div>

				<button
					type="submit"
					class="rounded-md bg-primary-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
				>
					Send message
				</button>
			</form>
		</div>
	</div>
</div>
