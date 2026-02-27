<script lang="ts">
	import { apiClient } from '$lib/api/client';

	// -------------------------------------------------------------------------
	// Date utilities
	// -------------------------------------------------------------------------

	// Returns YYYY-MM-DD in local time — reliable cross-browser via en-CA locale.
	function toDateStr(date: Date): string {
		return date.toLocaleDateString('en-CA');
	}

	function formatDisplay(dateStr: string): string {
		const d = new Date(`${dateStr}T12:00:00`);
		return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
	}

	const today = new Date();
	const todayStr = toDateStr(today);
	const defaultStart = toDateStr(new Date(today.getTime() - 30 * 86_400_000));

	// -------------------------------------------------------------------------
	// State
	// -------------------------------------------------------------------------

	let startDate = $state(defaultStart);
	let endDate = $state(todayStr);

	let pdfLoading = $state(false);
	let csvLoading = $state(false);
	let pdfError = $state('');
	let csvError = $state('');
	let successMessage = $state('');

	// -------------------------------------------------------------------------
	// Derived
	// -------------------------------------------------------------------------

	let startError = $derived(
		startDate && endDate && startDate > endDate
			? 'Start date must be on or before end date.'
			: ''
	);

	let endError = $derived(endDate > todayStr ? 'End date cannot be in the future.' : '');

	let isValid = $derived(!!startDate && !!endDate && !startError && !endError);

	let dateRangeDisplay = $derived(
		startDate && endDate ? `${formatDisplay(startDate)} – ${formatDisplay(endDate)}` : ''
	);

	function isNoDataError(message: string): boolean {
		return message.toLowerCase().includes('no symptom logs') || message.toLowerCase().includes('no logs found');
	}

	// -------------------------------------------------------------------------
	// Download handlers
	// -------------------------------------------------------------------------

	function triggerDownload(blob: Blob, filename: string) {
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	async function downloadPdf() {
		if (!isValid || pdfLoading) return;
		pdfLoading = true;
		pdfError = '';
		successMessage = '';

		try {
			const blob = await apiClient.post<Blob>(
				'/api/export/pdf',
				{ date_range_start: startDate, date_range_end: endDate },
				{ responseType: 'blob' }
			);
			triggerDownload(blob, `meno-report-${startDate}-to-${endDate}.pdf`);
			successMessage = `PDF downloaded for ${dateRangeDisplay}`;
			setTimeout(() => {
				successMessage = '';
			}, 3000);
		} catch (e) {
			pdfError = e instanceof Error ? e.message : 'Failed to generate PDF. Please try again.';
		} finally {
			pdfLoading = false;
		}
	}

	async function downloadCsv() {
		if (!isValid || csvLoading) return;
		csvLoading = true;
		csvError = '';
		successMessage = '';

		try {
			const blob = await apiClient.post<Blob>(
				'/api/export/csv',
				{ date_range_start: startDate, date_range_end: endDate },
				{ responseType: 'blob' }
			);
			triggerDownload(blob, `meno-report-${startDate}-to-${endDate}.csv`);
			successMessage = `CSV downloaded for ${dateRangeDisplay}`;
			setTimeout(() => {
				successMessage = '';
			}, 3000);
		} catch (e) {
			csvError = e instanceof Error ? e.message : 'Failed to export CSV. Please try again.';
		} finally {
			csvLoading = false;
		}
	}
</script>

<div class="px-4 py-8 sm:px-0">
	<!-- Header -->
	<div class="mb-8">
		<h1 class="text-2xl font-bold text-slate-900">Export Your Data</h1>
		<p class="mt-1 text-slate-500">Download your symptom history to share with your healthcare provider.</p>
	</div>

	<!-- Date Range Card -->
	<section class="mb-6 rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
		<h2 class="mb-4 text-base font-semibold text-slate-800">Select Date Range</h2>

		<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
			<!-- Start date -->
			<div>
				<label for="start-date" class="mb-1.5 block text-sm font-medium text-slate-700">
					From
				</label>
				<input
					id="start-date"
					type="date"
					bind:value={startDate}
					max={todayStr}
					aria-describedby={startError ? 'start-date-error' : undefined}
					class="w-full rounded-lg border px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-teal-200
						{startError ? 'border-red-300 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-teal-400'}"
				/>
				{#if startError}
					<p id="start-date-error" class="mt-1.5 text-xs text-red-600">{startError}</p>
				{/if}
			</div>

			<!-- End date -->
			<div>
				<label for="end-date" class="mb-1.5 block text-sm font-medium text-slate-700">
					To
				</label>
				<input
					id="end-date"
					type="date"
					bind:value={endDate}
					max={todayStr}
					aria-describedby={endError ? 'end-date-error' : undefined}
					class="w-full rounded-lg border px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-teal-200
						{endError ? 'border-red-300 focus:border-red-400 focus:ring-red-100' : 'border-slate-200 focus:border-teal-400'}"
				/>
				{#if endError}
					<p id="end-date-error" class="mt-1.5 text-xs text-red-600">{endError}</p>
				{/if}
			</div>
		</div>
	</section>

	<!-- Success banner -->
	{#if successMessage}
		<div class="mb-6 flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4">
			<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0 text-emerald-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
				<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
			</svg>
			<p class="text-sm font-medium text-emerald-800">{successMessage}</p>
		</div>
	{/if}

	<!-- Export format cards -->
	<div class="grid grid-cols-1 gap-5 lg:grid-cols-2">

		<!-- PDF card -->
		<div class="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
			<div class="mb-4 flex items-start gap-3">
				<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-600">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clip-rule="evenodd" />
					</svg>
				</div>
				<div>
					<h3 class="font-semibold text-slate-800">Doctor Visit Summary</h3>
					<p class="mt-0.5 text-sm text-slate-500">PDF · Best for provider appointments</p>
				</div>
			</div>

			<p class="mb-5 text-sm leading-relaxed text-slate-600">
				Includes AI-generated symptom patterns, frequency analysis, co-occurrence insights, and suggested questions for your provider. Formatted for clinical conversations.
			</p>

			<ul class="mb-5 space-y-1.5 text-xs text-slate-500">
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400"></span>
					Symptom pattern summary
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400"></span>
					Top 10 most-logged symptoms
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400"></span>
					Co-occurrence insights
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-400"></span>
					5–7 questions to ask your provider
				</li>
			</ul>

			{#if pdfError}
				<div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
					{#if isNoDataError(pdfError)}
						<p class="text-sm text-red-700">
							No symptoms logged in this date range.
							<a href="/log" class="font-medium underline hover:text-red-900">Start logging</a>
							to generate a report.
						</p>
					{:else}
						<div class="flex items-start justify-between gap-2">
							<p class="text-sm text-red-700">{pdfError}</p>
							<button
								onclick={() => (pdfError = '')}
								aria-label="Dismiss error"
								class="shrink-0 text-red-400 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
							>
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
									<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
								</svg>
							</button>
						</div>
					{/if}
				</div>
			{/if}

			<button
				onclick={downloadPdf}
				disabled={!isValid || pdfLoading}
				aria-busy={pdfLoading}
				class="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-teal-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 sm:w-auto"
			>
				{#if pdfLoading}
					<svg class="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
					Generating PDF...
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
					</svg>
					Download PDF Report
				{/if}
			</button>

			{#if pdfLoading}
				<p class="mt-2 text-xs text-slate-400">This usually takes 3–5 seconds while we generate your summary.</p>
			{/if}
		</div>

		<!-- CSV card -->
		<div class="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
			<div class="mb-4 flex items-start gap-3">
				<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path fill-rule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clip-rule="evenodd" />
					</svg>
				</div>
				<div>
					<h3 class="font-semibold text-slate-800">Raw Data Export</h3>
					<p class="mt-0.5 text-sm text-slate-500">CSV · Opens in Excel or Google Sheets</p>
				</div>
			</div>

			<p class="mb-5 text-sm leading-relaxed text-slate-600">
				Simple spreadsheet with dates, symptoms, and notes. Import to Excel, Google Sheets, or Numbers for your own analysis or personal records.
			</p>

			<ul class="mb-5 space-y-1.5 text-xs text-slate-500">
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"></span>
					Date, symptoms, and notes per row
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"></span>
					Compatible with Excel, Sheets, Numbers
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"></span>
					Oldest entries first
				</li>
				<li class="flex items-center gap-2">
					<span class="h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400"></span>
					No account data or PII included
				</li>
			</ul>

			{#if csvError}
				<div class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
					{#if isNoDataError(csvError)}
						<p class="text-sm text-red-700">
							No symptoms logged in this date range.
							<a href="/log" class="font-medium underline hover:text-red-900">Start logging</a>
							to generate a report.
						</p>
					{:else}
						<div class="flex items-start justify-between gap-2">
							<p class="text-sm text-red-700">{csvError}</p>
							<button
								onclick={() => (csvError = '')}
								aria-label="Dismiss error"
								class="shrink-0 text-red-400 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
							>
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
									<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
								</svg>
							</button>
						</div>
					{/if}
				</div>
			{/if}

			<button
				onclick={downloadCsv}
				disabled={!isValid || csvLoading}
				aria-busy={csvLoading}
				class="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400 sm:w-auto"
			>
				{#if csvLoading}
					<svg class="h-4 w-4 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden="true">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
					</svg>
					Exporting...
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
						<path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
					</svg>
					Download CSV Data
				{/if}
			</button>
		</div>
	</div>

	<!-- Disclaimer -->
	<p class="mt-8 text-xs text-slate-400">
		Reports contain symptom observations only — not medical diagnoses. Share with your provider to support an informed conversation.
	</p>
</div>
