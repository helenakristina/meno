<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { authState } from '$lib/stores/auth';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase/client';
	import { Menu, X } from '@lucide/svelte';
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { userSettings } from '$lib/stores/settings';
	import logo from '$lib/assets/logo.png';

	let { children }: { children: Snippet } = $props();
	let loading = $state(true);
	let mobileMenuOpen = $state(false);
	let profileMenuOpen = $state(false);
	const periodTrackingEnabled = $derived($userSettings?.period_tracking_enabled ?? false);
	const mhtTrackingEnabled = $derived($userSettings?.mht_tracking_enabled ?? false);

	// Check initial auth state (onMount — runs once, not reactive)
	onMount(() => {
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

	// Load settings into store — nav reactively derives periodTrackingEnabled from it
	onMount(async () => {
		try {
			const settings = await apiClient.get('/api/users/settings');
			userSettings.set(settings);
		} catch {
			// Leave store null — periodTrackingEnabled defaults to false
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
		...(periodTrackingEnabled ? [{ href: '/period', label: 'Cycles' }] : []),
		...(mhtTrackingEnabled ? [{ href: '/medications', label: 'Medications' }] : [])
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
	<div class="flex min-h-screen items-center justify-center bg-neutral-50">
		<div class="text-neutral-600">Loading...</div>
	</div>
{:else}
	<div class="min-h-screen bg-neutral-50">
		<!-- Mobile menu backdrop -->
		{#if mobileMenuOpen}
			<button
				class="fixed inset-0 z-40 w-full bg-black/30"
				onclick={closeMenu}
				aria-label="Close menu"
				tabindex="-1"
			></button>

			<!-- Mobile sidebar menu (only rendered when open) -->
			<div
				class="fixed top-0 left-0 z-50 h-full w-64 transform bg-white shadow-lg transition-transform duration-300"
			>
				<!-- Close button -->
				<div class="flex items-center justify-between border-b border-neutral-200 p-4">
					<a href="/dashboard" class="flex items-center gap-2">
						<img src={logo} alt="Meno" class="h-8 w-auto" />
						<span class="text-xl font-bold text-neutral-800">Meno</span>
					</a>
					<button
						onclick={closeMenu}
						class="text-neutral-500 hover:text-neutral-700"
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
								? 'bg-primary-50 font-semibold text-primary-800'
								: 'text-neutral-600 hover:bg-neutral-100 hover:text-primary-800'}"
						>
							{link.label}
						</a>
					{/each}
				</nav>

				<!-- Mobile user area -->
				{#if $authState.user}
					<div class="border-t border-neutral-200 p-4">
						<div class="mb-3 text-sm break-all text-neutral-600">{$authState.user.email}</div>
						<a
							href="/settings"
							onclick={closeMenu}
							class="mb-2 block rounded-md px-3 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-100"
						>
							Settings
						</a>
						<button
							onclick={() => {
								closeMenu();
								handleLogout();
							}}
							class="w-full rounded-md px-3 py-2 text-left text-sm font-medium text-neutral-600 hover:bg-neutral-100"
						>
							Log out
						</button>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Desktop nav -->
		<nav class="border-b border-neutral-200 bg-white">
			<div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
				<div class="flex h-16 items-center justify-between">
					<div class="flex items-center gap-10">
						<a href="/dashboard" class="flex items-center gap-2">
							<img src={logo} alt="Meno" class="h-8 w-auto" />
							<span class="text-xl font-bold text-neutral-800">Meno</span>
						</a>

						<!-- Desktop nav links (hidden on mobile) -->
						<div class="hidden gap-1 md:flex">
							{#each navLinks as link}
								<a
									href={link.href}
									aria-current={page.url.pathname === link.href ? 'page' : undefined}
									class="rounded-md px-3 py-2 text-sm font-medium {page.url.pathname === link.href
										? 'font-semibold text-primary-800'
										: 'text-neutral-600 hover:text-primary-800'}"
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
							class="flex h-11 w-11 items-center justify-center rounded text-neutral-500 hover:text-neutral-700 md:hidden"
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
								class="flex h-9 w-9 items-center justify-center rounded-full bg-primary-500 text-sm font-semibold text-white hover:bg-primary-600 focus:ring-2 focus:ring-primary-500 focus:ring-offset-1 focus:outline-none"
								aria-label="User menu"
								aria-expanded={profileMenuOpen}
							>
								{getUserInitials($authState.user?.email)}
							</button>

							{#if profileMenuOpen}
								<div
									class="absolute top-11 right-0 z-50 min-w-48 rounded-md border border-neutral-200 bg-white py-1 shadow-lg"
								>
									{#if $authState.user}
										<div
											class="max-w-xs truncate border-b border-neutral-100 px-4 py-2 text-xs text-neutral-500"
										>
											{$authState.user.email}
										</div>
									{/if}
									<a
										href="/settings"
										onclick={closeProfileMenu}
										class="block px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50"
									>
										Settings
									</a>
									<button
										onclick={() => {
											closeProfileMenu();
											handleLogout();
										}}
										class="block w-full px-4 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-50"
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

		<main
			class="w-full max-w-full overflow-hidden px-4 py-6 sm:px-6 lg:px-8"
			aria-label="Main content"
		>
			{@render children()}
		</main>
	</div>
{/if}
