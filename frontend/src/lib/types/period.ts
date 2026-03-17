/**
 * Shared types for period tracking feature.
 */

export type FlowLevel = 'spotting' | 'light' | 'medium' | 'heavy';

export type PeriodLog = {
	id: string;
	period_start: string;
	period_end: string | null;
	flow_level: FlowLevel | null;
	notes: string | null;
	cycle_length: number | null;
	created_at: string;
};
