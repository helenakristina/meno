/**
 * API Endpoint Type Mappings
 *
 * Define the request/response types for every API endpoint here.
 * This provides compile-time safety when calling the API client.
 *
 * Add a new entry every time you add an API endpoint.
 *
 * @example
 * const response = await apiClient.post('/api/chat', {
 *   message: 'Hello',
 *   conversation_id: '123',
 * });
 * // response is typed as ChatResponse
 */

import type { Citation, Message, SymptomLog, SymptomSummary, Provider, Conversation } from './index';
import type { FlowLevel, PeriodLog } from './period';

/**
 * Maps API endpoints to request/response types.
 * Keyed by endpoint path (string literal).
 */
export interface ApiEndpoints {
  // ========================================================================
  // Chat Endpoints
  // ========================================================================

  '/api/chat': {
    request: {
      message: string;
      conversation_id?: string;
    };
    response: {
      message: string;
      citations: Citation[];
      conversation_id: string;
    };
  };

  '/api/chat/conversations': {
    request: {
      limit?: number;
      offset?: number;
    };
    response: {
      conversations: Conversation[];
      total: number;
      has_more: boolean;
      limit: number;
      offset: number;
    };
  };

  // Dynamic path: /api/chat/conversations/{id}
  '/api/chat/conversations/{id}': {
    request: never;
    response: {
      conversation_id: string;
      messages: Message[];
    };
  };

  '/api/chat/suggested-prompts': {
    request: never;
    response: {
      prompts: string[];
    };
  };

  // ========================================================================
  // Symptom Endpoints
  // ========================================================================

  '/api/symptoms/logs': {
    request: {
      symptoms: string[];
      free_text_entry?: string;
      source: 'cards' | 'text' | 'both';
      logged_at?: string;
    };
    response: {
      id: string;
      user_id: string;
      logged_at: string;
      symptoms: Array<{ id: string; name: string; category: string }>;
      free_text_entry: string | null;
      source: string;
    };
  };

  '/api/symptoms/logs/get': {
    request: {
      start_date?: string;
      end_date?: string;
      limit?: number;
    };
    response: {
      logs: SymptomLog[];
      count: number;
      limit: number;
    };
  };

  '/api/symptoms/stats/frequency': {
    request: {
      days?: number;
    };
    response: {
      stats: Array<{
        symptom_id: string;
        symptom_name: string;
        count: number;
        frequency_percent: number;
      }>;
      period_days: number;
      total_logs: number;
    };
  };

  '/api/symptoms/stats/cooccurrence': {
    request: {
      days?: number;
    };
    response: {
      pairs: Array<{
        symptom_a_id: string;
        symptom_a_name: string;
        symptom_b_id: string;
        symptom_b_name: string;
        cooccurrence_count: number;
        cooccurrence_percent: number;
      }>;
      period_days: number;
      total_logs: number;
    };
  };

  // ========================================================================
  // Provider Endpoints
  // ========================================================================

  '/api/providers/search': {
    request: {
      state?: string;
      city?: string;
      zip_code?: string;
      nams_only?: boolean;
      provider_type?: string;
      insurance?: string;
      page?: number;
      page_size?: number;
    };
    response: {
      providers: Provider[];
      page: number;
      page_size: number;
      total: number;
      has_more: boolean;
    };
  };

  '/api/providers/states': {
    request: never;
    response: Array<{
      state: string;
      provider_count: number;
    }>;
  };

  '/api/providers/calling-script': {
    request: {
      provider_id: string;
      questions?: string[];
    };
    response: {
      provider: Provider;
      calling_script: string;
      questions: string[];
    };
  };

  '/api/providers/shortlist': {
    request: never;
    response: Array<{
      provider_id: string;
      status: 'contact_pending' | 'contacted' | 'completed' | 'other';
      notes: string | null;
      created_at: string;
      updated_at: string;
    }>;
  };

  '/api/providers/shortlist/ids': {
    request: never;
    response: {
      provider_ids: string[];
    };
  };

  '/api/providers/shortlist/add': {
    request: {
      provider_id: string;
    };
    response: {
      provider_id: string;
      status: 'contact_pending' | 'contacted' | 'completed' | 'other';
      notes: string | null;
      created_at: string;
      updated_at: string;
    };
  };

