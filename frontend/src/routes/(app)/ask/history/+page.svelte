<script lang="ts">
	import { onMount } from 'svelte';
	import { apiClient } from '$lib/api/client';
	import { ErrorBanner } from '$lib/components/shared';
	import type { Conversation } from '$lib/types';
	import type { ApiError } from '$lib/types/api';

	// =========================================================================
	// State
	// =========================================================================

	let conversations = $state<Conversation[]>([]);
	let total = $state(0);
	let hasMore = $state(false);
	let offset = $state(0);
	let limit = $state(20);

	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state<string | null>(null);
	let pendingDeleteId = $state<string | null>(null); // Tracks inline confirm step

	// =========================================================================
	// Load conversations on mount
	// =========================================================================

	onMount(async () => {
		await fetchConversations();
	});

	// =========================================================================
	// API calls
	// =========================================================================

	async function fetchConversations() {
		loading = true;
		error = null;

		try {
			const response = await apiClient.get('/api/chat/conversations', {
				limit,
				offset
			});

			conversations = response.conversations;
			total = response.total;
			hasMore = response.has_more;
		} catch (e) {
			const apiError = e as ApiError;
			error = apiError.detail || 'Failed to load conversations';
			console.error('Failed to load conversations:', e);
		} finally {
			loading = false;
		}
	}

	async function loadMore() {
		if (loadingMore || !hasMore) return;

		loadingMore = true;
		error = null;
		const newOffset = offset + limit;

		try {
			const response = await apiClient.get('/api/chat/conversations', {
				limit,
				offset: newOffset
			});

			conversations = [...conversations, ...response.conversations];
			total = response.total;
			hasMore = response.has_more;
			offset = newOffset;
		} catch (e) {
			const apiError = e as ApiError;
			error = apiError.detail || 'Failed to load more conversations';
			console.error('Failed to load more conversations:', e);
		} finally {
			loadingMore = false;
		}
	}

	async function deleteConversation(conversationId: string) {
		if (pendingDeleteId === conversationId) {
			// Confirm step — actually delete
			pendingDeleteId = null;
			error = null;

			try {
				await apiClient.delete(`/api/chat/conversations/${conversationId}` as any);

				// Remove from list optimistically
				conversations = conversations.filter((c) => c.id !== conversationId);
				total = Math.max(0, total - 1);
			} catch (e) {
				const apiError = e as ApiError;
				error = apiError.detail || 'Failed to delete conversation';
				console.error('Failed to delete conversation:', e);

				// Re-fetch to sync state with server
				await fetchConversations();
			}
		} else {
			// First click — show confirmation
			pendingDeleteId = conversationId;
		}
	}

	// =========================================================================
	// Helpers
	// =========================================================================

	function formatDate(dateString: string): string {
		const date = new Date(dateString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

		if (diffDays === 0) {
			// Today
			return date.toLocaleTimeString('en-US', {
				hour: 'numeric',
				minute: '2-digit'
			});
		} else if (diffDays === 1) {
			return 'Yesterday';
		} else if (diffDays < 7) {
			return `${diffDays} days ago`;
		} else if (diffDays < 30) {
			const weeks = Math.floor(diffDays / 7);
			return `${weeks} week${weeks > 1 ? 's' : ''} ago`;
		} else if (diffDays < 365) {
			const months = Math.floor(diffDays / 30);
			return `${months} month${months > 1 ? 's' : ''} ago`;
		}

		// Fallback: short date
		return date.toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric'
		});
	}

	function truncateTitle(title: string, maxLength: number = 80): string {
		if (title.length <= maxLength) return title;
		return title.substring(0, maxLength) + '…';
	}
</script>

