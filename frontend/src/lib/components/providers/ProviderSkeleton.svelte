<div class="space-y-4">
	{#each [1, 2, 3] as _}
		<div class="animate-pulse rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
			<!-- Name + NAMS badge row -->
			<div class="mb-3 flex items-start justify-between gap-3">
				<div class="space-y-2">
					<div class="h-5 w-52 rounded-md bg-slate-200"></div>
					<div class="h-4 w-36 rounded-md bg-slate-100"></div>
					<div class="h-4 w-24 rounded-md bg-slate-100"></div>
				</div>
				<div class="h-7 w-32 shrink-0 rounded-full bg-amber-100"></div>
			</div>

			<!-- Provider type pill -->
			<div class="mb-3 h-6 w-24 rounded-full bg-teal-50"></div>

			<!-- Insurance tags -->
			<div class="mb-4 flex items-center gap-2">
				<div class="h-4 w-16 rounded bg-slate-100"></div>
				<div class="h-5 w-16 rounded-full bg-slate-100"></div>
				<div class="h-5 w-20 rounded-full bg-slate-100"></div>
				<div class="h-5 w-14 rounded-full bg-slate-100"></div>
			</div>

			<!-- Footer: phone + button -->
			<div class="flex items-center justify-between">
				<div class="h-4 w-32 rounded bg-slate-100"></div>
				<div class="h-8 w-44 rounded-lg bg-slate-100"></div>
			</div>
		</div>
	{/each}
</div>
