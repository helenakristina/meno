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

<div class="flex min-h-screen items-center justify-center bg-slate-50 px-4">
	<div class="w-full max-w-md">
		<div class="mb-8 text-center">
			<h1 class="text-3xl font-bold text-slate-900">Welcome to Meno</h1>
			<p class="mt-2 text-slate-600">Sign in or create an account</p>
		</div>

		<div class="rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
			<form class="space-y-4" on:submit|preventDefault={handleLogin}>
				<div>
					<label for="email" class="mb-1 block text-sm font-medium text-slate-700"> Email </label>
					<input
						type="email"
						id="email"
						bind:value={email}
						required
						class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none"
						placeholder="you@example.com"
					/>
				</div>

				<div>
					<label for="password" class="mb-1 block text-sm font-medium text-slate-700">
						Password
					</label>
					<input
						type="password"
						id="password"
						bind:value={password}
						required
						minlength="6"
						class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:ring-1 focus:ring-slate-500 focus:outline-none"
						placeholder="••••••••"
					/>
				</div>

				{#if error}
					<div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
						{error}
					</div>
				{/if}

				<div class="flex gap-3">
					<button
						type="submit"
						disabled={loading}
						class="flex-1 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
					>
						{loading ? 'Loading...' : 'Sign In'}
					</button>
					<button
						type="button"
						on:click={handleSignup}
						disabled={loading}
						class="flex-1 rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
					>
						Sign Up
					</button>
				</div>
			</form>
		</div>
	</div>
</div>
