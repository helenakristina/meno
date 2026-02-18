<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { user } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase/client';

	let { children }: { children: Snippet } = $props();
	let loading = $state(true);

	// Check initial auth state
	$effect(() => {
		supabase.auth.getSession().then(() => {
			loading = false;
		});
	});

	// Redirect to login if not authenticated (after loading completes)
	$effect(() => {
		if (!loading && !$user) {
			goto('/login');
		}
	});

	async function handleLogout() {
		await supabase.auth.signOut();
		goto('/login');
	}
</script>

{#if loading}
	<div class="flex min-h-screen items-center justify-center bg-slate-50">
		<div class="text-slate-600">Loading...</div>
	</div>
{:else}
	<div class="min-h-screen bg-slate-50">
		<nav class="border-b border-slate-200 bg-white">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-10">
						<a href="/dashboard" class="text-xl font-bold text-slate-900">Meno</a>
						<div class="flex gap-1">
							<a
								href="/dashboard"
								class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === '/dashboard'
									? 'bg-slate-100 text-slate-900'
									: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
							>
								Dashboard
							</a>
							<a
								href="/log"
								class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === '/log'
									? 'bg-slate-100 text-slate-900'
									: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
							>
								Log Symptoms
							</a>
							<a
								href="/ask"
								class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === '/ask'
									? 'bg-slate-100 text-slate-900'
									: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
							>
								Ask Meno
							</a>
							<a
								href="/providers"
								class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === '/providers'
									? 'bg-slate-100 text-slate-900'
									: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
							>
								Providers
							</a>
							<a
								href="/export"
								class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === '/export'
									? 'bg-slate-100 text-slate-900'
									: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
							>
								Export
							</a>
						</div>
					</div>
					<div class="flex items-center gap-4">
						{#if $user}
							<span class="text-sm text-slate-600">{$user.email}</span>
							<button
								onclick={handleLogout}
								class="rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
							>
								Logout
							</button>
						{/if}
					</div>
				</div>
			</div>
		</nav>
		<main class="mx-auto max-w-7xl py-6 sm:px-6 lg:px-8">
			{@render children()}
		</main>
	</div>
{/if}
