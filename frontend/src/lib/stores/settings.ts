import { writable } from 'svelte/store';

export interface UserSettings {
	period_tracking_enabled: boolean;
	has_uterus: boolean | null;
	journey_stage: string | null;
}

export const userSettings = writable<UserSettings | null>(null);
