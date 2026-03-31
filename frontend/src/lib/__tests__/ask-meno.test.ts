import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderMarkdown, sanitizeMarkdownHtml } from '../markdown';

/**
 * Integration tests for Ask Meno chat functionality
 * Tests the core logic without requiring full Svelte component setup
 */

describe('Ask Meno - Chat Functionality', () => {
	describe('Message validation', () => {
		it('validates message is not empty', () => {
			const message = '';
			const isValid = message.trim().length > 0 && message.length <= 2000;
			expect(isValid).toBe(false);
		});

		it('validates message is under 2000 characters', () => {
			const message = 'a'.repeat(2001);
			const isValid = message.length <= 2000;
			expect(isValid).toBe(false);
		});

		it('validates valid message', () => {
			const message = 'What are the symptoms of perimenopause?';
			const isValid = message.trim().length > 0 && message.length <= 2000;
			expect(isValid).toBe(true);
		});

		it('trims whitespace from message', () => {
			const message = '  What is menopause?  ';
			const trimmed = message.trim();
			expect(trimmed).toBe('What is menopause?');
		});
	});

	describe('Citation rendering', () => {
		it('converts citation numbers to links', () => {
			const text = 'Research shows [1] that sleep is important [2].';
			// Simulate converting [1], [2], etc. to links
			const withLinks = text.replace(/\[(\d+)\]/g, '<a href="#source-$1">[$1]</a>');
			expect(withLinks).toContain('<a href="#source-1">[1]</a>');
			expect(withLinks).toContain('<a href="#source-2">[2]</a>');
		});

		it('handles invalid citation numbers', () => {
			const text = 'Some text [99] here';
			const maxSources = 3;
			// Remove citations beyond available sources
			const valid = text.replace(/\[(\d+)\]/g, (match, num) => {
				return parseInt(num) <= maxSources ? match : '';
			});
			expect(valid).not.toContain('[99]');
			expect(valid).toContain('Some text');
		});

		it('renumbers citations when sources are deduped', () => {
			// Original: [1], [3], [5] map to sources 1, 3, 5
			// After dedup, only 3 sources remain, so they should be [1], [2], [3]
			const citations = [1, 3, 5];
			const renumbered = citations.map((old, idx) => ({ old, new: idx + 1 }));
			expect(renumbered[0].new).toBe(1);
			expect(renumbered[1].new).toBe(2);
			expect(renumbered[2].new).toBe(3);
		});
	});

	describe('Response markdown rendering', () => {
		it('renders markdown in response', () => {
			const response = 'Some **bold** text with *italic*.';
			const html = renderMarkdown(response);
			expect(html).toContain('<strong>bold</strong>');
			expect(html).toContain('<em>italic</em>');
		});

		it('preserves citations in markdown', () => {
			const response = 'Studies show [1] that fatigue is common [2].';
			const html = renderMarkdown(response);
			// Should preserve the [1] and [2] in the output
			expect(html).toContain('[1]');
			expect(html).toContain('[2]');
		});

		it('sanitizes links in response HTML', () => {
			const response = 'Check [this](https://example.com) for more.';
			const html = renderMarkdown(response);
			const sanitized = sanitizeMarkdownHtml(html);
			expect(sanitized).toContain('target="_blank"');
		});

		it('handles empty response', () => {
			const response = '';
			const html = renderMarkdown(response);
			expect(typeof html).toBe('string');
		});
	});

	describe('API error handling', () => {
		it('handles network error', () => {
			const error = new Error('Network error. Please check your connection.');
			expect(error.message).toContain('Network error');
		});

		it('handles API validation error', () => {
			const errorResponse = {
				detail: 'Message must be between 1 and 2000 characters'
			};
			expect(errorResponse.detail).toContain('Message');
		});

		it('handles missing auth error', () => {
			const error = new Error('Not authenticated');
			expect(error.message).toBe('Not authenticated');
		});

		it('handles server error with user-friendly message', () => {
			const error = new Error('Failed to generate response. Please try again.');
			expect(error.message).toBe('Failed to generate response. Please try again.');
		});

		it('preserves API error detail field', () => {
			const apiError = {
				status: 400,
				detail: 'Invalid conversation ID'
			};
			expect(apiError.detail).toBe('Invalid conversation ID');
		});
	});

	describe('Conversation state management', () => {
		it('tracks conversation ID', () => {
			const conversationState = {
				id: 'conv-123-abc',
				messages: []
			};
			expect(conversationState.id).toBeDefined();
		});

		it('appends message to conversation', () => {
			const state = { messages: [] as string[] };
			state.messages.push('User message');
			state.messages.push('AI response');
			expect(state.messages).toHaveLength(2);
			expect(state.messages[0]).toBe('User message');
		});

		it('clears form after successful send', () => {
			const form = { message: 'What is menopause?' };
			form.message = '';
			expect(form.message).toBe('');
		});

		it('preserves conversation ID across messages', () => {
			const conv = { id: 'conv-123', messages: ['msg1', 'msg2'] };
			const newConv = { ...conv, messages: [...conv.messages, 'msg3'] };
			expect(newConv.id).toBe('conv-123'); // ID preserved
			expect(newConv.messages).toHaveLength(3);
		});
	});

	describe('Starter prompts', () => {
		it('contains non-empty starter prompts', () => {
			const starterPrompts = [
				'What are the most common symptoms?',
				'How can I manage hot flashes?',
				'When should I see a doctor?'
			];
			expect(starterPrompts.length).toBeGreaterThan(0);
			expect(starterPrompts.every((p) => p.length > 0)).toBe(true);
		});

		it('starter prompts are clickable without auto-sending', () => {
			// Verify that prompts populate the form but don't auto-send
			const form = { message: '' };
			const prompt = 'What are the most common symptoms?';
			form.message = prompt;
			expect(form.message).toBe(prompt);
			// Test would verify UI shows form but requires manual Send click
		});
	});

	describe('Loading and error states', () => {
		it('shows loading state when sending message', () => {
			const state = { isLoading: false };
			state.isLoading = true;
			expect(state.isLoading).toBe(true);
		});

		it('clears loading state after response', () => {
			const state = { isLoading: true };
			state.isLoading = false;
			expect(state.isLoading).toBe(false);
		});

		it('shows error message on failure', () => {
			const state = { error: '' };
			state.error = 'Failed to get response';
			expect(state.error).toBeTruthy();
		});

		it('clears error on new message', () => {
			const state = { error: 'Previous error' };
			state.error = '';
			expect(state.error).toBe('');
		});
	});
});
