<script lang="ts">
	import { tick, onMount } from 'svelte';
	import { superForm } from 'sveltekit-superforms/client';
	import { zod4 } from 'sveltekit-superforms/adapters';
	import { chatMessageSchema } from '$lib/schemas/chat';
	import { renderMarkdown, sanitizeMarkdownHtml } from '$lib/markdown';
	import { apiClient } from '$lib/api/client';
	import type { Citation, Message, ApiError } from '$lib/types';

	// =========================================================================
	// Props & Page Data
	// =========================================================================

	let { data } = $props();

	// =========================================================================
	// Constants
	// =========================================================================

	const FALLBACK_PROMPTS = [
		'What should I expect during menopause?',
		'What are my options for managing menopause symptoms?',
		'How can I prepare for conversations with my doctor?'
	];

	// =========================================================================
	// Superforms Setup
	// =========================================================================

	const form = superForm(data.form, {
		validators: zod4(chatMessageSchema),
		delayMs: 200,
	});

	const { form: formData, errors, enhance, submitting } = form;

	// =========================================================================
	// Component State
	// =========================================================================

	let messages = $state<Message[]>([]);
	let conversationId = $state<string | null>(null);

	let chatContainer = $state<HTMLDivElement | null>(null);
	let textareaEl = $state<HTMLTextAreaElement | null>(null);

	let isLoading = $state(false);
	let canSend = $derived($formData.message.trim().length > 0 && !isLoading);
	let hasMessages = $derived(messages.length > 0);
	let apiError = $state<string | null>(null);

	let suggestedPrompts = $state<string[]>([]);
	let loadingPrompts = $state(true);

	// =========================================================================
	// Load past messages when resuming from history, and load suggested prompts
	// =========================================================================

	async function loadSuggestedPrompts() {
		try {
			const response = await apiClient.get<{ prompts: string[] }>(
				'/api/chat/suggested-prompts'
			);
			suggestedPrompts = response.prompts;
		} catch (error) {
			console.error('Failed to load suggested prompts:', error);
			// Graceful fallback: show fallback prompts
			suggestedPrompts = FALLBACK_PROMPTS;
		} finally {
			loadingPrompts = false;
		}
	}

	onMount(async () => {
		// Load suggested prompts in parallel with resuming conversation
		await loadSuggestedPrompts();

		if (data.resumeId) {
			try {
				const response = await apiClient.get(
					`/api/chat/conversations/${data.resumeId}` as any
				);
				messages = response.messages;
				conversationId = data.resumeId;
			} catch (error) {
				const errorMsg = error instanceof Error && 'detail' in error
					? (error as ApiError).detail
					: 'Failed to load conversation history';
				apiError = errorMsg;
				console.error('Failed to load conversation:', error);
			}
		}
	});

	// =========================================================================
	// Auto-scroll when messages change
	// =========================================================================

	$effect(() => {
		const _dep = messages.length;
		tick().then(() => {
			chatContainer?.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
		});
	});

	// =========================================================================
	// Helpers
	// =========================================================================

	function adjustTextareaHeight() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
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
	 * Process:
	 * 1. Render markdown to HTML
	 * 2. Sanitize external links
	 * 3. Replace [Source N] markers with citation links
	 */
	function renderContent(content: string, citations: Citation[]): string {
		let html = renderMarkdown(content);
		html = sanitizeMarkdownHtml(html);

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

	// =========================================================================
	// Form Submission Handler
	// =========================================================================

	async function onSubmit() {
		const userMessage = $formData.message.trim();
		if (!userMessage) return;

		// Add user message to display
		messages = [...messages, { role: 'user', content: userMessage, citations: [] }];
		apiError = null;
		isLoading = true;

		// Update conversation_id in form if we have one
		if (conversationId) {
			$formData.conversation_id = conversationId;
		}

		// Scroll to bottom
		await tick();
		chatContainer?.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
		adjustTextareaHeight();

		// Make API call from client (where we have auth token)
		try {
			const response = await apiClient.post('/api/chat', {
				message: userMessage,
				...(conversationId && { conversation_id: conversationId }),
			});

			conversationId = response.conversation_id;
			messages = [
				...messages,
				{ role: 'assistant', content: response.message, citations: response.citations }
			];
			$formData.message = '';
		} catch (error) {
			const errorMsg = error instanceof Error && 'detail' in error
				? (error as ApiError).detail
				: error instanceof Error
					? error.message
					: 'Failed to get response. Please try again.';
			apiError = errorMsg;
			console.error('Chat API error:', error);
		} finally {
			isLoading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			onSubmit();
		}
	}

	// Populate quick prompts
	function selectPrompt(prompt: string) {
		$formData.message = prompt;
	}
</script>

<!-- Outer container fills viewport height -->
<div class="flex flex-col" style="height: calc(100vh - 7rem);">
	<!-- Page header -->
	<div class="flex-shrink-0 border-b border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-bold text-slate-900">Ask Meno</h1>
				<p class="mt-0.5 text-sm text-slate-500">
					Evidence-based information about perimenopause and menopause
				</p>
			</div>
			<a
				href="/ask/history"
				class="text-sm font-medium text-teal-600 hover:text-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 rounded px-2 py-1"
			>
				History
			</a>
		</div>
		<div class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
			Educational information only — not medical advice. Always discuss health decisions with your
			healthcare provider.
		</div>
	</div>

	<!-- Messages / empty state -->
	<div class="flex-1 overflow-y-auto" bind:this={chatContainer} aria-live="polite" aria-label="Chat messages">
		{#if !hasMessages}
			<!-- Empty state: starter prompts -->
			<div class="px-4 py-6 sm:px-6 lg:px-8">
				<p class="mb-4 text-center text-sm text-slate-500">
					Start with a question, or choose one below:
				</p>
				{#if loadingPrompts}
					<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
						{#each Array(6) as _}
							<div class="rounded-xl border border-slate-200 bg-white px-4 py-3 h-[60px] animate-pulse bg-slate-100" />
						{/each}
					</div>
				{:else if suggestedPrompts.length > 0}
					<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
						{#each suggestedPrompts as prompt (prompt)}
							<button
								type="button"
								onclick={() => selectPrompt(prompt)}
								class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 active:bg-teal-100"
							>
								{prompt}
							</button>
						{/each}
					</div>
				{:else}
					<!-- Fallback if suggestions failed to load -->
					<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
						{#each FALLBACK_PROMPTS as prompt}
							<button
								type="button"
								onclick={() => selectPrompt(prompt)}
								class="rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-colors hover:border-teal-300 hover:bg-teal-50 hover:text-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 active:bg-teal-100"
							>
								{prompt}
							</button>
						{/each}
					</div>
				{/if}
			</div>
		{:else}
			<!-- Message thread -->
			<div class="flex flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
				{#each messages as message, i (i)}
					{#if message.role === 'user'}
						<div class="flex justify-end">
							<div class="max-w-[75%] rounded-2xl rounded-tr-sm bg-slate-700 px-4 py-3 text-sm leading-relaxed text-white">
								{message.content}
							</div>
						</div>
					{:else}
						<div class="flex justify-start">
							<div class="max-w-[85%] rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm">
								<!-- Response text with citations -->
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
				{#if isLoading}
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

	<!-- Error messages -->
	{#if apiError || $errors.message}
		<div class="flex-shrink-0 border-t border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:px-6 lg:px-8" role="alert">
			{apiError || $errors.message}
			<button
				type="button"
				onclick={() => {
					apiError = null;
					$errors.message = undefined;
				}}
				class="ml-2 font-medium underline hover:no-underline"
			>
				Dismiss
			</button>
		</div>
	{/if}

	<!-- Form -->
	<form
		method="POST"
		action="?/chat"
		use:enhance
		class="flex-shrink-0 border-t border-slate-200 bg-white px-4 py-4 sm:px-6 lg:px-8"
		style="box-shadow: 0 -4px 12px rgba(0,0,0,0.05);"
	>
		<div class="flex items-end gap-3">
			<textarea
				bind:this={textareaEl}
				bind:value={$formData.message}
				oninput={adjustTextareaHeight}
				onkeydown={handleKeydown}
				name="message"
				placeholder="Ask a question about perimenopause or menopause…"
				rows="1"
				disabled={isLoading}
				class="flex-1 resize-none rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-teal-400 focus:outline-none focus:ring-2 focus:ring-teal-400/20 disabled:opacity-60"
				aria-invalid={apiError || $errors.message ? 'true' : 'false'}
				aria-describedby={apiError || $errors.message ? 'message-error' : undefined}
			></textarea>
			<button
				type="button"
				onclick={onSubmit}
				disabled={!canSend}
				class="flex-shrink-0 rounded-xl bg-teal-600 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40"
			>
				{isLoading ? 'Sending…' : 'Send'}
			</button>
		</div>
		<p class="mt-2 text-center text-xs text-slate-400">
			Enter to send &middot; Shift+Enter for new line
		</p>
	</form>
</div>

<style>
	/* Inline citation superscript links */
	:global(.citation-ref) {
		color: #0d9488;
		font-weight: 500;
		text-decoration: none;
	}
	:global(.citation-ref:hover) {
		color: #0f766e;
		text-decoration: underline;
	}

	/* Markdown rendering styles */
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
		list-style-position: outside;
		margin-left: 1.5rem;
		margin-bottom: 0.75rem;
	}

	:global(.message-content ol) {
		list-style-type: decimal;
		list-style-position: outside;
		margin-left: 1.5rem;
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
