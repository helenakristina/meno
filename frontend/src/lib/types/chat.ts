/**
 * Chat/Ask Meno types
 */

export interface Citation {
  url: string;
  title: string;
  section: string;
  source_index: number;
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp?: string;
}

export interface ChatApiResponse {
  message: string;
  citations: Citation[];
  conversation_id: string;
}

export interface ChatState {
  messages: Message[];
  conversationId: string | null;
  isLoading: boolean;
  error: string | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}
