import type { BatchSuggestItem } from '../types.js';
import type { Extractor, ExtractHelpers, ExtractedField } from './base.js';
import { resolvePrompt } from './dom-mapping.js';

const MAX_PAGE_TEXT_CHARS = 200_000;

export const llmFallbackExtractor: Extractor = {
  name: 'llm-fallback',

  detect(): boolean {
    return true; // Universal — registered last so prior tiers run first.
  },

  async extract(document: Document, helpers: ExtractHelpers): Promise<ExtractedField[]> {
    if (!helpers.callExtractFormAPI) return [];
    const pageText = (document.body?.innerText ?? '').slice(0, MAX_PAGE_TEXT_CHARS);
    if (!pageText.trim()) return [];

    const url = document.defaultView?.location?.href ?? '';
    const items = await helpers.callExtractFormAPI(pageText, url);
    if (items.length === 0) return [];

    return matchItemsToControls(document, items);
  },
};

export function matchItemsToControls(
  document: Document,
  items: BatchSuggestItem[],
): ExtractedField[] {
  const fields: ExtractedField[] = [];
  const candidates = Array.from(
    document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
      'input, textarea, select',
    ),
  ).filter((c) => {
    if (c.disabled) return false;
    if ((c as HTMLInputElement).type === 'hidden') return false;
    if ((c as HTMLInputElement).type === 'submit') return false;
    if ((c as HTMLInputElement).type === 'button') return false;
    return true;
  });

  const used = new WeakSet<HTMLElement>();
  for (const item of items) {
    const target = findMatchingControl(item, candidates, used);
    if (target) {
      fields.push({ item, element: target });
      used.add(target);
    }
  }
  return fields;
}

function findMatchingControl(
  item: BatchSuggestItem,
  candidates: Array<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  used: WeakSet<HTMLElement>,
): HTMLElement | null {
  const target = item.prompt.toLowerCase();
  for (const control of candidates) {
    if (used.has(control)) continue;
    const controlPrompt = resolvePrompt(control).toLowerCase();
    if (!controlPrompt) continue;
    if (controlPrompt.includes(target) || target.includes(controlPrompt)) {
      return control;
    }
  }
  return null;
}
