import { choiceMatchToken } from '../extractors/dom-mapping.js';
import type { ItemSuggestion } from '../types.js';

// Write a suggestion's resolved value back into its originating DOM element.
// Returns true when a value was applied; false when nothing could be written
// (e.g. radio target value not present in the group).
export function applySuggestion(element: HTMLElement, suggestion: ItemSuggestion): boolean {
  // ARIA widget surfaces (Google Forms radio/checkbox divs, similar SPA
  // patterns) — check by role before instance because these are plain
  // <div>s carrying role + data-value attributes, not real inputs.
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

// Click the role=radio / role=checkbox sibling whose label matches the
// suggestion. The "value" used by the extractor is the data-value /
// data-answer-value / aria-label / textContent in that priority — see
// ariaChoiceLabel in google-forms.ts. We resolve siblings inside the
// nearest meaningful group container (radiogroup / list / group /
// listitem); falling back to listitem keeps Google Forms checkboxes
// (which sit inside a plain role=list) reachable.
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

  const group =
    element.closest('[role="radiogroup"], [role="list"], [role="group"], [role="listitem"]') ??
    element.ownerDocument;
  const siblings = Array.from(group.querySelectorAll<HTMLElement>(`[role="${role}"]`));

  let applied = false;
  for (const sibling of siblings) {
    const label = ariaWidgetLabel(sibling);
    const wanted = targets.includes(label);
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

function ariaWidgetLabel(widget: HTMLElement): string {
  return (
    widget.getAttribute('data-value')?.trim() ||
    widget.getAttribute('data-answer-value')?.trim() ||
    widget.getAttribute('aria-label')?.trim() ||
    widget.textContent?.trim() ||
    ''
  );
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
    // Match by the same id the extractor emitted (value || label) so groups
    // with empty `value` attributes — common on Google Forms and many SPA
    // radio renderers — still resolve back to their click target.
    const candidateId = choiceMatchToken(candidate);
    const wanted = targetValues.includes(candidateId);
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
