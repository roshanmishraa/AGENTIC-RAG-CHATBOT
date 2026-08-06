// ── Auth ──────────────────────────────────────────────────
export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  phone_number?: string;
  role: "user" | "admin";
  auth_provider?: string;
  created_at?: string;
}

// ── Chat ──────────────────────────────────────────────────
export interface Citation {
  document_id: string;
  page_number?: number;
  chunk_index: number;
}

export interface Message {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
  model_used?: string;
  tokens_used?: number;
  cost_usd?: number;
  created_at?: string;
  needs_human_review?: boolean;
  isTyping?: boolean;
}

export interface Chat {
  id: string;
  title: string;
  created_at: string;
}

// ── Documents ─────────────────────────────────────────────
export interface Document {
  id: string;
  filename: string;
  file_type: string;
  status: "processing" | "ready" | "failed";
  uploaded_at: string;
}

// ── Admin ─────────────────────────────────────────────────
export interface UsageStats {
  total_tokens_used: number;
  total_cost_usd: number;
  total_messages: number;
  total_chats: number;
  total_documents: number;
}

export interface AdminUser {
  id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  detail: Record<string, any>;
  created_at: string;
}

// ── Feedback ──────────────────────────────────────────────
export type FeedbackRating = -1 | 0 | 1;

// ── Media ─────────────────────────────────────────────────
export interface VisionResponse {
  answer: string;
  filename: string;
  content_type: string;
}

export interface TranscriptResponse {
  transcript: string;
}