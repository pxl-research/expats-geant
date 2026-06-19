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
    return extractFromContainers(containers);
  },
};
