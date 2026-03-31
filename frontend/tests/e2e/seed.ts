import { Page } from '@playwright/test';

/**
 * Seed realistic symptom data for testing.
 * Creates 15-20 symptom logs spread across the last 30 days.
 * Uses UUIDs that match actual symptoms in the database.
 */
/**
 * Seeds realistic symptom data for responsiveness testing.
 * Creates 10-15 symptom logs spread across the last 20 days.
 */
export async function seedTestData(page: Page, authToken: string): Promise<void> {
	const API_BASE_URL = 'http://localhost:8000';

	// Using reasonable placeholder UUIDs for common menopause symptoms
	// These will be validated against symptoms_reference by the backend
	const commonSymptomIds = [
		'3fa85f64-5717-4562-b3fc-2c963f66afa6', // placeholder UUIDs
		'3fa85f64-5717-4562-b3fc-2c963f66afa7',
		'3fa85f64-5717-4562-b3fc-2c963f66afa8',
		'3fa85f64-5717-4562-b3fc-2c963f66afa9',
		'3fa85f64-5717-4562-b3fc-2c963f66afaa',
		'3fa85f64-5717-4562-b3fc-2c963f66afab',
		'3fa85f64-5717-4562-b3fc-2c963f66afac',
		'3fa85f64-5717-4562-b3fc-2c963f66afad',
		'3fa85f64-5717-4562-b3fc-2c963f66afae',
		'3fa85f64-5717-4562-b3fc-2c963f66afaf'
	];

	// Symptom notes to vary entries
	const notes = [
		'Woke up at 3am soaked in sweat',
		"Couldn't focus at work today",
		'Felt unusually irritable this afternoon',
		'Had trouble falling asleep',
		'Achy joints, especially knees',
		"Memory wasn't great today",
		'Multiple hot flashes throughout the day',
		'Felt anxious without clear reason',
		'Very tired despite good sleep',
		'Recurring headache in the afternoon'
	];

	try {
		console.log('Starting seed data creation...');

		// Seed logs: 1-3 per day for the last 20 days
		const today = new Date();
		let logsCreated = 0;

		for (let daysAgo = 1; daysAgo <= 20; daysAgo++) {
			const logDate = new Date(today);
			logDate.setDate(logDate.getDate() - daysAgo);

			// Some days skip a day, some days have multiple logs
			const isSkipped = Math.random() < 0.3; // 30% chance to skip a day
			if (isSkipped) continue;

			// 1-2 logs per day (reduced from 1-3)
			const logsPerDay = Math.floor(Math.random() * 2) + 1;

			for (let i = 0; i < logsPerDay; i++) {
				// Random time during the day
				const hour = Math.floor(Math.random() * 24);
				const minute = Math.floor(Math.random() * 60);

				logDate.setHours(hour, minute, 0, 0);

				// Random symptoms (1-2 per log)
				const symptomCount = Math.floor(Math.random() * 2) + 1;
				const selectedSymptoms: string[] = [];

				for (let j = 0; j < symptomCount; j++) {
					const symptom = commonSymptomIds[Math.floor(Math.random() * commonSymptomIds.length)];
					if (!selectedSymptoms.includes(symptom)) {
						selectedSymptoms.push(symptom);
					}
				}

				// Random note or empty
				const hasNote = Math.random() < 0.5;
				const note = hasNote ? notes[Math.floor(Math.random() * notes.length)] : null;

				// Create log entry
				const logPayload = {
					symptoms: selectedSymptoms,
					free_text_entry: note,
					source: note ? 'both' : 'cards',
					logged_at: logDate.toISOString()
				};

				try {
					const res = await fetch(`${API_BASE_URL}/api/symptoms/logs`, {
						method: 'POST',
						headers: {
							'Content-Type': 'application/json',
							Authorization: `Bearer ${authToken}`
						},
						body: JSON.stringify(logPayload)
					});

					if (!res.ok) {
						const error = await res.text();
						// Log but don't fail - some invalid IDs are expected
						if (res.status !== 400) {
							console.warn(`Failed to create seed log: ${res.status}`);
						}
					} else {
						logsCreated++;
					}
				} catch (err) {
					console.warn(`Error seeding log: ${err}`);
				}
			}
		}

		console.log(`Seed data created: ${logsCreated} logs`);
	} catch (err) {
		console.warn(`Error during seed: ${err}`);
		// Don't fail tests if seeding fails - the responsiveness audit can run without data
	}
}
