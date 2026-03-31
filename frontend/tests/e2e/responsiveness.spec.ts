import { test, expect, viewports } from './fixtures';
import { seedTestData } from './seed';

interface ResponsivenessIssue {
	severity: 'critical' | 'medium' | 'low';
	title: string;
	description: string;
	measurement?: string;
}

interface TestResult {
	page: string;
	viewport: string;
	issues: ResponsivenessIssue[];
	passed: boolean;
}

const testResults: TestResult[] = [];

test.describe('Responsiveness Audit', () => {
	const pages = [
		{ path: '/dashboard', name: 'Dashboard' },
		{ path: '/log', name: 'Log Symptoms' },
		{ path: '/ask', name: 'Ask Meno' },
		{ path: '/providers', name: 'Providers' },
		{ path: '/export', name: 'Export' }
	];

	test('Login and seed data', async ({ page, loginIfNeeded }) => {
		// This test ensures we're logged in and data is seeded for subsequent tests
		await loginIfNeeded();

		// Get auth token for seeding
		const cookies = await page.context().cookies();
		const sessionCookie = cookies.find((c) => c.name.includes('session'));

		if (sessionCookie) {
			await seedTestData(page, sessionCookie.value);
		}

		// Verify we're logged in
		await page.goto('/dashboard');
		await expect(page).toHaveURL('/dashboard');
	});

	for (const pageConfig of pages) {
		for (const viewport of viewports) {
			test(`${pageConfig.name} - Responsive at ${viewport.name} (${viewport.width}×${viewport.height})`, async ({
				page,
				takeResponsiveScreenshots,
				loginIfNeeded
			}) => {
				const issues: ResponsivenessIssue[] = [];

				try {
					// Ensure logged in
					await loginIfNeeded();

					// Set viewport size
					await page.setViewportSize({ width: viewport.width, height: viewport.height });

					// Navigate to page
					await page.goto(pageConfig.path);
					await page.waitForLoadState('networkidle');

					// Give the page a moment to settle
					await page.waitForTimeout(500);

					// 1. Check for horizontal overflow
					const hasHorizontalScroll = await page.evaluate(() => {
						return document.documentElement.scrollWidth > document.documentElement.clientWidth;
					});

					if (hasHorizontalScroll) {
						const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
						const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);

						issues.push({
							severity: 'critical',
							title: 'Horizontal Overflow Detected',
							description: `Page content extends beyond viewport width`,
							measurement: `scrollWidth: ${scrollWidth}px, viewport: ${viewport.width}px`
						});
					}

					// 2. Check button and input sizes (should be ≥44px)
					const smallTouchTargets = await page.evaluate(() => {
						const issues: Array<{
							selector: string;
							height: number;
							width: number;
						}> = [];

						const elements = document.querySelectorAll(
							'button, input[type="button"], input[type="submit"], [role="button"]'
						);

						elements.forEach((el) => {
							const rect = el.getBoundingClientRect();
							// Only flag if element is visible
							if (rect.height > 0 && rect.width > 0) {
								if (rect.height < 44 || rect.width < 44) {
									issues.push({
										selector: el.className || el.tagName,
										height: Math.round(rect.height),
										width: Math.round(rect.width)
									});
								}
							}
						});

						return issues;
					});

					if (smallTouchTargets.length > 0) {
						issues.push({
							severity: 'medium',
							title: `${smallTouchTargets.length} Small Touch Targets`,
							description:
								'Some interactive elements are smaller than the recommended 44×44px minimum',
							measurement: smallTouchTargets
								.slice(0, 3)
								.map((t) => `${t.selector}: ${t.width}×${t.height}px`)
								.join(', ')
						});
					}

					// 3. Check for off-screen elements
					const offScreenElements = await page.evaluate((vpWidth) => {
						const issues: string[] = [];
						const elements = document.querySelectorAll('button, input, a, [role="button"]');

						elements.forEach((el) => {
							const rect = el.getBoundingClientRect();
							if (rect.width > 0 && rect.height > 0) {
								// Check if element extends beyond right edge
								if (rect.right > vpWidth + 5) {
									// 5px tolerance for rounding
									issues.push(
										`${el.tagName} extends ${Math.round(rect.right - vpWidth)}px beyond viewport`
									);
								}
								// Check if element is off-screen to the left
								if (rect.left < -5) {
									issues.push(`${el.tagName} off-screen to the left`);
								}
							}
						});

						return issues;
					}, viewport.width);

					if (offScreenElements.length > 0) {
						issues.push({
							severity: 'critical',
							title: `${offScreenElements.length} Off-Screen Elements`,
							description: 'Some interactive elements are positioned off-screen',
							measurement: offScreenElements.slice(0, 2).join('; ')
						});
					}

					// 4. Check text readability (font size audit on mobile)
					if (viewport.width <= 375) {
						const smallText = await page.evaluate(() => {
							const issues: string[] = [];
							const elements = document.querySelectorAll('p, span, button, label, a');

							// Sample check on first 50 elements
							Array.from(elements)
								.slice(0, 50)
								.forEach((el) => {
									const style = window.getComputedStyle(el);
									const fontSize = parseFloat(style.fontSize);

									if (fontSize < 14 && el.textContent?.trim()) {
										issues.push(`${el.tagName}: ${fontSize.toFixed(1)}px`);
									}
								});

							return issues;
						});

						if (smallText.length > 2) {
							issues.push({
								severity: 'medium',
								title: 'Small Font Sizes on Mobile',
								description: 'Some text elements are smaller than recommended 14px minimum',
								measurement: `${smallText.length} elements < 14px`
							});
						}
					}

					// 5. Check for layout shifts or overlapping content
					const layoutIssues = await page.evaluate(() => {
						const issues: string[] = [];

						// Check for common overflow properties
						const allElements = document.querySelectorAll('*');
						let overflowCount = 0;

						allElements.forEach((el) => {
							const style = window.getComputedStyle(el);
							if (style.overflow === 'hidden' && el.scrollHeight > el.clientHeight) {
								overflowCount++;
							}
						});

						if (overflowCount > 5) {
							issues.push(`${overflowCount} elements with hidden overflow and cut-off content`);
						}

						return issues;
					});

					if (layoutIssues.length > 0) {
						issues.push({
							severity: 'low',
							title: 'Potential Content Clipping',
							description: 'Some elements may have content clipped by overflow:hidden',
							measurement: layoutIssues[0]
						});
					}

					// Take screenshot
					await takeResponsiveScreenshots(pageConfig.path);

					// Store results
					testResults.push({
						page: pageConfig.name,
						viewport: viewport.name,
						issues,
						passed: issues.filter((i) => i.severity === 'critical').length === 0
					});

					// Assert no critical issues
					const criticalIssues = issues.filter((i) => i.severity === 'critical');
					expect(criticalIssues).toHaveLength(
						0,
						`Critical responsiveness issues on ${pageConfig.name} at ${viewport.name}:\n${criticalIssues
							.map((i) => `- ${i.title}: ${i.description}`)
							.join('\n')}`
					);
				} catch (error) {
					testResults.push({
						page: pageConfig.name,
						viewport: viewport.name,
						issues: [
							{
								severity: 'critical',
								title: 'Test Error',
								description: String(error)
							}
						],
						passed: false
					});
					throw error;
				}
			});
		}
	}

	test.afterAll(async () => {
		// Generate report only after all tests complete
		console.log(
			`\n📊 Generating responsiveness audit report from ${testResults.length} test results...`
		);
		await generateResponsivenessReport(testResults);
	});
});

