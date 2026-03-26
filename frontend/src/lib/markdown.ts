import { marked } from 'marked';
import DOMPurify from 'dompurify';

// Configure marked to match our design
marked.setOptions({
	breaks: false, // Don't convert \n to <br> (breaks ordered lists)
	gfm: true // GitHub Flavored Markdown
});

// Allowlist of tags and attributes permitted in rendered markdown.
// Kept intentionally narrow — only what our UI actually emits.
// Citation links rely on href/class/target/rel; data-citation-id is
// included so future citation link enhancements survive sanitization.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const DOMPURIFY_CONFIG: Record<string, any> = {
	ALLOWED_TAGS: [
		'p',
		'a',
		'strong',
		'em',
		'ul',
		'ol',
		'li',
		'code',
		'pre',
		'sup',
		'br',
		'h1',
		'h2',
		'h3',
		'blockquote'
	],
	ALLOWED_ATTR: ['href', 'class', 'target', 'rel', 'data-citation-id']
};

/**
 * Render markdown to HTML with security checks.
 *
 * Security:
 * - Passes marked output through DOMPurify with an explicit tag/attr allowlist
 * - marked does NOT sanitize by design; DOMPurify is the authoritative sanitizer
 * - Escapes all user content on fallback path
 * - Validates URLs (http/https only) in sanitizeMarkdownHtml
 */
export function renderMarkdown(content: string): string {
	try {
		const raw = marked.parse(content);
		if (typeof raw !== 'string') {
			return 'Failed to render content';
		}
		return DOMPurify.sanitize(raw, DOMPURIFY_CONFIG);
	} catch (error) {
		console.error('Markdown rendering error:', error);
		return escapeHtml(content); // Fallback to plain text
	}
}

/**
 * Sanitize links in rendered markdown.
 *
 * This is called AFTER markdown rendering to:
 * - Add target="_blank" to external links
 * - Validate URLs (http/https only)
 * - Escape dangerous protocols
 */
export function sanitizeMarkdownHtml(html: string): string {
	// Add target="_blank" and validation to links
	return html.replace(/<a\s+href="([^"]*)"[^>]*>/g, (match, url) => {
		try {
			const parsed = new URL(url);
			if (!['http:', 'https:'].includes(parsed.protocol)) {
				return '<span>';
			}
		} catch {
			return '<span>';
		}
		return `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">`;
	});
}

function escapeHtml(str: string): string {
	return str
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}
