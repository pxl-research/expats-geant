import type { BatchChoice, BatchSuggestItem } from '../types.js';
import type { Extractor, ExtractedField } from './base.js';
import { makeIdGen } from './dom-mapping.js';
import { extractFromContainers } from './semantic-html.js';

// Only viewform (respondent) pages — the editor URL
// (docs.google.com/forms/d/<id>/edit) renders option-editor inputs with
// aria-label="optiewaarde" that would poison the generic prompt resolver.
const GOOGLE_FORMS_URL_RE = /^https:\/\/docs\.google\.com\/forms\/.*\/viewform/;

export const googleFormsExtractor: Extractor = {
  name: 'google-forms',

  detect(url: string, document: Document): boolean {
    if (!GOOGLE_FORMS_URL_RE.test(url)) return false;
    return document.querySelectorAll('[role="listitem"]').length > 0;
  },

  async extract(document: Document): Promise<ExtractedField[]> {
    const containers = Array.from(document.querySelectorAll<HTMLElement>('[role="listitem"]'));
    const idGen = makeIdGen();
    const fields: ExtractedField[] = [];

    // Iterate once in DOM order. Per container, if it carries an ARIA
    // radio/checkbox widget emit that field; otherwise delegate that one
    // container to extractFromContainers so its inputs/textareas pick up
    // the Google Forms heading prompt. This keeps the popup's slot order
    // mirroring the on-page order even when choice and open-ended
    // questions interleave.
    for (const container of containers) {
      const ariaField = extractAriaChoiceField(container, idGen);
      if (ariaField) {
        fields.push(ariaField);
        continue;
      }
      const inputFields = extractFromContainers([container], {
        promptForContainer: googleFormsHeadingPrompt,
        idGen,
      });
      fields.push(...inputFields);
    }
    return fields;
  },
};

function extractAriaChoiceField(
  container: HTMLElement,
  idGen: () => string,
): ExtractedField | null {
  const radios = Array.from(container.querySelectorAll<HTMLElement>('[role="radio"]'));
  if (radios.length > 0) {
    return buildAriaField(container, radios, 'single_choice', idGen);
  }
  const checkboxes = Array.from(container.querySelectorAll<HTMLElement>('[role="checkbox"]'));
  if (checkboxes.length > 0) {
    return buildAriaField(container, checkboxes, 'multiple_choice', idGen);
  }
  return null;
}

function buildAriaField(
  container: HTMLElement,
  widgets: HTMLElement[],
  type: 'single_choice' | 'multiple_choice',
  idGen: () => string,
): ExtractedField | null {
  const prompt = googleFormsHeadingPrompt(container);
  if (!prompt) return null;
  const choices: BatchChoice[] = [];
  const tokens: Record<string, string> = {};
  let n = 0;
  for (const widget of widgets) {
    const label = ariaChoiceLabel(widget);
    if (!label) continue;
    n += 1;
    const id = `c${n}`;
    choices.push({ id, label });
    // For ARIA widgets the actionable token IS the label (the dispatcher
    // matches on data-value/data-answer-value/aria-label/textContent —
    // see ariaWidgetLabel in writers/dispatcher.ts).
    tokens[id] = label;
  }
  if (choices.length === 0) return null;
  const item: BatchSuggestItem = { id: idGen(), type, prompt, choices };
  return { item, element: widgets[0], choiceTokens: tokens };
}

// Choice labels live in either `data-value` (radio) or `data-answer-value`
// (checkbox). Fall back to aria-label and textContent for robustness against
// future markup changes.
export function ariaChoiceLabel(widget: HTMLElement): string {
  return (
    widget.getAttribute('data-value')?.trim() ||
    widget.getAttribute('data-answer-value')?.trim() ||
    widget.getAttribute('aria-label')?.trim() ||
    widget.textContent?.trim() ||
    ''
  );
}

// Google Forms always renders the question text in a `[role="heading"]`
// element near the top of each `[role="listitem"]` container. The generic
// semantic resolver can miss this (it goes via aria-labelledby, which the
// live form sometimes points at not-yet-rendered nodes) and then falls
// through to the input placeholder text — for Dutch forms that's
// "Jouw antwoord" ("your answer"), a meaningless prompt for retrieval.
//
// Trust the heading directly. The first heading inside a container is
// sometimes an empty jsname slot; walk until we find one with text. Strip
// the trailing required-asterisk that Google Forms appends to required
// questions.
export function googleFormsHeadingPrompt(container: ParentNode): string | undefined {
  const headings = (container as ParentNode).querySelectorAll?.('[role="heading"]') ?? [];
  for (const heading of Array.from(headings)) {
    const text = heading.textContent?.trim();
    if (text) return stripRequiredMarker(text);
  }
  return undefined;
}

function stripRequiredMarker(text: string): string {
  return text.replace(/\s*\*\s*$/, '').trim();
}
