// Wire types mirroring the Cue API (cue_api/models.py). Keep these in sync
// when the server contract changes; mismatches surface as parse errors at
// runtime, not at compile time.

export type QuestionType =
  | 'open_ended'
  | 'single_choice'
  | 'multiple_choice'
  | 'slider';

export interface BatchChoice {
  id: string;
  label: string;
}

export interface BatchSuggestItem {
  id: string;
  type: QuestionType;
  prompt: string;
  choices?: BatchChoice[];
}

export interface BatchSuggestRequest {
  assessment_id: string;
  context?: string;
  items: BatchSuggestItem[];
}

export interface CitationResult {
  source: string;
  excerpt: string;
  position: number;
  distance: number;
  full_text: string;
}

export interface ItemSuggestion {
  item_id: string;
  type: string;
  suggestion: string | null;
  selected_id: string | null;
  selected_ids: string[] | null;
  reasoning: string | null;
  citations: CitationResult[];
  generated_at: string | null;
}

export interface BatchSuggestResponse {
  assessment_id: string;
  session_id: string;
  generated_at: string;
  model: string;
  responses: ItemSuggestion[];
}

export interface ExtractFormRequest {
  url: string;
  page_text: string;
}

export interface AuthTokenResponse {
  token: string;
  user_id: string;
}

export interface UploadResponse {
  status: string;
  filename: string;
  size_bytes: number;
  upload_timestamp: string;
  session_id: string;
}
