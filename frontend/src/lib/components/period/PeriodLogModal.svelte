<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { DateValue } from '@internationalized/date';

	type FlowLevel = 'spotting' | 'light' | 'medium' | 'heavy';

	type PeriodLog = {
		id: string;
		period_start: string;
		period_end: string | null;
		flow_level: FlowLevel | null;
		notes: string | null;
		cycle_length: number | null;
		created_at: string;
	};

	let {
		open = $bindable(false),
		date,
		existingLog = null,
		journeyStage = null,
		onSave
	}: {
		open: boolean;
		date: DateValue | null;
		existingLog?: PeriodLog | null;
		journeyStage?: string | null;
		onSave?: (log: PeriodLog, bleedingAlert: boolean) => void;
	} = $props();

	// Form state
	let startDate = $state('');
	let endDate = $state('');
	let flowLevel = $state<FlowLevel | ''>('');
	let notes = $state('');

	let saving = $state(false);
	let error = $state<string | null>(null);
	let bleedingAlert = $state(false);

	const flowOptions: { value: FlowLevel; label: string; colorClass: string }[] = [
		{ value: 'spotting', label: 'Spotting', colorClass: 'bg-rose-100 text-rose-800 border-rose-200' },
		{ value: 'light', label: 'Light', colorClass: 'bg-rose-200 text-rose-800 border-rose-300' },
		{ value: 'medium', label: 'Medium', colorClass: 'bg-rose-400 text-white border-rose-400' },
		{ value: 'heavy', label: 'Heavy', colorClass: 'bg-rose-600 text-white border-rose-600' }
	];

	function dateValueToString(d: DateValue): string {
		return `${d.year}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
	}

	// Reset form when modal opens
	$effect(() => {
		if (open) {
			startDate = date ? dateValueToString(date) : '';
			endDate = existingLog?.period_end ?? '';
			flowLevel = (existingLog?.flow_level as FlowLevel) ?? '';
			notes = existingLog?.notes ?? '';
			error = null;
			bleedingAlert = false;

			// Pre-check bleeding alert for post-menopause users
			if (journeyStage === 'post-menopause') {
				bleedingAlert = true;
			}
		}
	});

	function close() {
		open = false;
	}

	function handleBackdropKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	async function handleSubmit() {
		if (!startDate || saving) return;
		saving = true;
		error = null;

		try {
			if (existingLog) {
				// Edit existing log — PATCH
				const body: Record<string, unknown> = {};
				if (endDate) body.period_end = endDate;
				if (flowLevel) body.flow_level = flowLevel;
				if (notes.trim()) body.notes = notes.trim();

				const updated = await apiClient.patch<PeriodLog>(
					`/api/period/logs/${existingLog.id}`,
					body
				);
				onSave?.(updated, bleedingAlert);
			} else {
				// Create new log — POST
				const body: Record<string, unknown> = { period_start: startDate };
				if (endDate) body.period_end = endDate;
				if (flowLevel) body.flow_level = flowLevel;
				if (notes.trim()) body.notes = notes.trim();

				const response = await apiClient.post('/api/period/logs', body);
				const { log, bleeding_alert } = response as { log: PeriodLog; bleeding_alert: boolean };
				bleedingAlert = bleeding_alert;
				onSave?.(log, bleeding_alert);
			}
			close();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save. Please try again.';
		} finally {
			saving = false;
		}
	}

	const isEditing = $derived(existingLog !== null);
	const title = $derived(isEditing ? 'Edit Period Log' : 'Log Period');
</script>

{#if open}
	<!-- Backdrop -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 backdrop-blur-sm sm:items-center"
		role="dialog"
		aria-modal="true"
		aria-labelledby="period-log-title"
		tabindex="-1"
		onclick={close}
		onkeydown={handleBackdropKeydown}
	>
		<!-- Panel -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			class="w-full max-w-md rounded-2xl bg-white px-6 py-6 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="document"
		>
			<!-- Header -->
			<div class="mb-5 flex items-center justify-between">
				<h2 id="period-log-title" class="text-base font-semibold text-slate-900">{title}</h2>
				<button
					onclick={close}
					class="rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
					aria-label="Close modal"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						class="size-4"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
					>
						<path d="M18 6 6 18M6 6l12 12" />
					</svg>
				</button>
			</div>

			<!-- Postmenopausal bleeding alert -->
			{#if bleedingAlert}
				<div
					class="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3"
					role="alert"
					aria-live="polite"
				>
					<p class="text-sm font-medium text-amber-800">Important: Please contact your doctor</p>
					<p class="mt-0.5 text-sm text-amber-700">
						Postmenopausal bleeding should be evaluated by a healthcare provider promptly. You can
						still save this log — it may be helpful to share with your doctor.
					</p>
				</div>
			{/if}

			<div class="space-y-5">
				<!-- Start date (required) -->
				<div>
					<label for="period-start" class="mb-1.5 block text-sm font-medium text-slate-700">
						Period start date <span class="text-rose-500" aria-hidden="true">*</span>
					</label>
					<input
						id="period-start"
						type="date"
						bind:value={startDate}
						required
						class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-rose-400 focus:ring-2 focus:ring-rose-200 focus:outline-none"
					/>
				</div>

				<!-- End date (optional) -->
				<div>
					<label for="period-end" class="mb-1.5 block text-sm font-medium text-slate-700">
						Period end date
						<span class="ml-1 text-xs font-normal text-slate-400">optional</span>
					</label>
					<input
						id="period-end"
						type="date"
						bind:value={endDate}
						min={startDate}
						class="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-rose-400 focus:ring-2 focus:ring-rose-200 focus:outline-none"
					/>
				</div>

				<!-- Flow level (optional) -->
				<div>
					<p class="mb-2 text-sm font-medium text-slate-700">
						Flow level
						<span class="ml-1 text-xs font-normal text-slate-400">optional</span>
					</p>
					<div class="flex flex-wrap gap-2" role="group" aria-label="Select flow level">
						{#each flowOptions as opt (opt.value)}
							<button
								type="button"
								onclick={() => (flowLevel = flowLevel === opt.value ? '' : opt.value)}
								aria-pressed={flowLevel === opt.value}
								class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300
									{flowLevel === opt.value
									? opt.colorClass
									: 'border-slate-200 bg-white text-slate-600 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700'}"
							>
								{opt.label}
							</button>
						{/each}
					</div>
				</div>

				<!-- Notes (optional) -->
				<div>
					<label for="period-notes" class="mb-1.5 block text-sm font-medium text-slate-700">
						Notes
						<span class="ml-1 text-xs font-normal text-slate-400">optional</span>
					</label>
					<textarea
						id="period-notes"
						bind:value={notes}
						placeholder="Any additional details…"
						rows={3}
						class="w-full resize-none rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-700 placeholder-slate-400 shadow-sm focus:border-rose-400 focus:ring-2 focus:ring-rose-200 focus:outline-none"
					></textarea>
				</div>

				<!-- Error -->
				{#if error}
					<p class="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
						{error}
					</p>
				{/if}

				<!-- Actions -->
				<div class="flex gap-3 pt-1">
					<button
						type="button"
						onclick={close}
						class="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
					>
						Cancel
					</button>
					<button
						type="button"
						onclick={handleSubmit}
						disabled={!startDate || saving}
						class="flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-300
							{!startDate || saving
							? 'cursor-not-allowed bg-slate-100 text-slate-400'
							: 'bg-rose-600 text-white hover:bg-rose-700'}"
					>
						{saving ? 'Saving…' : isEditing ? 'Save changes' : 'Log period'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
