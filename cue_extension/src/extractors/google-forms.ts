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
      // Nested heading-less listitems are Google Forms' per-option wrappers
      // and the "Andere antwoord" text input it injects under choice
      // questions — never real questions. Top-level listitems fall through
      // to the semantic-html fallback (test fixtures rely on this).
      if (!googleFormsHeadingPrompt(container) && isNestedListitem(container)) continue;
      const ariaFields = extractAriaChoiceField(container, idGen);
      if (ariaFields.length > 0) {
        fields.push(...ariaFields);
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

function isNestedListitem(container: HTMLElement): boolean {
  return Boolean(container.parentElement?.closest('[role="listitem"], [role="list"]'));
}

// Google marks the synthetic "Other:" radio/checkbox with the internal
// sentinel value "__other_option__", but on a different attribute depending
// on widget type: radios carry only data-value="__other_option__" (no
// data-other-checkbox at all — confirmed via live capture); checkboxes carry
// data-answer-value="__other_option__" alongside data-other-checkbox="true".
// It pairs with a free-text input, extracted separately as a companion
// open_ended question (see buildOtherCompanionField) — it must not appear as
// a selectable choice itself, or it leaks in with the sentinel as its label.
function isOtherOption(widget: HTMLElement): boolean {
  return (
    widget.getAttribute('data-value') === '__other_option__' ||
    widget.getAttribute('data-answer-value') === '__other_option__' ||
    widget.getAttribute('data-other-checkbox') === 'true'
  );
}

function extractAriaChoiceField(container: HTMLElement, idGen: IdGen): ExtractedField[] {
  const allRadios = Array.from(container.querySelectorAll<HTMLElement>('[role="radio"]'));
  const radios = allRadios.filter((w) => !isOtherOption(w));
  if (radios.length > 0) {
    return buildChoiceFieldWithOtherCompanion(
      container,
      radios,
      'single_choice',
      idGen,
      allRadios.find(isOtherOption),
    );
  }
  const allCheckboxes = Array.from(container.querySelectorAll<HTMLElement>('[role="checkbox"]'));
  const checkboxes = allCheckboxes.filter((w) => !isOtherOption(w));
  if (checkboxes.length > 0) {
    return buildChoiceFieldWithOtherCompanion(
      container,
      checkboxes,
      'multiple_choice',
      idGen,
      allCheckboxes.find(isOtherOption),
    );
  }
  const listbox = container.querySelector<HTMLElement>('[role="listbox"]');
  if (listbox) {
    const options = Array.from(listbox.querySelectorAll<HTMLElement>('[role="option"]'));
    if (options.length > 0) {
      // Google Forms dropdowns don't support a free-text "Other" option, so
      // there's never a companion question to build here.
      const trigger = container.querySelector<HTMLElement>('[role="combobox"]') ?? listbox;
      const field = buildAriaField(container, options, 'single_choice', idGen, trigger);
      return field ? [field] : [];
    }
  }
  return [];
}

function buildChoiceFieldWithOtherCompanion(
  container: HTMLElement,
  widgets: HTMLElement[],
  type: 'single_choice' | 'multiple_choice',
  idGen: IdGen,
  otherWidget: HTMLElement | undefined,
): ExtractedField[] {
  const primary = buildAriaField(container, widgets, type, idGen);
  if (!primary) return [];
  if (!otherWidget) return [primary];
  const companion = buildOtherCompanionField(container, primary.item, idGen);
  return companion ? [primary, companion] : [primary];
}

// The "Other" checkbox/radio and its paired free-text <input> are extracted
// as a separate open_ended question rather than folded into the parent's
// choices — the parent's write-back can only select from a fixed id set, but
// filling this input (via the same native-value-setter path every open_ended
// field already uses) is what actually produces an answer, and Google's own
// JS ticks the paired checkbox/radio as a side effect of that input event.
// In both real DOM shapes observed (checkbox: each option incl. Other in its
// own listitem; radio: options not wrapped in listitems at all) there is
// exactly one input[type="text"] anywhere inside the question container, and
// no unrelated text input can appear there — so no shape-specific traversal
// is needed.
function buildOtherCompanionField(
  container: HTMLElement,
  parentItem: BatchSuggestItem,
  idGen: IdGen,
): ExtractedField | null {
  const input = container.querySelector<HTMLInputElement>('input[type="text"]');
  if (!input) return null;
  const labels = (parentItem.choices ?? []).map((c) => `- ${c.label}`).join('\n');
  const prompt =
    `This is the free-text "Other" answer for the question: "${parentItem.prompt}"\n` +
    `The listed choices already cover:\n${labels}\n` +
    'Only answer if the correct response is NOT one of the choices above; ' +
    'leave it blank if one of the listed choices already covers it.';
  // Short display label for audit/report UIs — never sent to the LLM.
  const label = `${parentItem.prompt}, Andere`;
  return {
    item: { id: idGen(), type: 'open_ended', prompt, label },
    element: input,
    isOptionalOther: true,
  };
}

function buildAriaField(
  container: HTMLElement,
  widgets: HTMLElement[],
  type: 'single_choice' | 'multiple_choice',
  idGen: IdGen,
  elementOverride?: HTMLElement,
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
  return { item, element: elementOverride ?? widgets[0], choiceTokens: tokens };
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
