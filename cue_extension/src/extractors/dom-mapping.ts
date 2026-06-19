import type { BatchChoice, BatchSuggestItem } from '../types.js';
import type { ExtractedField } from './base.js';

const OPEN_ENDED_INPUT_TYPES = new Set([
  'text',
  'email',
  'number',
  'url',
  'tel',
  'search',
  'date',
  'time',
  'password',
  'month',
  'week',
  'datetime-local',
]);

const SKIPPED_INPUT_TYPES = new Set([
  'hidden',
  'submit',
  'button',
  'reset',
  'image',
  'file',
]);

export type IdGen = () => string;

export function makeIdGen(): IdGen {
  let n = 0;
  return () => `q${++n}`;
}

export function isHidden(el: HTMLElement): boolean {
  if (el.hidden) return true;
  if (el.getAttribute('aria-hidden') === 'true') return true;
  const style = el.style;
  if (style && (style.display === 'none' || style.visibility === 'hidden')) return true;
  return false;
}

type FormControl = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

function isDisabled(el: FormControl): boolean {
  return el.disabled;
}

export function resolvePrompt(element: HTMLElement): string {
  // 1. <label for="id">
  const id = element.id;
  if (id) {
    const associated = element.ownerDocument.querySelector<HTMLLabelElement>(
      `label[for="${cssEscape(id)}"]`,
    );
    const txt = associated?.textContent?.trim();
    if (txt) return txt;
  }
  // 2. Parent <label>
  const parentLabel = element.closest('label');
  if (parentLabel) {
    const txt = textWithoutControls(parentLabel);
    if (txt) return txt;
  }
  // 3. aria-label
  const ariaLabel = element.getAttribute('aria-label')?.trim();
  if (ariaLabel) return ariaLabel;
  // 4. aria-labelledby
  const labelledBy = element.getAttribute('aria-labelledby');
  if (labelledBy) {
    const parts: string[] = [];
    for (const refId of labelledBy.split(/\s+/)) {
      const ref = element.ownerDocument.getElementById(refId);
      const t = ref?.textContent?.trim();
      if (t) parts.push(t);
    }
    if (parts.length) return parts.join(' ');
  }
  // 5. placeholder
  const placeholder = (element as HTMLInputElement).placeholder?.trim();
  if (placeholder) return placeholder;
  // 6. name attribute as a last resort
  return element.getAttribute('name')?.trim() ?? '';
}

function textWithoutControls(label: HTMLLabelElement): string {
  // Concatenate text nodes only; skip nested input/select/textarea content.
  const parts: string[] = [];
  const walker = label.ownerDocument.createTreeWalker(label, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const txt = node.nodeValue?.trim();
    if (txt) parts.push(txt);
    node = walker.nextNode();
  }
  return parts.join(' ').trim();
}

function cssEscape(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/g, '\\$&');
}

export function mapInput(
  input: HTMLInputElement,
  idGen: IdGen,
  promptOverride?: string,
): ExtractedField | null {
  if (isHidden(input) || isDisabled(input)) return null;
  const type = input.type.toLowerCase();
  if (SKIPPED_INPUT_TYPES.has(type)) return null;
  if (type === 'radio' || type === 'checkbox') return null;

  if (type === 'range') {
    const prompt = promptOverride || resolvePrompt(input);
    if (!prompt) return null;
    return {
      item: { id: idGen(), type: 'slider', prompt },
      element: input,
    };
  }

  if (OPEN_ENDED_INPUT_TYPES.has(type)) {
    const prompt = promptOverride || resolvePrompt(input);
    if (!prompt) return null;
    return {
      item: { id: idGen(), type: 'open_ended', prompt },
      element: input,
    };
  }
  return null;
}

export function mapTextarea(
  ta: HTMLTextAreaElement,
  idGen: IdGen,
  promptOverride?: string,
): ExtractedField | null {
  if (isHidden(ta) || isDisabled(ta)) return null;
  const prompt = promptOverride || resolvePrompt(ta);
  if (!prompt) return null;
  return {
    item: { id: idGen(), type: 'open_ended', prompt },
    element: ta,
  };
}

export function mapSelect(
  sel: HTMLSelectElement,
  idGen: IdGen,
  promptOverride?: string,
): ExtractedField | null {
  if (isHidden(sel) || isDisabled(sel)) return null;
  const prompt = promptOverride || resolvePrompt(sel);
  if (!prompt) return null;
  const choices: BatchChoice[] = [];
  for (const opt of Array.from(sel.options)) {
    if (opt.disabled) continue;
    if (opt.value === '' && !opt.text.trim()) continue;
    if (opt.value === '') continue; // skip "— select —" style placeholders
    choices.push({
      id: opt.value || opt.text.trim(),
      label: opt.text.trim() || opt.value,
    });
  }
  if (choices.length === 0) return null;
  const type: BatchSuggestItem['type'] = sel.multiple ? 'multiple_choice' : 'single_choice';
  return {
    item: { id: idGen(), type, prompt, choices },
    element: sel,
  };
}

export function mapRadioGroup(
  radios: HTMLInputElement[],
  idGen: IdGen,
  promptOverride?: string,
): ExtractedField | null {
  const visible = radios.filter((r) => !isHidden(r) && !isDisabled(r));
  if (visible.length === 0) return null;
  const prompt = promptOverride || groupPrompt(visible[0]);
  if (!prompt) return null;
  const choices = collectChoiceLabels(visible);
  if (choices.length === 0) return null;
  return {
    item: { id: idGen(), type: 'single_choice', prompt, choices },
    element: visible[0],
  };
}

export function mapCheckboxGroup(
  checkboxes: HTMLInputElement[],
  idGen: IdGen,
  promptOverride?: string,
): ExtractedField | null {
  const visible = checkboxes.filter((c) => !isHidden(c) && !isDisabled(c));
  if (visible.length === 0) return null;
  // A lone checkbox is a yes/no toggle; we don't have a question type for it
  // in BatchSuggestItem, so skip rather than misrepresent.
  if (visible.length === 1) return null;
  const prompt = promptOverride || groupPrompt(visible[0]);
  if (!prompt) return null;
  const choices = collectChoiceLabels(visible);
  if (choices.length === 0) return null;
  return {
    item: { id: idGen(), type: 'multiple_choice', prompt, choices },
    element: visible[0],
  };
}

function groupPrompt(member: HTMLInputElement): string {
  const fieldset = member.closest('fieldset');
  if (fieldset) {
    const legend = fieldset.querySelector('legend');
    const txt = legend?.textContent?.trim();
    if (txt) return txt;
  }
  return resolvePrompt(member);
}

function collectChoiceLabels(inputs: HTMLInputElement[]): BatchChoice[] {
  const choices: BatchChoice[] = [];
  for (const input of inputs) {
    const label = choiceLabelFor(input);
    if (!label) continue;
    choices.push({
      id: input.value || label,
      label,
    });
  }
  return choices;
}

function choiceLabelFor(input: HTMLInputElement): string {
  if (input.id) {
    const associated = input.ownerDocument.querySelector<HTMLLabelElement>(
      `label[for="${cssEscape(input.id)}"]`,
    );
    const txt = associated?.textContent?.trim();
    if (txt) return txt;
  }
  const parent = input.closest('label');
  if (parent) {
    const txt = textWithoutControls(parent);
    if (txt) return txt;
  }
  const ariaLabel = input.getAttribute('aria-label')?.trim();
  if (ariaLabel) return ariaLabel;
  return input.value || '';
}
