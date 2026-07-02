import type { BatchSuggestItem } from '../types.js';

export interface ExtractedField {
  item: BatchSuggestItem;
  element: HTMLElement;
  // Synthetic choice id → DOM-side click token. Kept off the wire.
  choiceTokens?: Record<string, string>;
  // Marks this field as the free-text "Other" companion to a choice
  // question. An empty write-back here is the expected default outcome
  // (most answers are covered by the listed choices), not something the
  // user needs to check. Surfaced to the popup via
  // ContentExtractResponse.optionalItemIds — never added to
  // BatchSuggestItem, so it never reaches the server.
  isOptionalOther?: boolean;
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
