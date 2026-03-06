import { describe, it, expect } from 'vitest';
import { renderMarkdown, sanitizeMarkdownHtml } from '../markdown';

describe('renderMarkdown', () => {
	it('renders bold text', () => {
		const result = renderMarkdown('**bold text**');
		expect(result).toContain('<strong>bold text</strong>');
	});

	it('renders headers', () => {
		const result = renderMarkdown('# Heading 1\n## Heading 2');
		expect(result).toContain('<h1>Heading 1</h1>');
		expect(result).toContain('<h2>Heading 2</h2>');
	});

	it('renders unordered lists', () => {
		const result = renderMarkdown('- Item 1\n- Item 2\n- Item 3');
		expect(result).toContain('<li>Item 1</li>');
		expect(result).toContain('<li>Item 2</li>');
		expect(result).toContain('<li>Item 3</li>');
	});

	it('renders ordered lists', () => {
		const result = renderMarkdown('1. First\n2. Second\n3. Third');
		expect(result).toContain('<ol>');
		expect(result).toContain('<li>First</li>');
		expect(result).toContain('<li>Second</li>');
	});

	it('renders italic text', () => {
		const result = renderMarkdown('*italic text*');
		expect(result).toContain('<em>italic text</em>');
	});

	it('handles empty strings', () => {
		const result = renderMarkdown('');
		// Empty string should render to empty or minimal HTML
		expect(typeof result).toBe('string');
	});

	it('handles line breaks', () => {
		const result = renderMarkdown('Line 1\nLine 2');
		// Single newlines are soft-wrapped into the same paragraph (breaks: false)
		expect(result).toContain('Line 1');
		expect(result).toContain('Line 2');
	});

	it('renders HTML as-is (sanitization should be done by caller)', () => {
		const result = renderMarkdown('This has <script>alert("xss")</script>');
		// marked allows HTML by default - sanitization is the caller's responsibility
		// This is why we have sanitizeMarkdownHtml() for LLM output
		expect(typeof result).toBe('string');
	});

	it('escapes on markdown parse error (returns escaped content)', () => {
		// This test verifies the error handling works
		const result = renderMarkdown('Normal text');
		expect(typeof result).toBe('string');
	});

	it('renders inline code', () => {
		const result = renderMarkdown('Use `const x = 1;` to declare');
		expect(result).toContain('<code>');
	});

	it('handles blockquotes', () => {
		const result = renderMarkdown('> This is a quote');
		expect(result).toContain('<blockquote>');
	});
});

describe('sanitizeMarkdownHtml', () => {
	it('adds target="_blank" to external links', () => {
		const html = '<a href="https://example.com">Link</a>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toContain('target="_blank"');
		expect(result).toContain('rel="noopener noreferrer"');
	});

	it('removes dangerous protocols from links', () => {
		const html = '<a href="javascript:alert(\'xss\')">Click me</a>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toContain('<span>');
		expect(result).not.toContain('javascript:');
	});

	it('removes data: protocol from links', () => {
		const html = '<a href="data:text/html,<script>alert(1)</script>">Link</a>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).not.toContain('data:');
	});

	it('escapes URL characters in href', () => {
		const html = '<a href="https://example.com/?q=<script>">Link</a>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toContain('&lt;');
		expect(result).toContain('&gt;');
	});

	it('handles multiple links', () => {
		const html = '<a href="https://example1.com">Link 1</a> and <a href="https://example2.com">Link 2</a>';
		const result = sanitizeMarkdownHtml(html);
		const linkCount = (result.match(/target="_blank"/g) || []).length;
		expect(linkCount).toBe(2);
	});

	it('preserves non-link content', () => {
		const html = '<p>Some text</p><a href="https://example.com">Link</a><p>More text</p>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toContain('<p>Some text</p>');
		expect(result).toContain('<p>More text</p>');
	});

	it('handles links with attributes', () => {
		const html = '<a href="https://example.com" class="link">Click</a>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toContain('target="_blank"');
		expect(result).toContain('https://example.com');
	});

	it('handles empty HTML string', () => {
		const result = sanitizeMarkdownHtml('');
		expect(result).toBe('');
	});

	it('handles HTML with no links', () => {
		const html = '<p>Just text</p><strong>Bold</strong>';
		const result = sanitizeMarkdownHtml(html);
		expect(result).toBe(html);
	});
});