async function generateResponsivenessReport(results: TestResult[]): Promise<void> {
	const fs = await import('fs').then((m) => m.promises);
	const path = await import('path');

	const criticalCount = results.reduce(
		(sum, r) => sum + r.issues.filter((i) => i.severity === 'critical').length,
		0
	);
	const mediumCount = results.reduce(
		(sum, r) => sum + r.issues.filter((i) => i.severity === 'medium').length,
		0
	);
	const lowCount = results.reduce(
		(sum, r) => sum + r.issues.filter((i) => i.severity === 'low').length,
		0
	);

	const passedCount = results.filter((r) => r.passed).length;

	// Executive summary
	let summary = `# Responsiveness Audit Report

**Generated:** ${new Date().toISOString()}

## Executive Summary

- **Total Tests:** ${results.length}
- **Passed:** ${passedCount}/${results.length}
- **Critical Issues:** 🔴 ${criticalCount}
- **Medium Issues:** 🟡 ${mediumCount}
- **Low Issues:** 🟢 ${lowCount}

${criticalCount > 0 ? `\n⚠️ **${criticalCount} critical issues found that require immediate attention.**\n` : '\n✅ **No critical issues detected.**\n'}

---

## Test Results by Page

| Page | Mobile | Mobile-L | Tablet | Desktop |
|------|--------|----------|--------|---------|
${Object.entries(
	results.reduce((acc: Record<string, string[]>, r) => {
		if (!acc[r.page]) acc[r.page] = [];
		const status = r.passed ? '✅' : '❌';
		acc[r.page].push(status);
		return acc;
	}, {})
)
	.map(([page, statuses]) => `| ${page} | ${statuses.join(' | ')} |`)
	.join('\n')}

---

## Detailed Findings

`;

	// Detailed findings per page
	const pages = [...new Set(results.map((r) => r.page))];

	for (const page of pages) {
		const pageResults = results.filter((r) => r.page === page);
		const pageIssues = pageResults.flatMap((r) => r.issues);

		summary += `\n### ${page}\n`;

		// Screenshots (in root docs directory)
		const screenshotDir = path.join(
			process.cwd(),
			'..',
			'..',
			'docs/screenshots/responsiveness',
			page.toLowerCase().replace(/\\s+/g, '-')
		);

		summary += `\n**Screenshots:**\n`;
		for (const viewport of viewports) {
			const screenshotPath = path.join(screenshotDir, `${viewport.name}.png`);
			try {
				await fs.stat(screenshotPath);
				const relPath = path.relative(path.join(process.cwd(), '..', '..', 'docs'), screenshotPath);
				summary += `\n- **${viewport.name}** (${viewport.width}×${viewport.height})\n  ![${viewport.name}](${relPath})\n`;
			} catch {
				// Screenshot doesn't exist yet
			}
		}

		// Issues for this page
		if (pageIssues.length > 0) {
			summary += `\n**Issues Found:**\n`;

			const byViewport = pageResults.reduce((acc: Record<string, ResponsivenessIssue[]>, r) => {
				acc[r.viewport] = r.issues;
				return acc;
			}, {});

			for (const [viewport, issues] of Object.entries(byViewport)) {
				if (issues.length > 0) {
					summary += `\n#### ${viewport}\n`;
					for (const issue of issues) {
						const emoji =
							issue.severity === 'critical' ? '🔴' : issue.severity === 'medium' ? '🟡' : '🟢';
						summary += `\n${emoji} **${issue.title}**\n`;
						summary += `   ${issue.description}\n`;
						if (issue.measurement) {
							summary += `   _Measurement: ${issue.measurement}_\n`;
						}
					}
				}
			}
		} else {
			summary += `\n✅ No issues detected\n`;
		}

		summary += '\n---\n';
	}

	// Issue catalog
	summary += `\n## Issue Catalog\n\n`;

	const issuesByType = new Map<string, ResponsivenessIssue[]>();
	results.forEach((r) => {
		r.issues.forEach((i) => {
			if (!issuesByType.has(i.title)) {
				issuesByType.set(i.title, []);
			}
			issuesByType.get(i.title)!.push(i);
		});
	});

	if (issuesByType.size === 0) {
		summary += `✅ No responsive design issues detected.\n`;
	} else {
		for (const [title, issues] of issuesByType.entries()) {
			const emoji =
				issues[0].severity === 'critical' ? '🔴' : issues[0].severity === 'medium' ? '🟡' : '🟢';
			summary += `\n### ${emoji} ${title}\n`;
			summary += `**Severity:** ${issues[0].severity}\n\n`;
			summary += `Found in ${
				new Set(
					results
						.filter((r) => r.issues.some((i) => i.title === title))
						.map((r) => `${r.page} (${r.viewport})`)
				).size
			} locations\n`;
		}
	}

	// Write report to project docs directory
	const reportPath = path.join(process.cwd(), '..', 'docs/RESPONSIVENESS_AUDIT.md');

	try {
		await fs.mkdir(path.dirname(reportPath), { recursive: true });
	} catch (e) {
		// Directory exists
	}

	await fs.writeFile(reportPath, summary, 'utf-8');
	console.log(`\n✅ Responsiveness audit report saved to: ${reportPath}`);
}
