<script lang="ts">
	import { tick } from 'svelte';
	import { apiClient } from '$lib/api/client';

	// -------------------------------------------------------------------------
	// Types
	// -------------------------------------------------------------------------

	interface Citation {
		url: string;
		title: string;
		section?: string;
		source_index?: number;
	}

	interface Message {
		role: 'user' | 'assistant';
		content: string;
		citations: Citation[];
	}

	interface ChatApiResponse {
		message: string;
		citations: Citation[];
		conversation_id: string;
	}

	// -------------------------------------------------------------------------
	// Constants
	// -------------------------------------------------------------------------

	const STARTER_PROMPTS = [
		'What causes brain fog during perimenopause?',
		'How do I talk to my doctor about hormone therapy?',
		"What's the difference between perimenopause and menopause?",
		'Why do I keep waking up at 3am?',
		'What does current research say about HRT safety?',
		'What symptoms are commonly dismissed but actually related to hormones?'
	];

	// -------------------------------------------------------------------------
	// State
	// -------------------------------------------------------------------------

	let messages = $state<Message[]>([]);
	let conversationId = $state<string | null>(null);
	let inputText = $state('');
	let loading = $state(false);
	let error = $state<string | null>(null);

	let chatContainer = $state<HTMLDivElement | null>(null);
	let textareaEl = $state<HTMLTextAreaElement | null>(null);

	let canSend = $derived(inputText.trim().length > 0 && !loading);
	let hasMessages = $derived(messages.length > 0);

	// -------------------------------------------------------------------------
	// Auto-scroll when messages change
	// -------------------------------------------------------------------------

	$effect(() => {
		const _dep = messages.length;
		tick().then(() => {
			chatContainer?.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
		});
	});

	// -------------------------------------------------------------------------
	// Helpers
	// -------------------------------------------------------------------------

	function adjustTextareaHeight() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
		// Max 5 lines (~120px at 1.5rem line-height)
		textareaEl.style.height = Math.min(textareaEl.scrollHeight, 120) + 'px';
	}

	function escapeHtml(str: string): string {
		return str
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}

	/**
	 * HTML-escape content, convert newlines to <br>, and replace [Source N]
	 * markers with clickable superscript citation links.
	 */
	function renderContent(content: string, citations: Citation[]): string {
		const escaped = escapeHtml(content).replace(/\n/g, '<br>');
		return escaped.replace(/\[Source (\d+)\]/g, (_match, n) => {
			const idx = parseInt(n, 10) - 1;
			if (idx >= 0 && idx < citations.length) {
				const url = escapeHtml(citations[idx].url);
				return `<sup><a href="${url}" target="_blank" rel="noopener noreferrer" class="citation-ref">[${n}]</a></sup>`;
			}
			return `<sup>[${n}]</sup>`;
		});
	}

	// -------------------------------------------------------------------------
	// Actions
	// -------------------------------------------------------------------------

	async function sendMessage(text: string) {
		const trimmed = text.trim();
		if (!trimmed || loading) return;

		error = null;
		inputText = '';
		await tick();
		adjustTextareaHeight();
		loading = true;

		messages = [...messages, { role: 'user', content: trimmed, citations: [] }];

		try {
			const data = await apiClient.post<ChatApiResponse>('/api/chat', {
				message: trimmed,
				...(conversationId ? { conversation_id: conversationId } : {})
			});
			conversationId = data.conversation_id;
			messages = [
				...messages,
				{ role: 'assistant', content: data.message, citations: data.citations }
			];
		} catch (err) {
			error = err instanceof Error ? err.message : 'Something went wrong. Please try again.';
			// Restore input so the user can retry
			inputText = trimmed;
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage(inputText);
		}
	}
</script>

<!--
  The outer div fills the available viewport height. The parent layout adds:
    nav (h-16 = 4rem) + main py-6 (1.5rem top + 1.5rem bottom) = 7rem total.
  So calc(100vh - 7rem) exactly fills the remaining space without overflow.
