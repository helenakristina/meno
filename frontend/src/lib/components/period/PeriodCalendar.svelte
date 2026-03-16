<script lang="ts">
	import { Calendar } from 'bits-ui';
	import {
		getLocalTimeZone,
		today,
		type DateValue,
		CalendarDate
	} from '@internationalized/date';

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
		logs = [],
		onDayClick
	}: {
		logs: PeriodLog[];
		onDayClick: (date: DateValue, existingLog: PeriodLog | null) => void;
	} = $props();

	let currentMonth = $state(today(getLocalTimeZone()));

	// Build a lookup: "YYYY-MM-DD" → PeriodLog
	const logByDate = $derived(() => {
		const map = new Map<string, PeriodLog>();
		for (const log of logs) {
			map.set(log.period_start, log);
		}
		return map;
	});

	function getLogForDate(date: DateValue): PeriodLog | null {
		const key = `${date.year}-${String(date.month).padStart(2, '0')}-${String(date.day).padStart(2, '0')}`;
		return logByDate().get(key) ?? null;
	}

	function isPeriodRangeDay(date: DateValue): boolean {
		for (const log of logs) {
			if (!log.period_end) continue;
			const start = parseDate(log.period_start);
			const end = parseDate(log.period_end);
			if (date.compare(start) > 0 && date.compare(end) < 0) return true;
		}
		return false;
	}

	function parseDate(iso: string): DateValue {
		const [y, m, d] = iso.split('-').map(Number);
		return new CalendarDate(y, m, d);
	}

	function flowColorClass(flowLevel: FlowLevel | null): string {
		switch (flowLevel) {
			case 'spotting': return 'bg-rose-100 text-rose-900';
			case 'light': return 'bg-rose-200 text-rose-900';
			case 'medium': return 'bg-rose-400 text-white';
			case 'heavy': return 'bg-rose-600 text-white';
			default: return 'bg-rose-300 text-white';
		}
	}

	const todayValue = today(getLocalTimeZone());
</script>

<Calendar.Root
	type="single"
	bind:placeholder={currentMonth}
	class="w-full"
>
	{#snippet children({ months, weekdays })}
		<Calendar.Header class="mb-4 flex items-center justify-between">
			<Calendar.PrevButton
				class="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-30"
				aria-label="Previous month"
			>
				‹
			</Calendar.PrevButton>
			<Calendar.Heading class="text-sm font-semibold text-slate-900" />
			<Calendar.NextButton
				class="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-30"
				aria-label="Next month"
			>
				›
			</Calendar.NextButton>
		</Calendar.Header>

		{#each months as month (month.value)}
			<Calendar.Grid class="w-full border-collapse">
				<Calendar.GridHead>
					<Calendar.GridRow class="flex">
						{#each weekdays as day, i (i)}
							<Calendar.HeadCell
								class="flex-1 py-1 text-center text-xs font-medium text-slate-400"
							>
								{day.slice(0, 2)}
							</Calendar.HeadCell>
						{/each}
					</Calendar.GridRow>
				</Calendar.GridHead>

				<Calendar.GridBody>
					{#each month.weeks as weekDates, i (i)}
						<Calendar.GridRow class="flex mt-1">
							{#each weekDates as date, d (d)}
								{@const log = getLogForDate(date)}
								{@const isRangeDay = isPeriodRangeDay(date)}
								{@const isToday = date.compare(todayValue) === 0}
								<Calendar.Cell
									{date}
									month={month.value}
									class="relative flex-1 p-0 text-center"
								>
									<!-- Period range background stripe (days between start and end) -->
									{#if isRangeDay}
										<div class="absolute inset-y-0 inset-x-0 bg-rose-100 rounded-none pointer-events-none"></div>
									{/if}

									<Calendar.Day
										class="relative z-10 mx-auto flex h-9 w-9 items-center justify-center rounded-full text-sm transition-colors
											{log ? flowColorClass(log.flow_level) : ''}
											{!log && !isRangeDay ? 'text-slate-700 hover:bg-slate-100' : ''}
											{!log && isRangeDay ? 'text-rose-700 hover:bg-rose-200' : ''}
											data-[outside-month]:opacity-30
											data-[outside-month]:pointer-events-none
											focus:outline-none focus:ring-2 focus:ring-rose-400 focus:ring-offset-1"
										onclick={() => onDayClick(date, log)}
									>
										<span>{date.day}</span>
										<!-- Today indicator dot (only if no period log) -->
										{#if isToday && !log}
											<span
												class="absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-slate-400"
												aria-hidden="true"
											></span>
										{/if}
									</Calendar.Day>
								</Calendar.Cell>
							{/each}
						</Calendar.GridRow>
					{/each}
				</Calendar.GridBody>
			</Calendar.Grid>
		{/each}
	{/snippet}
</Calendar.Root>

<!-- Legend -->
<div class="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
	<span class="flex items-center gap-1.5">
		<span class="inline-block h-3 w-3 rounded-full bg-rose-100 border border-rose-200"></span>
		Spotting
	</span>
	<span class="flex items-center gap-1.5">
		<span class="inline-block h-3 w-3 rounded-full bg-rose-200"></span>
		Light
	</span>
	<span class="flex items-center gap-1.5">
		<span class="inline-block h-3 w-3 rounded-full bg-rose-400"></span>
		Medium
	</span>
	<span class="flex items-center gap-1.5">
		<span class="inline-block h-3 w-3 rounded-full bg-rose-600"></span>
		Heavy
	</span>
</div>
