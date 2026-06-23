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

  it('clicks the correct radio when inputs have empty value attributes (label match)', () => {
    document.body.innerHTML = `
      <form>
        <label><input type="radio" name="x" value="" />Apple</label>
        <label><input type="radio" name="x" value="" />Banana</label>
      </form>
    `;
    const first = document.querySelector<HTMLInputElement>('input[name="x"]')!;
    applySuggestion(first, makeSuggestion({ selected_id: 'Banana' }));
    const radios = document.querySelectorAll<HTMLInputElement>('input[name="x"]');
    expect(radios[0].checked).toBe(false);
    expect(radios[1].checked).toBe(true);
  });

  it('clicks the matching role="radio" sibling on Google-Forms-shaped widgets', () => {
    document.body.innerHTML = `
      <div role="listitem">
        <div role="radiogroup">
          <div id="a" role="radio" data-value="Ja" aria-checked="false"></div>
          <div id="b" role="radio" data-value="Nee" aria-checked="false"></div>
        </div>
      </div>
    `;
    const first = document.getElementById('a')!;
    const clicked: string[] = [];
    document.getElementById('b')!.addEventListener('click', () => clicked.push('b'));
    document.getElementById('a')!.addEventListener('click', () => clicked.push('a'));
    const applied = applySuggestion(first, makeSuggestion({ selected_id: 'Nee' }));
    expect(applied).toBe(true);
    expect(clicked).toEqual(['b']);
  });

  it('clicks every matching role="checkbox" sibling on Google-Forms-shaped widgets', () => {
    document.body.innerHTML = `
      <div role="listitem">
        <div role="list">
          <div id="a" role="checkbox" data-answer-value="Hoofdgerecht" aria-checked="false"></div>
          <div id="b" role="checkbox" data-answer-value="Salade" aria-checked="false"></div>
          <div id="c" role="checkbox" data-answer-value="Dessert" aria-checked="false"></div>
        </div>
      </div>
    `;
    const first = document.getElementById('a')!;
    const clicked: string[] = [];
    for (const id of ['a', 'b', 'c']) {
      document.getElementById(id)!.addEventListener('click', () => clicked.push(id));
    }
    const applied = applySuggestion(
      first,
      makeSuggestion({ selected_ids: ['Hoofdgerecht', 'Dessert'] }),
    );
    expect(applied).toBe(true);
    expect(clicked.sort()).toEqual(['a', 'c']);
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

  it('does not blank a pre-filled input with an empty-string suggestion', () => {
    document.body.innerHTML = `<input id="x" type="text" value="prior" />`;
    const input = document.getElementById('x') as HTMLInputElement;
    const applied = applySuggestion(input, makeSuggestion({ suggestion: '' }));
    expect(applied).toBe(false);
    expect(input.value).toBe('prior');
  });

  it('treats a whitespace-only suggestion as no-answer', () => {
    document.body.innerHTML = `<textarea id="x">existing</textarea>`;
    const ta = document.getElementById('x') as HTMLTextAreaElement;
    const applied = applySuggestion(ta, makeSuggestion({ suggestion: '   \n   ' }));
    expect(applied).toBe(false);
    expect(ta.value).toBe('existing');
  });

  it('does not click radios when selected_id is null', () => {
    document.body.innerHTML = `
      <form>
        <input type="radio" name="x" value="a" />
        <input type="radio" name="x" value="b" />
      </form>
    `;
    const radioA = document.querySelector<HTMLInputElement>('input[value="a"]')!;
    const applied = applySuggestion(radioA, makeSuggestion());
    expect(applied).toBe(false);
    expect(document.querySelectorAll<HTMLInputElement>('input:checked').length).toBe(0);
  });

  it('does not click checkboxes when selected_ids is empty', () => {
    document.body.innerHTML = `
      <form>
        <input type="checkbox" name="x" value="a" />
        <input type="checkbox" name="x" value="b" />
      </form>
    `;
    const member = document.querySelector<HTMLInputElement>('input[value="a"]')!;
    const applied = applySuggestion(member, makeSuggestion({ selected_ids: [] }));
    expect(applied).toBe(false);
    expect(document.querySelectorAll<HTMLInputElement>('input:checked').length).toBe(0);
  });
});
