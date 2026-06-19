import type { BatchSuggestItem } from '../types.js';

export interface ExtractedField {
  item: BatchSuggestItem;
  element: HTMLElement;
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