<div class="min-h-screen bg-neutral-50 px-4 py-8 sm:px-6 lg:px-8">
	<div class="mx-auto max-w-4xl">
		<!-- Header -->
		<div class="mb-8">
			<h1 class="text-3xl font-bold text-neutral-800">Conversation History</h1>
			<p class="mt-2 text-neutral-600">View and manage your Ask Meno conversations</p>
		</div>

		<!-- Error Message -->
		{#if error}
			<div class="mb-6">
				<ErrorBanner message={error} onRetry={() => { error = null; fetchConversations(); }} />
			</div>
		{/if}

		<!-- Loading State -->
		{#if loading}
			<div class="space-y-3">
				{#each { length: 3 } as _}
					<div class="animate-pulse rounded-lg border border-neutral-200 bg-white p-4">
						<div class="h-4 w-3/4 rounded bg-neutral-200"></div>
						<div class="mt-3 h-3 w-1/2 rounded bg-neutral-100"></div>
					</div>
				{/each}
			</div>
		{:else if conversations.length === 0}
			<!-- Empty State -->
			<div class="rounded-lg border border-dashed border-neutral-300 bg-white px-8 py-16 text-center">
				<div class="mb-4 text-4xl">💬</div>
				<h2 class="text-lg font-semibold text-neutral-800">No conversations yet</h2>
				<p class="mt-2 text-neutral-600">Start your first Ask Meno conversation to see it here.</p>
				<a
					href="/ask"
					class="mt-6 inline-block rounded-lg bg-primary-500 px-6 py-3 font-semibold text-white hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
				>
					Ask Meno a Question
				</a>
			</div>
		{:else}
			<!-- Conversation List -->
			<div class="space-y-3">
				{#each conversations as conversation (conversation.id)}
					<div class="flex items-stretch gap-4 rounded-lg border border-neutral-200 bg-white hover:border-neutral-300 hover:shadow-sm transition-all">
						<!-- Main Content (clickable for resume) -->
						<a
							href="/ask?resume={conversation.id}"
							class="flex flex-1 flex-col justify-center gap-2 px-4 py-4 text-left hover:text-primary-700"
						>
							<h3 class="font-semibold text-neutral-800">
								{truncateTitle(conversation.title)}
							</h3>
							<div class="flex items-center gap-3 text-sm text-neutral-600">
								<span>{formatDate(conversation.created_at)}</span>
								<span>•</span>
								<span>{conversation.message_count} message{conversation.message_count !== 1 ? 's' : ''}</span>
							</div>
						</a>

						<!-- Delete Button -->
						<div class="flex items-center px-4 py-4">
							{#if pendingDeleteId === conversation.id}
								<!-- Confirm State -->
								<div class="flex gap-2">
									<button
										onclick={() => deleteConversation(conversation.id)}
										class="inline-flex items-center justify-center h-10 w-10 rounded-md bg-danger-light text-danger hover:bg-danger hover:text-white focus:outline-none focus:ring-2 focus:ring-danger focus:ring-offset-2"
										aria-label="Confirm delete"
										title="Confirm delete"
									>
										✓
									</button>
									<button
										onclick={() => {
											pendingDeleteId = null;
										}}
										class="inline-flex items-center justify-center h-10 w-10 rounded-md bg-neutral-100 text-neutral-600 hover:bg-neutral-200 focus:outline-none focus:ring-2 focus:ring-neutral-400 focus:ring-offset-2"
										aria-label="Cancel"
										title="Cancel"
									>
										✕
									</button>
								</div>
							{:else}
								<!-- Delete Button -->
								<button
									onclick={() => deleteConversation(conversation.id)}
									class="inline-flex items-center justify-center h-10 w-10 rounded-md text-neutral-400 hover:bg-danger-light hover:text-danger focus:outline-none focus:ring-2 focus:ring-danger focus:ring-offset-2 transition-colors"
									aria-label="Delete conversation"
									title="Delete conversation"
								>
									🗑️
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>

			<!-- Load More Button -->
			{#if hasMore}
				<div class="mt-6 flex justify-center">
					<button
						onclick={loadMore}
						disabled={loadingMore}
						class="rounded-lg border border-neutral-300 bg-white px-6 py-3 font-semibold text-neutral-700 hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
					>
						{loadingMore ? 'Loading...' : 'Load More'}
					</button>
				</div>
			{/if}

			<!-- Pagination Info -->
			<div class="mt-6 text-center text-sm text-neutral-600">
				Showing {conversations.length} of {total} conversation{total !== 1 ? 's' : ''}
			</div>
		{/if}
	</div>
</div>
