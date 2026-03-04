<script lang="ts">
	import { tick } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { renderMarkdown, sanitizeMarkdownHtml } from '$lib/markdown';

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
	 * Render markdown content with citations.
	 *
	 * Process steps:
	 * 1. Render markdown to HTML (handles bold, headers, lists, etc.)
	 * 2. Sanitize external links (add target="_blank", validate protocols)
	 * 3. Replace [Source N] markers with superscript citation links
	 *
	 * Security: URLs are validated to ensure they're http/https to prevent
	 * javascript: and data: URIs.
	 */
	function renderContent(content: string, citations: Citation[]): string {
		// 1. Render markdown to HTML
		let html = renderMarkdown(content);

		// 2. Sanitize external links
		html = sanitizeMarkdownHtml(html);

		// 3. Replace [Source N] markers with citation links
		html = html.replace(/\[Source (\d+)\]/g, (_match, n) => {
			const idx = parseInt(n, 10) - 1;
			if (idx >= 0 && idx < citations.length) {
				const url = escapeHtml(citations[idx].url);
				return `<sup><a href="${url}" target="_blank" rel="noopener noreferrer" class="citation-ref">[${n}]</a></sup>`;
			}
			return `<sup>[${n}]</sup>`;
		});

		return html;
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
	<div class="flex-shrink-0 border-b border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
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
	<div class="flex-1 overflow-y-auto" bind:this={chatContainer} aria-live="polite" aria-label="Chat messages">
		{#if !hasMessages}
			<!-- Empty state: starter prompt grid -->
			<div class="px-4 py-6 sm:px-6 lg:px-8">
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
			<div class="flex flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
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
								<div class="message-content text-sm leading-relaxed text-slate-800">
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
							role="status"
							aria-live="assertive"
							aria-label="Assistant is thinking"
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
		<div class="flex-shrink-0 border-t border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:px-6 lg:px-8">
			{error}
			<button onclick={() => (error = null)} class="ml-2 font-medium underline hover:no-underline">
				Dismiss
			</button>
		</div>
	{/if}

	<!-- Input area -->
	<div
		class="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8"
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

	/* Markdown rendering styles for message content */
	:global(.message-content h1) {
		font-size: 1.5rem;
		font-weight: bold;
		margin-top: 1rem;
		margin-bottom: 0.5rem;
	}

	:global(.message-content h2) {
		font-size: 1.25rem;
		font-weight: bold;
		margin-top: 0.875rem;
		margin-bottom: 0.5rem;
	}

	:global(.message-content h3) {
		font-size: 1.125rem;
		font-weight: bold;
		margin-top: 0.75rem;
		margin-bottom: 0.375rem;
	}

	:global(.message-content p) {
		margin-bottom: 0.75rem;
	}

	:global(.message-content ul) {
		list-style-type: disc;
		list-style-position: inside;
		margin-left: 1rem;
		margin-bottom: 0.75rem;
	}

	:global(.message-content ol) {
		list-style-type: decimal;
		list-style-position: inside;
		margin-left: 1rem;
		margin-bottom: 0.75rem;
	}

	:global(.message-content li) {
		margin-bottom: 0.25rem;
	}

	:global(.message-content code) {
		background-color: #f1f5f9;
		border-radius: 0.25rem;
		padding: 0.125rem 0.375rem;
		font-family: monospace;
		font-size: 0.875rem;
	}

	:global(.message-content pre) {
		background-color: #f1f5f9;
		border-radius: 0.5rem;
		padding: 1rem;
		overflow-x: auto;
		margin-bottom: 0.75rem;
	}

	:global(.message-content pre code) {
		background-color: transparent;
		padding: 0;
	}

	:global(.message-content blockquote) {
		border-left: 4px solid #cbd5e1;
		padding-left: 1rem;
		margin-left: 0;
		margin-bottom: 0.75rem;
		color: #64748b;
		font-style: italic;
	}

	:global(.message-content strong) {
		font-weight: 600;
	}

	:global(.message-content em) {
		font-style: italic;
	}

	:global(.message-content a) {
		color: #0d9488;
		text-decoration: underline;
	}

	:global(.message-content a:hover) {
		color: #0f766e;
	}
</style>
