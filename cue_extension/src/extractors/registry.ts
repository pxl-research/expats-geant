import type { ExtractedField, ExtractHelpers, Extractor } from './base.js';
import { googleFormsExtractor } from './google-forms.js';
import { llmFallbackExtractor } from './llm-fallback.js';
import { semanticHtmlExtractor } from './semantic-html.js';

// Priority-ordered list. Known-platform extractors come first; the semantic
// HTML extractor is the universal floor; the LLM fallback is the last resort.
export const extractors: Extractor[] = [
  googleFormsExtractor,
  semanticHtmlExtractor,
  llmFallbackExtractor,
];

export interface ExtractionResult {
  extractorName: string;
  fields: ExtractedField[];
}

// Selects the first extractor whose detect() returns true and runs it. If the
// chosen extractor returns zero fields and is not the last in the priority
// list, the orchestrator falls through to the next extractor whose detect()
// matches. This implements the three-tier fall-through specified in
// specs/cue-extension/spec.md (Three-Tier Form Extraction).
export async function runExtraction(
  url: string,
  document: Document,
  helpers: ExtractHelpers,
): Promise<ExtractionResult> {
  for (let i = 0; i < extractors.length; i++) {
    const e = extractors[i];
    if (!e.detect(url, document)) continue;
    const fields = await e.extract(document, helpers);
    const isLast = i === extractors.length - 1;
    if (fields.length > 0 || isLast) {
      return { extractorName: e.name, fields };
    }
    // Otherwise fall through to subsequent extractors.
  }
  return { extractorName: 'none', fields: [] };
}
