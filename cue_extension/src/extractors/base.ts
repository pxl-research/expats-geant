import type { BatchSuggestItem } from '../types.js';

export interface ExtractedField {
  item: BatchSuggestItem;
  element: HTMLElement;
  // Synthetic choice id → DOM-side actionable token used by the writer
  // dispatcher (e.g. `input.value` for a real radio, the original
  // `data-value` for a Google Forms ARIA widget). Kept off the wire — the
  // server only sees `item.choices[].id` (the synthetic) and `…label`. Set
  // when item.choices is non-empty.
  choiceTokens?: Record<string, string>;
}

export interface ExtractHelpers {
  // The LLM-fallback extractor uses this to call POST /extract-form via the
  // popup. DOM extractors ignore it.
  callExtractFormAPI?: (pageText: string, url: string) => Promise<BatchSuggestItem[]>;
}

export interface Extractor {
  name: string;
  detect(url: string, document: Document): boolean;
  extract(document: Document, helpers: ExtractHelpers): Promise<ExtractedField[]>;
}
