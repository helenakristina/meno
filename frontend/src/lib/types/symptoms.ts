/**
 * Symptom-related types
 */

export interface Symptom {
  id: string;
  name: string;
  category: string;
  description?: string;
}

export interface SymptomLog {
  id: string;
  user_id: string;
  symptoms: string[]; // Array of symptom IDs
  logged_at: string;
  created_at: string;
}

export interface SymptomSummary {
  symptom_id: string;
  symptom_name: string;
  count: number;
  frequency: number; // Percentage
  last_logged: string;
}

export interface SymptomState {
  logs: SymptomLog[];
  summary: SymptomSummary[];
  isLoading: boolean;
  error: string | null;
}
