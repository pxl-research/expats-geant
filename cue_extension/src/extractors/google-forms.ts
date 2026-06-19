import type { Extractor, ExtractedField } from './base.js';
import { extractFromContainers } from './semantic-html.js';

const GOOGLE_FORMS_URL_RE = /^https:\/\/docs\.google\.com\/forms\//;

export const googleFormsExtractor: Extractor = {
  name: 'google-forms',

  detect(url: string, document: Document): boolean {
    if (!GOOGLE_FORMS_URL_RE.test(url)) return false;
    return document.querySelectorAll('[role="listitem"]').length > 0;
  },

  async extract(document: Document): Promise<ExtractedField[]> {
    const containers = Array.from(document.querySelectorAll('[role="listitem"]'));
    return extractFromContainers(containers, {
      promptForContainer: googleFormsHeadingPrompt,
    });
  },
};

// Google Forms always renders the question text in a `[role="heading"]`
// element near the top of each `[role="listitem"]` container. The generic
// semantic resolver can miss this (it goes via aria-labelledby, which the
// live form sometimes points at not-yet-rendered nodes) and then falls
// through to the input placeholder text — for Dutch forms that's
// "Jouw antwoord" ("your answer"), a meaningless prompt for retrieval.
//
// Trust the heading directly. Strip the trailing required-asterisk that
// Google Forms appends to required questions.
export function googleFormsHeadingPrompt(container: ParentNode): string | undefined {
  const heading = (container as ParentNode).querySelector?.('[role="heading"]');
  const text = heading?.textContent?.trim();
  return text ? stripRequiredMarker(text) : undefined;
}

function stripRequiredMarker(text: string): string {
  return text.replace(/\s*\*\s*$/, '').trim();
}