  '/api/providers/shortlist/update': {
    request: {
      provider_id: string;
      status: 'contact_pending' | 'contacted' | 'completed' | 'other';
      notes?: string;
    };
    response: {
      provider_id: string;
      status: 'contact_pending' | 'contacted' | 'completed' | 'other';
      notes: string | null;
      created_at: string;
      updated_at: string;
    };
  };

  '/api/providers/shortlist/remove': {
    request: {
      provider_id: string;
    };
    response: never;
  };

  // ========================================================================
  // User Endpoints
  // ========================================================================

  '/api/users/onboard': {
    request: {
      age?: number;
      journey_stage?: 'premenopause' | 'perimenopause' | 'menopause' | 'postmenopause';
      insurance_provider?: string;
      newsletter_opt_in?: boolean;
    };
    response: {
      id: string;
      email: string;
      age: number | null;
      journey_stage: string | null;
      insurance_provider: string | null;
      created_at: string;
    };
  };

  '/api/users/onboarding': {
    request: {
      date_of_birth: string;
      journey_stage: 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';
    };
    response: {
      id: string;
      email: string;
      date_of_birth: string;
      journey_stage: string;
      onboarding_completed: boolean;
      created_at: string;
    };
  };

  '/api/users/profile': {
    request: never;
    response: {
      id: string;
      email: string;
      age: number | null;
      journey_stage: string | null;
      insurance_provider: string | null;
      created_at: string;
    };
  };

  // ========================================================================
  // Appointment Prep Endpoints
  // ========================================================================

  '/api/appointment-prep/context': {
    request: {
      appointment_type: string;
      goal: string;
      dismissed_before: string;
      urgent_symptom?: string | null;
    };
    response: {
      appointment_id: string;
      next_step: string;
    };
  };

  // Dynamic path: /api/appointment-prep/{id}/narrative
  '/api/appointment-prep/{id}/narrative': {
    request: {
      days_back?: number;
    };
    response: {
      appointment_id: string;
      narrative: string;
      next_step: string;
    };
  };

  // Dynamic path: /api/appointment-prep/{id}/prioritize
  '/api/appointment-prep/{id}/prioritize': {
    request: {
      concerns: string[];
    };
    response: {
      appointment_id: string;
      concerns: string[];
      next_step: string;
    };
  };

  // Dynamic path: /api/appointment-prep/{id}/scenarios
  '/api/appointment-prep/{id}/scenarios': {
    request: never;
    response: {
      appointment_id: string;
      scenarios: Array<{
        id: string;
        title: string;
        situation: string;
        suggestion: string;
        category: string;
      }>;
      next_step: string;
    };
  };

  // Dynamic path: /api/appointment-prep/{id}/generate
  '/api/appointment-prep/{id}/generate': {
    request: never;
    response: {
      appointment_id: string;
      provider_summary_url: string;
      personal_cheat_sheet_url: string;
      message: string;
    };
  };

  // ========================================================================
  // User Settings Endpoints
  // ========================================================================

  '/api/users/settings': {
    request: {
      period_tracking_enabled?: boolean;
      mht_tracking_enabled?: boolean;
      has_uterus?: boolean | null;
      journey_stage?: 'perimenopause' | 'menopause' | 'post-menopause' | 'unsure';
    };
    response: {
      period_tracking_enabled: boolean;
      mht_tracking_enabled: boolean;
      has_uterus: boolean | null;
      journey_stage: string | null;
    };
  };

  // ========================================================================
  // Period Tracking Endpoints
  // ========================================================================

  '/api/period/logs': {
    request: {
      period_start: string;
      period_end?: string;
      flow_level?: FlowLevel;
      notes?: string;
    };
    response: {
      log: PeriodLog;
      bleeding_alert: boolean;
    };
  };

  // Dynamic path: /api/period/logs/{id}
  '/api/period/logs/{id}': {
    request: never;
    response: PeriodLog;
  };

  // Dynamic path: /api/period/logs/{id} (PATCH)
  '/api/period/logs/{id}/patch': {
    request: {
      period_end?: string | null;
      flow_level?: FlowLevel | null;
      notes?: string | null;
    };
    response: PeriodLog;
  };

  '/api/period/analysis': {
    request: never;
    response: {
      average_cycle_length: number | null;
      cycle_variability: number | null;
      months_since_last_period: number | null;
      inferred_stage: string | null;
      has_sufficient_data: boolean;
      calculated_at: string | null;
    };
  };

  // ========================================================================
  // Export Endpoints
  // ========================================================================

