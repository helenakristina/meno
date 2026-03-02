<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { user } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase/client';
	import { Menu, X } from '@lucide/svelte';

	let { children }: { children: Snippet } = $props();
	let loading = $state(true);
	let mobileMenuOpen = $state(false);

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

	function closeMenu() {
		mobileMenuOpen = false;
	}

	const navLinks = [
		{ href: '/dashboard', label: 'Dashboard' },
		{ href: '/log', label: 'Log Symptoms' },
		{ href: '/ask', label: 'Ask Meno' },
		{ href: '/providers', label: 'Providers' },
		{ href: '/export', label: 'Export' }
	];
</script>

{#if loading}
	<div class="flex min-h-screen items-center justify-center bg-slate-50">
		<div class="text-slate-600">Loading...</div>
	</div>
{:else}
	<div class="min-h-screen bg-slate-50">
		<!-- Mobile menu backdrop -->
		{#if mobileMenuOpen}
			<div
				class="fixed inset-0 z-40 bg-black/30"
				onclick={closeMenu}
			></div>

			<!-- Mobile sidebar menu (only rendered when open) -->
			<div
				class="fixed left-0 top-0 z-50 h-full w-64 transform bg-white shadow-lg transition-transform duration-300"
			>
			<!-- Close button -->
			<div class="flex items-center justify-between border-b border-slate-200 p-4">
				<a href="/dashboard" class="text-xl font-bold text-slate-900">Meno</a>
				<button
					onclick={closeMenu}
					class="text-slate-600 hover:text-slate-900"
					aria-label="Close menu"
				>
					<X size={24} />
				</button>
			</div>

			<!-- Mobile nav links (stacked) -->
			<nav class="flex flex-col gap-1 p-4">
				{#each navLinks as link}
					<a
						href={link.href}
						aria-current={page.url.pathname === link.href ? 'page' : undefined}
						onclick={closeMenu}
						class="rounded-md px-4 py-3 text-base font-medium {page.url.pathname === link.href
							? 'bg-slate-100 text-slate-900'
							: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
					>
						{link.label}
					</a>
				{/each}
			</nav>

				<!-- Mobile logout button -->
				{#if $user}
					<div class="border-t border-slate-200 p-4">
						<div class="mb-4 text-sm text-slate-600 break-all">{$user.email}</div>
						<button
							onclick={() => {
								closeMenu();
								handleLogout();
							}}
							class="w-full rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
						>
							Logout
						</button>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Desktop nav -->
		<nav class="border-b border-slate-200 bg-white">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-10">
						<a href="/dashboard" class="text-xl font-bold text-slate-900">Meno</a>

						<!-- Desktop nav links (hidden on mobile) -->
						<div class="hidden gap-1 md:flex">
							{#each navLinks as link}
								<a
									href={link.href}
									aria-current={page.url.pathname === link.href ? 'page' : undefined}
									class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === link.href
										? 'bg-slate-100 text-slate-900'
										: 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'}"
								>
									{link.label}
								</a>
							{/each}
						</div>
					</div>

					<!-- Desktop right side: user + logout + mobile hamburger -->
					<div class="flex items-center gap-4">
						{#if $user}
							<span class="hidden text-sm text-slate-600 sm:inline">{$user.email}</span>
						{/if}

						<!-- Mobile hamburger button (hidden on md and up) -->
						<button
							onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
							class="flex h-11 w-11 items-center justify-center rounded md:hidden text-slate-600 hover:text-slate-900"
							aria-label="Toggle menu"
							aria-expanded={mobileMenuOpen}
							aria-controls="mobile-menu"
						>
							<Menu size={24} />
						</button>

						<!-- Desktop logout button (hidden on mobile) -->
						{#if $user}
							<button
								onclick={handleLogout}
								class="hidden rounded-md px-3 py-3 text-sm font-medium text-slate-700 hover:bg-slate-100 sm:inline"
							>
								Logout
							</button>
						{/if}
					</div>
				</div>
			</div>
		</nav>

		<main class="w-full max-w-full overflow-hidden px-4 py-6 sm:px-6 lg:px-8">
			{@render children()}
		</main>
	</div>
{/if}
