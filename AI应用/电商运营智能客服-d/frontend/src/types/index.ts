export interface UserInfo { id: number; username: string; }
export interface Session { id: string; title: string; }
export interface HistoryMessage {
  role: 'user' | 'agent';
  content: string;
  type?: string;
  complaintLevel?: string;
  complaintType?: string;
}
export interface AIResponse {
  type: 'text' | 'order_card' | 'human_tip' | 'comparison_card';
  content: string;
  complaint_level?: string;
  complaint_type?: string;
}
export interface KbFile {
  id: number;
  filename: string;
  file_size: number;
  chunk_count: number;
  status: string;
  created_at: string;
  operator: string;
}

export interface KbChunk {
  id: string;
  content: string;
  chunk_index: number;
}

export interface KbFileListResponse {
  items: KbFile[];
  total: number;
  page: number;
  page_size: number;
}

export interface KbFileDetailResponse {
  file: Omit<KbFile, 'status' | 'operator'>;
  chunks: KbChunk[];
}

export interface ChatOutput {
  session_id: string;
  user_id: string;
  intent: string;
  input_text: string;
  ai_response: AIResponse;
}