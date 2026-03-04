import { describe, it, expect } from 'vitest';

/**
 * Example unit test to verify Vitest is working correctly.
 * Delete this file and replace with real tests.
 */

describe('Vitest setup', () => {
	it('should run a passing test', () => {
		expect(1 + 1).toBe(2);
	});

	it('should support async tests', async () => {
		const result = await Promise.resolve(42);
		expect(result).toBe(42);
	});
});
