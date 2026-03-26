<script lang="ts">
	import { supabase } from '$lib/supabase/client';
	import { goto } from '$app/navigation';

	let email = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');

	async function handleLogin() {
		loading = true;
		error = '';

		const { data, error: authError } = await supabase.auth.signInWithPassword({
			email,
			password
		});

		loading = false;

		if (authError) {
			error = authError.message;
		} else {
			// Success! Redirect to dashboard
			goto('/dashboard');
		}
	}

	async function handleSignup() {
		loading = true;
		error = '';

		const { data, error: authError } = await supabase.auth.signUp({
			email,
			password
		});

		loading = false;

		if (authError) {
			error = authError.message;
		} else {
			// Success! Redirect to onboarding
			goto('/onboarding');
		}
	}
</script>

<div class="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
	<div class="w-full max-w-md">
		<div class="mb-8 text-center">
			<h1 class="text-3xl font-bold text-neutral-800">Welcome to Meno</h1>
			<p class="mt-2 text-neutral-600">Sign in or create an account</p>
		</div>

		<div class="rounded-lg border border-neutral-200 bg-white p-8 shadow-sm">
			<form class="space-y-4" onsubmit={(e) => { e.preventDefault(); handleLogin(); }}>
				<div>
					<label for="email" class="mb-1 block text-sm font-medium text-neutral-700"> Email </label>
					<input
						type="email"
						id="email"
						bind:value={email}
						required
						class="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none"
						placeholder="you@example.com"
					/>
				</div>

				<div>
					<label for="password" class="mb-1 block text-sm font-medium text-neutral-700">
						Password
					</label>
					<input
						type="password"
						id="password"
						bind:value={password}
						required
						minlength="6"
						class="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 focus:outline-none"
						placeholder="••••••••"
					/>
				</div>

				{#if error}
					<div class="rounded-md border border-danger-light bg-danger-light px-4 py-3 text-sm text-danger-dark">
						{error}
					</div>
				{/if}

				<div class="flex gap-3">
					<button
						type="submit"
						disabled={loading}
						class="flex-1 rounded-md bg-primary-500 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-600 disabled:cursor-not-allowed disabled:bg-neutral-300"
					>
						{loading ? 'Loading...' : 'Sign In'}
					</button>
					<button
						type="button"
						onclick={handleSignup}
						disabled={loading}
						class="flex-1 rounded-md border border-neutral-300 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:bg-neutral-100"
					>
						Sign Up
					</button>
				</div>
			</form>
		</div>
	</div>
</div>
