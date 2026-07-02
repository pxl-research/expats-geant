import type { Extractor, ExtractedField } from './base.js';
import { extractFromContainers } from './semantic-html.js';

// Matches both the legacy forms.office.com host and the newer
// forms.cloud.microsoft host (which has no .com TLD — it's a real
// Microsoft top-level subdomain Microsoft now serves Forms from).
const MS_FORMS_URL_RE = /^https:\/\/forms\.(office\.com|cloud\.microsoft)\//;

export const microsoftFormsExtractor: Extractor = {
  name: 'microsoft-forms',

  detect(url: string, document: Document): boolean {
    if (!MS_FORMS_URL_RE.test(url)) return false;
    return (
      document.querySelectorAll('[data-automation-id="questionItem"]').length > 0
    );
  },

  async extract(document: Document): Promise<ExtractedField[]> {
    const containers = Array.from(
      document.querySelectorAll('[data-automation-id="questionItem"]'),
    );
    return extractFromContainers(containers, {
      promptForContainer: microsoftFormsTitlePrompt,
    });
  },
};

// Every Microsoft Forms questionItem carries the question text in a
// [data-automation-id="questionTitle"] element. The structurally annoying
// bits inside that element — the screen-reader-only type marker
// (" Single line text.", " Single choice.", …) tagged `aria-hidden="true"`,
// the required-asterisk span, and the in-line "Immersive Reader" button —
// are stripped via structural selectors rather than regex so the prompt is
// just the question text. A regex fallback handles the edge case where MS
// inlines the marker as a sibling text node rather than its own span.
export function microsoftFormsTitlePrompt(container: ParentNode): string | undefined {
  const title = (container as ParentNode).querySelector?.(
    '[data-automation-id="questionTitle"]',
  );
  if (!title) return undefined;
  const clone = title.cloneNode(true) as Element;
  for (const selector of [
    '[aria-hidden="true"]',
    '[data-automation-id="requiredStar"]',
    '[data-automation-id="questionSubTitle"]',
    'button',
    'svg',
  ]) {
    clone.querySelectorAll(selector).forEach((el) => el.remove());
  }
  const text = clone.textContent?.replace(/\s+/g, ' ').trim();
  return text ? stripTypeMarker(text) : undefined;
}

const TYPE_MARKER_RE =
  /\s*(Single line text|Multi-line text|Single choice|Multiple choice|Rating|Date|Net Promoter Score|File upload|Ranking|Likert)\.?\s*$/i;

function stripTypeMarker(text: string): string {
  return text.replace(TYPE_MARKER_RE, '').trim();
}
