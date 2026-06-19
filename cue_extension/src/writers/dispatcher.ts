import type { ItemSuggestion } from '../types.js';

// Write a suggestion's resolved value back into its originating DOM element.
// Returns true when a value was applied; false when nothing could be written
// (e.g. radio target value not present in the group).
export function applySuggestion(element: HTMLElement, suggestion: ItemSuggestion): boolean {
  if (element instanceof HTMLInputElement) {
    return applyToInput(element, suggestion);
  }
  if (element instanceof HTMLTextAreaElement) {
    return applyToTextarea(element, suggestion);
  }
  if (element instanceof HTMLSelectElement) {
    return applyToSelect(element, suggestion);
  }
  if (isContentEditable(element)) {
    return applyToContentEditable(element, suggestion);
  }
  return false;
}

function isContentEditable(el: HTMLElement): boolean {
  if (el.isContentEditable) return true;
  const attr = el.getAttribute('contenteditable');
  return attr === '' || attr === 'true' || attr === 'plaintext-only';
}

function applyToInput(input: HTMLInputElement, suggestion: ItemSuggestion): boolean {
  const type = input.type.toLowerCase();

  if (type === 'radio') {
    if (!suggestion.selected_id) return false;
    return clickGroupedInput(input, [suggestion.selected_id]);
  }
  if (type === 'checkbox') {
    const targets = suggestion.selected_ids ?? [];
    return clickGroupedInput(input, targets);
  }
  if (type === 'range') {
    if (suggestion.suggestion === null) return false;
    return setNativeValue(input, suggestion.suggestion);
  }
  if (suggestion.suggestion === null) return false;
  return setNativeValue(input, suggestion.suggestion);
}

function applyToTextarea(ta: HTMLTextAreaElement, suggestion: ItemSuggestion): boolean {
  if (suggestion.suggestion === null) return false;
  return setNativeValue(ta, suggestion.suggestion);
}

function applyToSelect(sel: HTMLSelectElement, suggestion: ItemSuggestion): boolean {
  if (sel.multiple) {
    const targets = new Set(suggestion.selected_ids ?? []);
    if (targets.size === 0) return false;
    let changed = false;
    for (const option of Array.from(sel.options)) {
      const wanted = targets.has(option.value);
      if (option.selected !== wanted) {
        option.selected = wanted;
        changed = true;
      }
    }
    if (changed) {
      sel.dispatchEvent(new Event('input', { bubbles: true }));
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return changed;
  }
  const target = suggestion.selected_id ?? suggestion.suggestion;
  if (target === null) return false;
  for (const option of Array.from(sel.options)) {
    if (option.value === target) {
      sel.value = option.value;
      sel.dispatchEvent(new Event('input', { bubbles: true }));
      sel.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
  }
  return false;
}

function applyToContentEditable(el: HTMLElement, suggestion: ItemSuggestion): boolean {
  if (suggestion.suggestion === null) return false;
  el.focus();
  el.textContent = suggestion.suggestion;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
}

// Toggle one or more inputs in the same radio/checkbox group. The provided
// `member` is any element from the group; siblings are located by the shared
// `name` attribute on the form, or by querying the document if no form scope.
function clickGroupedInput(member: HTMLInputElement, targetValues: string[]): boolean {
  if (!member.name) return false;
  const root = member.form ?? member.ownerDocument;
  const selector = `input[type="${member.type}"][name="${cssEscape(member.name)}"]`;
  const candidates = Array.from(root.querySelectorAll<HTMLInputElement>(selector));
  let applied = false;
  for (const candidate of candidates) {
    const wanted = targetValues.includes(candidate.value);
    if (member.type === 'checkbox' || wanted) {
      if (candidate.checked !== wanted) {
        candidate.click();
        applied = true;
      } else if (wanted) {
        applied = true;
      }
    }
  }
  return applied;
}

// Set a value on a React-controlled input by invoking the native setter and
// then dispatching the input event so any framework listener observes it.
function setNativeValue(
  element: HTMLInputElement | HTMLTextAreaElement,
  value: string,
): boolean {
  const ctor = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement : HTMLInputElement;
  const proto = ctor.prototype as unknown as Record<string, unknown>;
  const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
  const setter = descriptor?.set;
  if (typeof setter === 'function') {
    setter.call(element, value);
  } else {
    element.value = value;
  }
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}

function cssEscape(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(value);
  }
  return value.replace(/["\\]/g, '\\$&');
}
