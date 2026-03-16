<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { authState } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase/client';
	import { Menu, X, User } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';

	let { children }: { children: Snippet } = $props();
	let loading = $state(true);
	let mobileMenuOpen = $state(false);
	let profileMenuOpen = $state(false);
	let periodTrackingEnabled = $state(false);

	// Check initial auth state
	$effect(() => {
		supabase.auth.getSession().then(() => {
			loading = false;
		});
	});

	// Redirect to login if not authenticated (after loading completes)
	$effect(() => {
		if (!loading && !$authState.user) {
			goto('/login');
		}
	});

	// Load period tracking preference
	onMount(async () => {
		try {
			const settings = await apiClient.get('/api/users/settings');
			periodTrackingEnabled = settings.period_tracking_enabled;
		} catch {
			// Default to false if settings can't be loaded — period nav won't show
			periodTrackingEnabled = false;
		}
	});

	async function handleLogout() {
		await supabase.auth.signOut();
		goto('/login');
	}

	function closeMenu() {
		mobileMenuOpen = false;
	}

	function closeProfileMenu() {
		profileMenuOpen = false;
	}

	function getUserInitials(email: string | undefined): string {
		if (!email) return '?';
		return email.charAt(0).toUpperCase();
	}

	const baseNavLinks = [
		{ href: '/dashboard', label: 'Dashboard' },
		{ href: '/log', label: 'Log Symptoms' },
		{ href: '/ask', label: 'Ask Meno' },
		{ href: '/appointment-prep', label: 'Appt Prep' },
		{ href: '/providers', label: 'Providers' },
		{ href: '/export', label: 'Export' }
	];

	const navLinks = $derived([
		...baseNavLinks,
		...(periodTrackingEnabled ? [{ href: '/period', label: 'Cycles' }] : [])
	]);
</script>

<!-- Close profile menu when clicking outside -->
<svelte:window
	onclick={(e) => {
		const target = e.target as HTMLElement;
		if (!target.closest('[data-profile-menu]')) {
			profileMenuOpen = false;
		}
	}}
/>

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

			<!-- Mobile user area -->
			{#if $authState.user}
				<div class="border-t border-slate-200 p-4">
					<div class="mb-3 text-sm text-slate-600 break-all">{$authState.user.email}</div>
					<a
						href="/settings"
						onclick={closeMenu}
						class="mb-2 block rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
					>
						Settings
					</a>
					<button
						onclick={() => {
							closeMenu();
							handleLogout();
						}}
						class="w-full rounded-md px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-100"
					>
						Log out
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

					<!-- Right side: profile menu + mobile hamburger -->
					<div class="flex items-center gap-2">
						<!-- Mobile hamburger button (hidden on md and up) -->
						<button
							onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
							class="flex h-11 w-11 items-center justify-center rounded md:hidden text-slate-600 hover:text-slate-900"
							aria-label="Toggle menu"
							aria-expanded={mobileMenuOpen}
						>
							<Menu size={24} />
						</button>

						<!-- Desktop profile/avatar menu (hidden on mobile) -->
						<div class="relative hidden md:block" data-profile-menu>
							<button
								onclick={(e) => {
									e.stopPropagation();
									profileMenuOpen = !profileMenuOpen;
								}}
								class="flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-1"
								aria-label="User menu"
								aria-expanded={profileMenuOpen}
								aria-haspopup="true"
							>
								{getUserInitials($authState.user?.email)}
							</button>

							{#if profileMenuOpen}
								<div
									class="absolute right-0 top-11 z-50 min-w-48 rounded-md border border-slate-200 bg-white py-1 shadow-lg"
									role="menu"
								>
									{#if $authState.user}
										<div class="border-b border-slate-100 px-4 py-2 text-xs text-slate-500 truncate max-w-xs">
											{$authState.user.email}
										</div>
									{/if}
									<a
										href="/settings"
										onclick={closeProfileMenu}
										class="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
										role="menuitem"
									>
										Settings
									</a>
									<button
										onclick={() => {
											closeProfileMenu();
											handleLogout();
										}}
										class="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
										role="menuitem"
									>
										Log out
									</button>
								</div>
							{/if}
						</div>
					</div>
				</div>
			</div>
		</nav>

		<main class="w-full max-w-full overflow-hidden px-4 py-6 sm:px-6 lg:px-8" aria-label="Main content">
			{@render children()}
		</main>
	</div>
{/if}