  '/api/export/csv': {
    request: {
      date_range_start: string;
      date_range_end: string;
    };
    response: {
      signed_url: string;
      filename: string;
      export_type: string;
    };
  };

  '/api/export/pdf': {
    request: {
      date_range_start: string;
      date_range_end: string;
    };
    response: {
      signed_url: string;
      filename: string;
      export_type: string;
    };
  };

  '/api/export/history': {
    request: never;
    response: {
      exports: Array<Record<string, unknown>>;
      total: number;
      has_more: boolean;
      limit: number;
      offset: number;
    };
  };

  // ========================================================================
  // Medication Tracking Endpoints
  // ========================================================================

  '/api/medications': {
    request: never;
    response: Medication[];
  };

  '/api/medications/add': {
    request: {
      medication_name: string;
      dose: string;
      delivery_method: string;
      frequency?: string;
      start_date: string;
      notes?: string;
    };
    response: Medication;
  };

  // Dynamic path: /api/medications/{id}
  '/api/medications/{id}': {
    request: never;
    response: Medication;
  };

  // Dynamic path: /api/medications/{id} (PUT)
  '/api/medications/{id}/update': {
    request: {
      dose?: string;
      delivery_method?: string;
      frequency?: string | null;
      notes?: string | null;
      end_date?: string | null;
    };
    response: Medication;
  };

  // Dynamic path: /api/medications/{id}/change
  '/api/medications/{id}/change': {
    request: {
      new_dose: string;
      new_delivery_method: string;
      effective_date: string;
    };
    response: Medication;
  };

  // Dynamic path: /api/medications/{id}/delete
  '/api/medications/{id}/delete': {
    request: never;
    response: never;
  };

  // Dynamic path: /api/medications/{id}/symptom-comparison
  '/api/medications/{id}/symptom-comparison': {
    request: never;
    response: SymptomComparisonResponse;
  };

  // Reference medication search: GET /api/medications/reference?query=...
  '/api/medications/reference': {
    request: never;
    response: MedicationReferenceResult[];
  };
}

/**
 * A single MHT medication entry returned from the API.
 */
export interface Medication {
  id: string;
  medication_ref_id: string | null;
  medication_name: string;
  dose: string;
  delivery_method: string;
  frequency: string | null;
  start_date: string;
  end_date: string | null;
  previous_entry_id: string | null;
  notes: string | null;
}

/**
 * A single row in the before/after symptom comparison table.
 */
export interface ComparisonRow {
  symptom_id: string;
  symptom_name: string;
  category: string;
  before_count: number;
  before_days: number;
  before_pct: number;   // 0–100
  after_count: number;
  after_days: number;
  after_pct: number;    // 0–100
  direction: 'improved' | 'worsened' | 'stable';
}

/**
 * Response from GET /api/medications/{id}/symptom-comparison
 */
export interface SymptomComparisonResponse {
  medication_id: string;
  medication_name: string;
  dose: string;
  delivery_method: string;
  start_date: string;
  end_date: string | null;
  before_start: string | null;
  before_end: string | null;
  after_start: string | null;
  after_end: string | null;
  window_days: number;
  has_after_data: boolean;
  before_log_days: number;
  after_log_days: number;
  before_is_sparse: boolean;
  after_is_sparse: boolean;
  rows: ComparisonRow[];
  has_confounding_changes: boolean;
}

/**
 * A medication from the curated reference list (returned by GET /api/medications/reference).
 */
export interface MedicationReferenceResult {
  id: string;
  brand_name: string | null;
  generic_name: string;
  hormone_type: string;
  common_forms: string[];
  common_doses: string[];
  notes: string | null;
  is_user_created: boolean;
}

/**
 * Type-safe API method references
 */
export type ApiMethod = keyof ApiEndpoints;

/**
 * Extract request type for a given endpoint
 * @example type ChatRequest = ApiRequest<'/api/chat'>
 */
export type ApiRequest<T extends ApiMethod> = ApiEndpoints[T]['request'] extends never
  ? undefined
  : ApiEndpoints[T]['request'];

/**
 * Extract response type for a given endpoint
 * @example type ChatResponse = ApiResponse<'/api/chat'>
 */
export type ApiResponse<T extends ApiMethod> = ApiEndpoints[T]['response'] extends never
  ? undefined
  : ApiEndpoints[T]['response'];

/**
 * API Error class returned by the client
 */
export class ApiError extends Error {
  status: number;
  code: string;
  detail: string;
  timestamp: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.timestamp = new Date().toISOString();
  }
}
