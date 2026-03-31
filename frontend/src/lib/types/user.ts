/**
 * User-related types
 */

export interface UserProfile {
	id: string;
	email: string;
	age?: number;
	journey_stage?: 'premenopause' | 'perimenopause' | 'menopause' | 'postmenopause';
	created_at: string;
}

export interface UserPreferences {
	newsletter_opt_in?: boolean;
	data_sharing?: boolean;
}
