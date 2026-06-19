import { beforeEach, describe, expect, it } from 'vitest';

import type { ItemSuggestion } from '../../src/types.js';
import { applySuggestion } from '../../src/writers/dispatcher.js';

function makeSuggestion(overrides: Partial<ItemSuggestion> = {}): ItemSuggestion {
  return {
    item_id: 'q1',
    type: 'open_ended',
    suggestion: null,
    selected_id: null,
    selected_ids: null,
    reasoning: null,
    citations: [],
    generated_at: null,
    ...overrides,
  };
}

describe('applySuggestion', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
  });

  it('sets text input value and dispatches input + change events', () => {
    document.body.innerHTML = `<input id="x" type="text" />`;
    const input = document.getElementById('x') as HTMLInputElement;
    const events: string[] = [];
    input.addEventListener('input', () => events.push('input'));
    input.addEventListener('change', () => events.push('change'));
    const applied = applySuggestion(input, makeSuggestion({ suggestion: 'hello' }));
    expect(applied).toBe(true);
    expect(input.value).toBe('hello');
    expect(events).toEqual(['input', 'change']);
  });

  it('writes a textarea', () => {
    document.body.innerHTML = `<textarea id="x"></textarea>`;
    const ta = document.getElementById('x') as HTMLTextAreaElement;
    applySuggestion(ta, makeSuggestion({ suggestion: 'multi\nline' }));
    expect(ta.value).toBe('multi\nline');
  });

  it('selects an option in a single-select by value', () => {
    document.body.innerHTML = `
      <select id="x">
        <option value="">choose</option>
        <option value="a">Alpha</option>
        <option value="b">Beta</option>
      </select>
    `;
    const sel = document.getElementById('x') as HTMLSelectElement;
    applySuggestion(sel, makeSuggestion({ selected_id: 'b' }));
    expect(sel.value).toBe('b');
  });

  it('selects multiple options in a multi-select by id list', () => {
    document.body.innerHTML = `
      <select id="x" multiple>
        <option value="a">A</option>
        <option value="b">B</option>
        <option value="c">C</option>
      </select>
    `;
    const sel = document.getElementById('x') as HTMLSelectElement;
    applySuggestion(sel, makeSuggestion({ selected_ids: ['a', 'c'] }));
    const selected = Array.from(sel.selectedOptions).map((o) => o.value);
    expect(selected).toEqual(['a', 'c']);
  });

  it('clicks the correct radio in a group', () => {
    document.body.innerHTML = `
      <form>
        <input type="radio" name="x" value="a" />
        <input type="radio" name="x" value="b" />
      </form>
    `;
    const radioA = document.querySelector<HTMLInputElement>('input[value="a"]')!;
    applySuggestion(radioA, makeSuggestion({ selected_id: 'b' }));
    const radioB = document.querySelector<HTMLInputElement>('input[value="b"]')!;
    expect(radioB.checked).toBe(true);
  });

  it('checks multiple checkboxes in a group', () => {
    document.body.innerHTML = `
      <form>
        <input type="checkbox" name="x" value="a" />
        <input type="checkbox" name="x" value="b" />
        <input type="checkbox" name="x" value="c" />
      </form>
    `;
    const member = document.querySelector<HTMLInputElement>('input[value="a"]')!;
    applySuggestion(member, makeSuggestion({ selected_ids: ['a', 'c'] }));
    expect(document.querySelector<HTMLInputElement>('input[value="a"]')!.checked).toBe(true);
    expect(document.querySelector<HTMLInputElement>('input[value="b"]')!.checked).toBe(false);
    expect(document.querySelector<HTMLInputElement>('input[value="c"]')!.checked).toBe(true);
  });

  it('writes to a contenteditable element', () => {
    document.body.innerHTML = `<div id="x" contenteditable="true"></div>`;
    const div = document.getElementById('x') as HTMLElement;
    applySuggestion(div, makeSuggestion({ suggestion: 'rich text' }));
    expect(div.textContent).toBe('rich text');
  });

  it('returns false when suggestion is null and no choices selected', () => {
    document.body.innerHTML = `<input id="x" type="text" />`;
    const input = document.getElementById('x') as HTMLInputElement;
    const applied = applySuggestion(input, makeSuggestion());
    expect(applied).toBe(false);
    expect(input.value).toBe('');
  });
});
