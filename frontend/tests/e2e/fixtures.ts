import { test as base, Page } from '@playwright/test';

export interface TestContext {
	page: Page;
	loginIfNeeded: () => Promise<void>;
	takeResponsiveScreenshots: (pagePath: string) => Promise<void>;
}

export const viewports = [
	{ name: 'mobile', width: 375, height: 667 },
	{ name: 'mobile-landscape', width: 667, height: 375 },
	{ name: 'tablet', width: 768, height: 1024 },
	{ name: 'desktop', width: 1440, height: 900 },
];

export const test = base.extend<TestContext>({
	loginIfNeeded: async ({ page }, use) => {
		let isLoggedIn = false;

		const login = async () => {
			if (isLoggedIn) return;

			// Navigate to login page
			await page.goto('/login');
			await page.waitForLoadState('networkidle');

			// Fill in credentials
			const emailInput = page.locator('input[type="email"]');
			const passwordInput = page.locator('input[type="password"]');
			const submitButton = page.locator('button[type="submit"]');

			await emailInput.fill('helena@example.com');
			await passwordInput.fill('testing');

			// Submit form and wait for navigation
			await submitButton.click();
			await page.waitForURL('**/dashboard**', { timeout: 30000 });

			isLoggedIn = true;
		};

		await use(login);
	},

	takeResponsiveScreenshots: async ({ page }, use) => {
		const captureScreenshots = async (pagePath: string) => {
			// Create screenshots directory if needed
			const fs = await import('fs').then((m) => m.promises);
			const path = await import('path');

			// Screenshots go to root docs/screenshots/responsiveness/ directory
			const screenshotDir = path.join(
				process.cwd(),
				'..',
				'..',
				'docs/screenshots/responsiveness',
				pagePath.replace(/\//g, '-').slice(1) || 'home'
			);

			try {
				await fs.mkdir(screenshotDir, { recursive: true });
			} catch (e) {
				// Directory already exists
			}

			// Navigate to page
			await page.goto(pagePath);
			await page.waitForLoadState('networkidle');

			// Take screenshot at each viewport
			for (const viewport of viewports) {
				await page.setViewportSize({ width: viewport.width, height: viewport.height });
				await page.waitForTimeout(500); // Brief wait for layout to settle

				const filename = path.join(screenshotDir, `${viewport.name}.png`);
				await page.screenshot({ path: filename, fullPage: false });
			}
		};

		await use(captureScreenshots);
	},
});

export { expect } from '@playwright/test';
