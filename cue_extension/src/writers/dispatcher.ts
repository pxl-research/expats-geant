import { ariaChoiceLabel, choiceMatchToken } from '../extractors/dom-mapping.js';
import type { ItemSuggestion } from '../types.js';

// Returns true when a value was applied; false when nothing could be written.
export function applySuggestion(element: HTMLElement, suggestion: ItemSuggestion): boolean {
  // role check first: ARIA widgets are plain <div>s, not HTMLInputElement.
  const role = element.getAttribute('role');
  if (role === 'radio' || role === 'checkbox') {
    return applyToAriaWidget(element, suggestion, role);
  }
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

function applyToAriaWidget(
  element: HTMLElement,
  suggestion: ItemSuggestion,
  role: 'radio' | 'checkbox',
): boolean {
  const targets =
    role === 'radio'
      ? suggestion.selected_id
        ? [suggestion.selected_id]
        : []
      : (suggestion.selected_ids ?? []);
  if (targets.length === 0) return false;

  // The fallback to ownerDocument keeps checkboxes inside Google Forms'
  // plain role="list" reachable even when no recognised group wraps them.
  const group =
    element.closest('[role="radiogroup"], [role="list"], [role="group"], [role="listitem"]') ??
    element.ownerDocument;
  const siblings = Array.from(group.querySelectorAll<HTMLElement>(`[role="${role}"]`));

  let applied = false;
  for (const sibling of siblings) {
    const wanted = targets.includes(ariaChoiceLabel(sibling));
    if (role === 'checkbox' || wanted) {
      const checked = sibling.getAttribute('aria-checked') === 'true';
      if (checked !== wanted) {
        sibling.click();
        applied = true;
      } else if (wanted) {
        applied = true;
      }
    }
  }
  return applied;
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
    if (targets.length === 0) return false;
    return clickGroupedInput(input, targets);
  }
  const value = effectiveValue(suggestion);
  if (value === null) return false;
  return setNativeValue(input, value);
}

function applyToTextarea(ta: HTMLTextAreaElement, suggestion: ItemSuggestion): boolean {
  const value = effectiveValue(suggestion);
  if (value === null) return false;
  return setNativeValue(ta, value);
}

// An "effective" value treats null, empty, and whitespace-only suggestions
// the same: nothing to write. This stops boilerplate "no answer found"
// strings from blanking fields the user already filled.
function effectiveValue(suggestion: ItemSuggestion): string | null {
  if (suggestion.suggestion === null) return null;
  const trimmed = suggestion.suggestion.trim();
  return trimmed.length === 0 ? null : suggestion.suggestion;
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
  const value = effectiveValue(suggestion);
  if (value === null) return false;
  el.focus();
  el.textContent = value;
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
}

// Siblings are located by the shared `name` attribute. Matching by
// choiceMatchToken (value || label) covers groups with empty value attrs.
function clickGroupedInput(member: HTMLInputElement, targetValues: string[]): boolean {
  if (!member.name) return false;
  const root = member.form ?? member.ownerDocument;
  const selector = `input[type="${member.type}"][name="${cssEscape(member.name)}"]`;
  const candidates = Array.from(root.querySelectorAll<HTMLInputElement>(selector));
  let applied = false;
  for (const candidate of candidates) {
    const wanted = targetValues.includes(choiceMatchToken(candidate));
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
