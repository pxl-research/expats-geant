import { beforeEach, describe, expect, it } from 'vitest';

import { matchItemsToControls } from '../../src/extractors/llm-fallback.js';
import type { BatchSuggestItem } from '../../src/types.js';

const open = (id: string, prompt: string): BatchSuggestItem => ({
  id,
  type: 'open_ended',
  prompt,
});

describe('matchItemsToControls', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('matches items to controls by case-insensitive substring of resolved prompt', () => {
    document.body.innerHTML = `
      <form>
        <label for="name">Full Name</label>
        <input id="name" type="text" />
        <label for="email">Email Address</label>
        <input id="email" type="email" />
      </form>
    `;
    const fields = matchItemsToControls(document, [open('q1', 'name'), open('q2', 'EMAIL')]);
    expect(fields.length).toBe(2);
    expect((fields[0].element as HTMLInputElement).id).toBe('name');
    expect((fields[1].element as HTMLInputElement).id).toBe('email');
  });

  it('skips items with no matching control', () => {
    document.body.innerHTML = `
      <form>
        <label for="name">Name</label>
        <input id="name" type="text" />
      </form>
    `;
    const fields = matchItemsToControls(document, [
      open('q1', 'name'),
      open('q2', 'an unrelated label that does not appear'),
    ]);
    expect(fields.length).toBe(1);
    expect(fields[0].item.id).toBe('q1');
  });

  it('does not reuse the same control for two items', () => {
    document.body.innerHTML = `
      <form>
        <label for="name">Name</label>
        <input id="name" type="text" />
      </form>
    `;
    const fields = matchItemsToControls(document, [open('q1', 'name'), open('q2', 'name')]);
    expect(fields.length).toBe(1);
    expect(fields[0].item.id).toBe('q1');
  });

  it('ignores hidden and submit controls', () => {
    document.body.innerHTML = `
      <form>
        <input type="hidden" name="csrf" />
        <input type="submit" value="Send" />
        <label for="name">Name</label>
        <input id="name" type="text" />
      </form>
    `;
    const fields = matchItemsToControls(document, [open('q1', 'Name')]);
    expect(fields.length).toBe(1);
    expect((fields[0].element as HTMLInputElement).id).toBe('name');
  });
});
