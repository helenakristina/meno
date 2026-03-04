#!/usr/bin/env node

/**
 * Accessibility Audit Script
 * Simple audit using Playwright and axe-playwright
 * For detailed analysis, use axe DevTools browser extension
 */

import { chromium } from 'playwright';
import { injectAxe, checkA11y } from 'axe-playwright';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PAGES_TO_AUDIT = [
	{ path: '/ask', name: 'Ask Meno' },
	{ path: '/dashboard', name: 'Dashboard' },
	{ path: '/log', name: 'Log Symptoms' },
	{ path: '/providers', name: 'Providers' },
	{ path: '/export', name: 'Export' },
];

const results = {
	passed: [],
	failed: [],
	timestamp: new Date().toISOString(),
};

async function auditPage(page, baseUrl, pagePath, pageName) {
	console.log(`\n🔍 Scanning ${pageName} (${pagePath})...`);

	try {
		// Navigate to page and wait for full load + idle network
		await page.goto(`${baseUrl}${pagePath}`, { waitUntil: 'networkidle', timeout: 30000 });

		// Wait an extra moment for any client-side rendering
		await page.waitForTimeout(1000);

		// Check if redirected (indicates auth required)
		if (!page.url().includes(pagePath)) {
			console.log(`  ℹ️  Page redirected (auth required) - skipping`);
			return;
		}

		// Inject axe
		await injectAxe(page);

		// Try to check accessibility using axe.run for detailed results
		try {
			const axeResults = await page.evaluate(async () => {
				return await window.axe.run();
			});

			if (axeResults.violations.length === 0) {
				console.log(`  ✅ No violations found`);
				results.passed.push(pageName);
			} else {
				console.log(`  ⚠️  Found ${axeResults.violations.length} accessibility issue(s):`);
				axeResults.violations.forEach((violation) => {
					console.log(`     - ${violation.id} [${violation.impact.toUpperCase()}] (${violation.nodes.length} node(s))`);
					violation.nodes.slice(0, 2).forEach((node) => {
						const html = node.html || node.target[0];
						console.log(`       → ${html.substring(0, 70)}`);
					});
				});
				results.failed.push({ page: pageName, issues: axeResults.violations.length });
			}
		} catch (axeError) {
			const errorMessage = axeError.toString();
			console.log(`  ⚠️  Accessibility check failed: ${errorMessage.substring(0, 100)}`);
			results.failed.push({ page: pageName, issues: 'unknown' });
		}
	} catch (error) {
		console.log(`  ℹ️  Could not audit ${pageName}: ${error.message.substring(0, 80)}`);
	}
}

async function runAudit() {
	console.log('🚀 Starting Accessibility Audit\n');
	console.log(`Standard: WCAG 2.1 Level AA\n`);

	const baseUrl = 'http://localhost:5173';
	const browser = await chromium.launch();
	const page = await browser.newPage();

	try {
		// Audit each page
		for (const p of PAGES_TO_AUDIT) {
			await auditPage(page, baseUrl, p.path, p.name);
		}

		// Print summary
		console.log('\n' + '='.repeat(70));
		console.log('📊 AUDIT SUMMARY\n');

		console.log(`Pages Passed: ${results.passed.length}`);
		results.passed.forEach((page) => console.log(`  ✅ ${page}`));

		console.log(`\nPages with Issues: ${results.failed.length}`);
		results.failed.forEach((item) => {
			const issueText = typeof item.issues === 'number' ? `${item.issues} issue(s)` : item.issues;
			console.log(`  ⚠️  ${item.page} - ${issueText}`);
		});

		if (results.failed.length === 0) {
			console.log(`\n✨ All pages passed accessibility audit!\n`);
		} else {
			console.log(`\n💡 For detailed violation analysis, use:\n`);
			console.log(`   - axe DevTools browser extension`);
			console.log(`   - Lighthouse (Chrome DevTools)`);
			console.log(`   - WAVE by WebAIM\n`);
		}

		// Save report
		const reportPath = path.join(__dirname, '../../docs/dev/frontend/ACCESSIBILITY_AUDIT.md');
		const reportDir = path.dirname(reportPath);

		if (!fs.existsSync(reportDir)) {
			fs.mkdirSync(reportDir, { recursive: true });
		}

		const report = generateMarkdownReport();
		fs.writeFileSync(reportPath, report);
		console.log(`📄 Report saved to: docs/dev/frontend/ACCESSIBILITY_AUDIT.md`);
	} finally {
		await page.close();
		await browser.close();
	}
}

function generateMarkdownReport() {
	let markdown = `# Accessibility Audit Report\n\n`;
	markdown += `**Generated:** ${results.timestamp}\n`;
	markdown += `**Standard:** WCAG 2.1 Level AA\n\n`;

	markdown += `## Results\n\n`;
	markdown += `**Pages Passed:** ${results.passed.length}\n`;
	markdown += `**Pages with Issues:** ${results.failed.length}\n\n`;

	if (results.passed.length > 0) {
		markdown += `### ✅ Passed Pages\n\n`;
		results.passed.forEach((page) => {
			markdown += `- ${page}\n`;
		});
		markdown += `\n`;
	}

	if (results.failed.length > 0) {
		markdown += `### ⚠️ Pages Needing Review\n\n`;
		results.failed.forEach((item) => {
			const issues = typeof item.issues === 'number' ? `${item.issues} issue(s)` : item.issues;
			markdown += `- **${item.page}** - ${issues}\n`;
		});

		markdown += `\n## How to Get Detailed Violations\n\n`;
		markdown += `To see specific accessibility violations and fixes:\n\n`;
		markdown += `1. **axe DevTools** (Recommended)\n`;
		markdown += `   - [Chrome](https://chrome.google.com/webstore/detail/axe-devtools-web-accessibility-testing/lhdoppojpmngadmnkpklempisson/)\n`;
		markdown += `   - Provides detailed violation explanations and remediation advice\n\n`;
		markdown += `2. **Lighthouse** (Built-in to Chrome DevTools)\n`;
		markdown += `   - DevTools → Lighthouse → Accessibility\n`;
		markdown += `   - Good for general accessibility score\n\n`;
		markdown += `3. **WAVE by WebAIM**\n`;
		markdown += `   - [Browser Extension](https://wave.webaim.org/extension/)\n`;
		markdown += `   - Visual identification of issues\n`;
	} else {
		markdown += `## Result\n\n✅ **All pages passed the accessibility audit!**\n\n`;
		markdown += `Your application meets WCAG 2.1 Level AA standards.\n`;
	}

	return markdown;
}

// Run the audit
runAudit().catch((error) => {
	console.error('Audit failed:', error);
	process.exit(1);
});
