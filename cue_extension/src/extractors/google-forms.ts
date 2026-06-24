import type { BatchChoice, BatchSuggestItem } from '../types.js';
import type { Extractor, ExtractedField } from './base.js';
import { type IdGen, ariaChoiceLabel, makeIdGen } from './dom-mapping.js';
import { extractFromContainers } from './semantic-html.js';

// Editor pages render option-editor inputs with aria-label="optiewaarde"
// that would poison the generic prompt resolver — match viewform only.
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

function extractAriaChoiceField(container: HTMLElement, idGen: IdGen): ExtractedField | null {
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
  idGen: IdGen,
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
    tokens[id] = label;
  }
  if (choices.length === 0) return null;
  const item: BatchSuggestItem = { id: idGen(), type, prompt, choices };
  return { item, element: widgets[0], choiceTokens: tokens };
}

// Google Forms heading lookup. The generic semantic resolver would fall
// through to the input placeholder ("Jouw antwoord" / "Your answer" —
// useless for retrieval), so we read [role="heading"] directly. Skip empty
// jsname-only slots that sometimes precede the real heading, and strip the
// trailing required-asterisk.
export function googleFormsHeadingPrompt(container: ParentNode): string | undefined {
  const headings = container.querySelectorAll?.('[role="heading"]') ?? [];
  for (const heading of Array.from(headings)) {
    const text = heading.textContent?.trim();
    if (text) return text.replace(/\s*\*\s*$/, '').trim();
  }
  return undefined;
}