-->
<div class="flex flex-col" style="height: calc(100vh - 7rem);">
	<!-- Page header -->
	<div class="flex-shrink-0 border-b border-slate-200 bg-white px-6 py-4">
		<h1 class="text-2xl font-bold text-slate-900">Ask Meno</h1>
		<p class="mt-0.5 text-sm text-slate-500">
			Evidence-based information about perimenopause and menopause
		</p>
		<div
			class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700"
		>
			Educational information only — not medical advice. Always discuss health decisions with your
			healthcare provider.
		</div>
	</div>

	<!-- Messages / empty state -->
	<div class="flex-1 overflow-y-auto" bind:this={chatContainer}>
		{#if !hasMessages}
			<!-- Empty state: starter prompt grid -->
			<div class="p-6">
				<p class="mb-4 text-center text-sm text-slate-500">
					Start with a question, or choose one below:
				</p>
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					{#each STARTER_PROMPTS as prompt}
						<button
							onclick={() => sendMessage(prompt)}
							class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 active:bg-teal-100"
						>
							{prompt}
						</button>
					{/each}
				</div>
			</div>
		{:else}
			<!-- Message thread -->
			<div class="flex flex-col gap-5 p-6">
				{#each messages as message, i (i)}
					{#if message.role === 'user'}
						<div class="flex justify-end">
							<div
								class="max-w-[75%] rounded-2xl rounded-tr-sm bg-slate-700 px-4 py-3 text-sm leading-relaxed text-white"
							>
								{message.content}
							</div>
						</div>
					{:else}
						<div class="flex justify-start">
							<div class="max-w-[85%] rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm">
								<!-- Response text with inline citation superscripts -->
								<div class="text-sm leading-relaxed text-slate-800">
									{@html renderContent(message.content, message.citations)}
								</div>

								<!-- Citations list -->
								{#if message.citations.length > 0}
									<div class="mt-3 border-t border-slate-100 pt-3">
										<p class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
											Sources
										</p>
										<ol class="space-y-1">
											{#each message.citations as citation, j}
												<li class="text-xs text-slate-500">
													<span class="font-medium text-slate-600">[{j + 1}]</span>
													<a
														href={citation.url}
														target="_blank"
														rel="noopener noreferrer"
														class="ml-1 text-teal-600 hover:text-teal-800 hover:underline"
													>
														{citation.title || citation.url}
														{#if citation.section}
															<span class="text-slate-400"> — {citation.section}</span>
														{/if}
													</a>
												</li>
											{/each}
										</ol>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				{/each}

				<!-- Thinking indicator -->
				{#if loading}
					<div class="flex justify-start">
						<div
							class="rounded-2xl rounded-tl-sm bg-white px-4 py-3 text-sm text-slate-400 shadow-sm"
						>
							<span class="animate-pulse">Thinking…</span>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Error banner -->
	{#if error}
		<div class="flex-shrink-0 border-t border-red-200 bg-red-50 px-6 py-3 text-sm text-red-700">
			{error}
			<button onclick={() => (error = null)} class="ml-2 font-medium underline hover:no-underline">
				Dismiss
			</button>
		</div>
	{/if}

	<!-- Input area -->
	<div
		class="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-4"
		style="box-shadow: 0 -4px 12px rgba(0,0,0,0.05);"
	>
		<div class="flex items-end gap-3">
			<textarea
				bind:this={textareaEl}
				bind:value={inputText}
				oninput={adjustTextareaHeight}
				onkeydown={handleKeydown}
				placeholder="Ask a question about perimenopause or menopause…"
				rows="1"
				disabled={loading}
				class="flex-1 resize-none rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-400/20 disabled:opacity-60"
			></textarea>
			<button
				onclick={() => sendMessage(inputText)}
				disabled={!canSend}
				class="flex-shrink-0 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
			>
				Send
			</button>
		</div>
		<p class="mt-2 text-center text-xs text-slate-400">
			Enter to send &middot; Shift+Enter for new line
		</p>
	</div>
</div>

<style>
	/* Inline citation superscript links rendered via {@html} */
	:global(.citation-ref) {
		color: #0d9488; /* teal-600 */
		font-weight: 500;
		text-decoration: none;
	}
	:global(.citation-ref:hover) {
		color: #0f766e; /* teal-700 */
		text-decoration: underline;
	}
</style>
