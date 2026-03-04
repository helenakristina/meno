/**
 * Healthcare provider types
 */

export interface Provider {
  id: string;
  name: string;
  specialty?: string;
  address?: string;
  city: string;
  state: string;
  zip?: string;
  phone?: string;
  website?: string;
  credentials?: string[];
  is_shortlisted?: boolean;
}

export interface ProviderShortlistEntry {
  provider_id: string;
  status: 'contact_pending' | 'contacted' | 'completed' | 'other';
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ProviderSearch {
  query?: string;
  state?: string;
  limit?: number;
}

export interface ProviderState {
  providers: Provider[];
  shortlist: ProviderShortlistEntry[];
  isLoading: boolean;
  error: string | null;
}
