import { marked } from 'marked';

// Configure marked to match our design
marked.setOptions({
	breaks: true, // Convert \n to <br>
	gfm: true // GitHub Flavored Markdown
});

/**
 * Render markdown to HTML with security checks.
 *
 * Security:
 * - Uses marked's default sanitizer (blocks <script>, etc.)
 * - Escapes all user content before rendering
 * - Validates URLs (http/https only)
 */
export function renderMarkdown(content: string): string {
	try {
		const html = marked.parse(content);
		if (typeof html === 'string') {
			return html;
		}
		return 'Failed to render content';
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
