<script lang="ts">
	import { apiClient } from '$lib/api/client';
	import type { DateValue } from '@internationalized/date';
	import type { FlowLevel, PeriodLog } from '$lib/types/period';

	let {
		open = $bindable(false),
		date,
		existingLog = null,
		journeyStage = null,
		onSave,
		onDelete
	}: {
		open: boolean;
		date: DateValue | null;
		existingLog?: PeriodLog | null;
		journeyStage?: string | null;
		onSave?: (log: PeriodLog, bleedingAlert: boolean) => void;
		onDelete?: (logId: string) => void;
	} = $props();

	// Form state
	let startDate = $state('');
	let endDate = $state('');
	let flowLevel = $state<FlowLevel | ''>('');
	let notes = $state('');

	let saving = $state(false);
	let deleting = $state(false);
	let confirmingDelete = $state(false);
	let error = $state<string | null>(null);
	let bleedingAlert = $state(false);

	const flowOptions: { value: FlowLevel; label: string; colorClass: string }[] = [
		{ value: 'spotting', label: 'Spotting', colorClass: 'bg-accent-100 text-accent-800 border-accent-200' },
		{ value: 'light', label: 'Light', colorClass: 'bg-accent-200 text-accent-800 border-accent-300' },
		{ value: 'medium', label: 'Medium', colorClass: 'bg-accent-400 text-white border-accent-400' },
		{ value: 'heavy', label: 'Heavy', colorClass: 'bg-accent-600 text-white border-accent-600' }
	];

	function dateValueToString(d: DateValue): string {
		return `${d.year}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
	}

	// Reset form when modal opens
	$effect(() => {
		if (open) {
			startDate = date ? dateValueToString(date) : '';
			endDate = existingLog?.period_end ?? startDate; // default to start month so picker opens there
			flowLevel = (existingLog?.flow_level as FlowLevel) ?? '';
			notes = existingLog?.notes ?? '';
			error = null;
			bleedingAlert = false;
			confirmingDelete = false;

			// Pre-check bleeding alert for post-menopause users
			if (journeyStage === 'post-menopause') {
				bleedingAlert = true;
			}
		}
	});

	function close() {
		open = false;
	}

	async function handleDelete() {
		if (!existingLog || deleting) return;
		deleting = true;
		error = null;
		try {
			await apiClient.delete(`/api/period/logs/${existingLog.id}`);
			onDelete?.(existingLog.id);
			close();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete. Please try again.';
		} finally {
			deleting = false;
			confirmingDelete = false;
		}
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

	function trapFocus(node: HTMLElement) {
		const focusable = () =>
			Array.from(
				node.querySelectorAll<HTMLElement>(
					'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
				)
			).filter((el) => !el.hasAttribute('disabled'));

		function onKeydown(e: KeyboardEvent) {
			if (e.key === 'Escape') {
				close();
				return;
			}
			if (e.key !== 'Tab') return;
			const els = focusable();
			if (!els.length) return;
			const first = els[0];
			const last = els[els.length - 1];
			if (e.shiftKey) {
				if (document.activeElement === first) {
					e.preventDefault();
					last.focus();
				}
			} else {
				if (document.activeElement === last) {
					e.preventDefault();
					first.focus();
				}
			}
		}

		// Focus first focusable element on mount
		const first = focusable()[0];
		first?.focus();

		node.addEventListener('keydown', onKeydown);
		return { destroy() { node.removeEventListener('keydown', onKeydown); } };
	}
</script>

{#if open}
	<!-- Backdrop (visual only — Escape and keyboard handled by panel's trapFocus action) -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 backdrop-blur-sm sm:items-center"
		onclick={close}
	>
		<!-- Panel -->
		<div
			class="w-full max-w-md rounded-2xl bg-white px-6 py-6 shadow-2xl"
			role="dialog"
			aria-modal="true"
			aria-labelledby="period-log-title"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
			use:trapFocus
		>
			<!-- Header -->
			<div class="mb-5 flex items-center justify-between">
				<h2 id="period-log-title" class="text-base font-semibold text-neutral-800">{title}</h2>
				<button
					onclick={close}
					class="rounded-full p-1.5 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-300"
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
					class="mb-5 rounded-lg border border-warning bg-warning-light px-4 py-3"
					role="alert"
					aria-live="polite"
				>
					<p class="text-sm font-medium text-warning-dark">Important: Please contact your doctor</p>
					<p class="mt-0.5 text-sm text-warning">
						Postmenopausal bleeding should be evaluated by a healthcare provider promptly. You can
						still save this log — it may be helpful to share with your doctor.
					</p>
				</div>
			{/if}

			<div class="space-y-5">
				<!-- Start date (required) -->
				<div>
					<label for="period-start" class="mb-1.5 block text-sm font-medium text-neutral-700">
						Period start date <span class="text-accent-500" aria-hidden="true">*</span>
					</label>
					<input
						id="period-start"
						type="date"
						bind:value={startDate}
						required
						class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm text-neutral-700 shadow-sm focus:border-accent-400 focus:ring-2 focus:ring-accent-200 focus:outline-none"
					/>
				</div>

				<!-- End date (optional) -->
				<div>
					<label for="period-end" class="mb-1.5 block text-sm font-medium text-neutral-700">
						Period end date
						<span class="ml-1 text-xs font-normal text-neutral-400">optional</span>
					</label>
					<input
						id="period-end"
						type="date"
						bind:value={endDate}
						min={startDate}
						class="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm text-neutral-700 shadow-sm focus:border-accent-400 focus:ring-2 focus:ring-accent-200 focus:outline-none"
					/>
				</div>

				<!-- Flow level (optional) -->
				<div>
					<p class="mb-2 text-sm font-medium text-neutral-700">
						Flow level
						<span class="ml-1 text-xs font-normal text-neutral-400">optional</span>
					</p>
					<div class="flex flex-wrap gap-2" role="group" aria-label="Select flow level">
						{#each flowOptions as opt (opt.value)}
							<button
								type="button"
								onclick={() => (flowLevel = flowLevel === opt.value ? '' : opt.value)}
								aria-pressed={flowLevel === opt.value}
								class="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-300
									{flowLevel === opt.value
									? opt.colorClass
									: 'border-neutral-200 bg-white text-neutral-600 hover:border-accent-200 hover:bg-accent-50 hover:text-accent-700'}"
							>
								{opt.label}
							</button>
						{/each}
					</div>
				</div>

				<!-- Notes (optional) -->
				<div>
					<label for="period-notes" class="mb-1.5 block text-sm font-medium text-neutral-700">
						Notes
						<span class="ml-1 text-xs font-normal text-neutral-400">optional</span>
					</label>
					<textarea
						id="period-notes"
						bind:value={notes}
						placeholder="Any additional details…"
						rows={3}
						class="w-full resize-none rounded-lg border border-neutral-200 px-3 py-2.5 text-sm text-neutral-700 placeholder-neutral-400 shadow-sm focus:border-accent-400 focus:ring-2 focus:ring-accent-200 focus:outline-none"
					></textarea>
				</div>

				<!-- Error -->
				{#if error}
					<p class="rounded-lg border border-danger-light bg-danger-light px-3 py-2 text-sm text-danger-dark" role="alert">
						{error}
					</p>
				{/if}

				<!-- Actions -->
				<div class="flex gap-3 pt-1">
					<button
						type="button"
						onclick={close}
						class="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-medium text-neutral-700 transition-colors hover:border-neutral-300 hover:bg-neutral-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-300"
					>
						Cancel
					</button>
					<button
						type="button"
						onclick={handleSubmit}
						disabled={!startDate || saving}
						class="flex-1 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-300
							{!startDate || saving
							? 'cursor-not-allowed bg-neutral-100 text-neutral-400'
							: 'bg-accent-600 text-white hover:bg-accent-700'}"
					>
						{saving ? 'Saving…' : isEditing ? 'Save changes' : 'Log period'}
					</button>
				</div>

				<!-- Delete (edit mode only, two-step inline confirmation) -->
				{#if isEditing}
					<div class="flex justify-center pt-1">
						{#if confirmingDelete}
							<div class="flex items-center gap-3 text-sm">
								<span class="text-neutral-600">Delete this log?</span>
								<button
									type="button"
									onclick={handleDelete}
									disabled={deleting}
									class="font-medium text-danger hover:text-danger-dark focus:outline-none focus-visible:underline"
								>
									{deleting ? 'Deleting…' : 'Yes, delete'}
								</button>
								<button
									type="button"
									onclick={() => (confirmingDelete = false)}
									class="text-neutral-500 hover:text-neutral-700 focus:outline-none focus-visible:underline"
								>
									Keep
								</button>
							</div>
						{:else}
							<button
								type="button"
								onclick={() => (confirmingDelete = true)}
								class="text-sm text-neutral-400 hover:text-danger focus:outline-none focus-visible:underline"
							>
								Delete log
							</button>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
