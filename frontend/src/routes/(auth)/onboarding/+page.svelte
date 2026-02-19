<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { fly, fade } from 'svelte/transition';
	import { supabase } from '$lib/supabase/client';

	const API_BASE = 'http://localhost:8000';

	type JourneyStage = 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';

	const stages: { value: JourneyStage; label: string; description: string }[] = [
		{
			value: 'perimenopause',
			label: 'Perimenopause',
			description: 'Experiencing changes but still having periods (even if irregular)'
		},
		{
			value: 'menopause',
			label: 'Menopause',
			description: 'No period for 12+ consecutive months'
		},
		{
			value: 'post-menopause',
			label: 'Post-menopause',
			description: 'Beyond the 12-month mark'
		},
		{
			value: 'unsure',
			label: 'Not sure',
			description: "Not sure where I am in the process"
		}
	];

	// Today's date as YYYY-MM-DD, used as the max for the date input
	const todayStr = new Date().toISOString().split('T')[0];

	let dateOfBirth = $state('');
	let journeyStage = $state<JourneyStage | ''>('');
	let disclaimerAcknowledged = $state(false);
	let loading = $state(false);
	let error = $state('');
	let dobError = $state('');
	let success = $state(false);
	let checkingAuth = $state(true);

	let canSubmit = $derived(
		dateOfBirth !== '' &&
			journeyStage !== '' &&
			disclaimerAcknowledged &&
			dobError === '' &&
			!loading
	);

	onMount(async () => {
		try {
			const { data: sessionData } = await supabase.auth.getSession();

			if (!sessionData.session) {
				goto('/login');
				return;
			}

			// Redirect if the user has already completed onboarding
			const { data: profile } = await supabase
				.from('users')
				.select('id')
				.eq('id', sessionData.session.user.id)
				.maybeSingle();

			if (profile) {
				goto('/dashboard');
				return;
			}
		} catch (e) {
			// If the auth check fails, show the form anyway
			console.error('Auth check failed:', e);
		}

		checkingAuth = false;
	});

	function validateDob() {
		if (!dateOfBirth) {
			dobError = '';
			return;
		}

		// Parse as local date to avoid timezone-shifted "yesterday" errors
		const [year, month, day] = dateOfBirth.split('-').map(Number);
		const dob = new Date(year, month - 1, day);
		const today = new Date();
		today.setHours(0, 0, 0, 0);

		if (dob >= today) {
			dobError = 'Date of birth must be in the past.';
			return;
		}

		// Accurate age calculation: subtract 1 if birthday hasn't occurred yet this year
		let age = today.getFullYear() - dob.getFullYear();
		const monthDiff = today.getMonth() - dob.getMonth();
		if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
			age--;
		}

		if (age < 18) {
			dobError = 'You must be at least 18 years old to use Meno.';
		} else {
			dobError = '';
		}
	}

	async function handleSubmit() {
		if (!canSubmit) return;

		loading = true;
		error = '';

		try {
			const { data: sessionData } = await supabase.auth.getSession();
			const token = sessionData.session?.access_token;

			if (!token) {
				error = 'Your session has expired. Please sign in again.';
				goto('/login');
				return;
			}

			const response = await fetch(`${API_BASE}/api/users/onboarding`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${token}`,
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					date_of_birth: dateOfBirth,
					journey_stage: journeyStage
				})
			});

			if (response.status === 409) {
				// Already onboarded — redirect silently
				goto('/dashboard');
				return;
			}

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				if (response.status === 400) {
					error = errorData.detail ?? 'Please check your date of birth and try again.';
				} else {
					error = errorData.detail ?? 'Something went wrong. Please try again.';
				}
				return;
			}

			success = true;
			setTimeout(() => goto('/dashboard'), 1200);
		} catch (e) {
			error = 'Network error. Please check your connection and try again.';
			console.error('Onboarding error:', e);
		} finally {
			loading = false;
		}
	}
</script>

{#if checkingAuth}
	<div class="flex min-h-screen items-center justify-center bg-slate-50">
		<p class="text-sm text-slate-400">Loading…</p>
	</div>
{:else if success}
	<div
		class="flex min-h-screen items-center justify-center bg-slate-50 px-4"
		in:fade={{ duration: 200 }}
	>
		<div class="text-center">
			<div
				class="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100"
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-8 w-8 text-emerald-600"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
					stroke-width="2"
					aria-hidden="true"
				>
					<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
				</svg>
			</div>
			<h2 class="text-2xl font-semibold text-slate-900">You're all set!</h2>
			<p class="mt-2 text-slate-500">Taking you to your dashboard…</p>
		</div>
	</div>
{:else}
	<div class="min-h-screen bg-slate-50 px-4 py-12" in:fade={{ duration: 150 }}>
		<div class="mx-auto max-w-lg">

			<!-- Header -->
			<div class="mb-8 text-center">
				<h1 class="text-3xl font-bold text-slate-900">Welcome to Meno</h1>
				<p class="mt-2 text-slate-500">
					Meno helps you track perimenopause and menopause symptoms, understand patterns,
					and prepare for healthcare conversations.
				</p>
				<p class="mt-5 text-lg font-medium text-slate-700">Tell us a bit about yourself</p>
			</div>

			<!-- Medical disclaimer -->
			<div class="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
				<div class="flex gap-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="mt-0.5 h-5 w-5 shrink-0 text-amber-600"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						stroke-width="2"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
					<p class="text-sm leading-relaxed text-amber-900">
						Meno provides educational information and symptom tracking. It is not a medical tool
						and cannot diagnose conditions, recommend treatments, or replace the advice of a
						healthcare provider. Please discuss your symptoms and any treatment decisions with
						your doctor.
					</p>
				</div>
				<label class="mt-4 flex cursor-pointer items-center gap-3">
					<input
						type="checkbox"
						bind:checked={disclaimerAcknowledged}
						class="h-4 w-4 rounded border-amber-400 accent-amber-600"
					/>
					<span class="text-sm font-medium text-amber-900">I understand</span>
				</label>
			</div>

			<!-- Form card -->
			<div class="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
				<form
					onsubmit={(e) => {
						e.preventDefault();
						handleSubmit();
					}}
				>
					<!-- Date of Birth -->
					<div class="mb-8">
						<label for="dob" class="mb-1.5 block text-sm font-semibold text-slate-700">
							Date of Birth
						</label>
						<input
							type="date"
							id="dob"
							bind:value={dateOfBirth}
							onchange={validateDob}
							onblur={validateDob}
							max={todayStr}
							required
							class="w-full rounded-lg border px-3 py-2.5 text-sm text-slate-800 transition-colors focus:outline-none focus:ring-2
								{dobError
								? 'border-red-300 focus:border-red-400 focus:ring-red-200'
								: 'border-slate-300 focus:border-violet-400 focus:ring-violet-200'}"
						/>
						{#if dobError}
							<p
								class="mt-1.5 text-sm text-red-600"
								in:fly={{ y: -4, duration: 150 }}
								role="alert"
							>
								{dobError}
							</p>
						{:else}
							<p class="mt-1.5 text-xs text-slate-400">
								Used to provide age-appropriate information
							</p>
						{/if}
					</div>

					<!-- Journey Stage -->
					<fieldset class="mb-8">
						<legend class="mb-3 text-sm font-semibold text-slate-700">
							Where are you in your journey?
						</legend>
						<div class="space-y-2.5">
							{#each stages as stage (stage.value)}
								<label
									class="flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-all
										{journeyStage === stage.value
										? 'border-violet-400 bg-violet-50 shadow-sm'
										: 'border-slate-200 hover:border-slate-300 hover:bg-slate-50/80'}"
								>
									<input
										type="radio"
										name="journey_stage"
										value={stage.value}
										bind:group={journeyStage}
										class="mt-0.5 shrink-0 accent-violet-600"
									/>
									<div>
										<span
											class="block font-medium
												{journeyStage === stage.value ? 'text-violet-900' : 'text-slate-800'}"
										>
											{stage.label}
										</span>
										<span class="mt-0.5 block text-sm text-slate-500">
											{stage.description}
										</span>
									</div>
								</label>
							{/each}
						</div>
						<p class="mt-3 text-xs text-slate-400">
							Don't worry if you're unsure — this helps us show relevant information, and you can
							update it later.
						</p>
					</fieldset>

					<!-- API error -->
					{#if error}
						<div
							class="mb-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
							in:fly={{ y: -4, duration: 150 }}
							role="alert"
						>
							{error}
						</div>
					{/if}

					<!-- Submit -->
					<button
						type="submit"
						disabled={!canSubmit}
						class="w-full rounded-xl bg-slate-900 px-6 py-3.5 text-sm font-semibold text-white shadow-sm transition-all
							hover:bg-slate-800
							disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
					>
						{loading ? 'Setting up your account…' : 'Complete Setup'}
					</button>
				</form>
			</div>
		</div>
	</div>
{/if}
