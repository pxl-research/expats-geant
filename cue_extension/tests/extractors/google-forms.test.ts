import { beforeEach, describe, expect, it } from 'vitest';

import { googleFormsExtractor } from '../../src/extractors/google-forms.js';

describe('googleFormsExtractor.detect', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('matches a /forms/ URL when listitem containers are present', () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <label for="x">Q1</label>
        <input id="x" type="text" />
      </div>
    `;
    expect(
      googleFormsExtractor.detect(
        'https://docs.google.com/forms/d/e/1FAIpQ/viewform',
        document,
      ),
    ).toBe(true);
  });

  it('rejects Google Docs and unrelated URLs', () => {
    document.documentElement.innerHTML = `<div role="listitem"><input type="text" /></div>`;
    expect(
      googleFormsExtractor.detect('https://docs.google.com/document/d/abc/edit', document),
    ).toBe(false);
    expect(googleFormsExtractor.detect('https://example.com/forms/x', document)).toBe(false);
  });

  it('rejects when no listitem containers are present', () => {
    document.documentElement.innerHTML = `<form><input type="text" /></form>`;
    expect(
      googleFormsExtractor.detect(
        'https://docs.google.com/forms/d/abc/viewform',
        document,
      ),
    ).toBe(false);
  });
});

describe('googleFormsExtractor.extract', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('extracts one item per listitem container', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <label for="q1">What is your name?</label>
        <input id="q1" type="text" />
      </div>
      <div role="listitem">
        <fieldset>
          <legend>Shift preference</legend>
          <label><input type="radio" name="shift" value="morning" /> Morning</label>
          <label><input type="radio" name="shift" value="evening" /> Evening</label>
        </fieldset>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(2);
    expect(fields[0].item.type).toBe('open_ended');
    expect(fields[0].item.prompt).toBe('What is your name?');
    expect(fields[1].item.type).toBe('single_choice');
    expect(fields[1].item.choices?.length).toBe(2);
  });

  it('emits sequential synthetic IDs', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <label for="a">A</label><input id="a" type="text" />
      </div>
      <div role="listitem">
        <label for="b">B</label><input id="b" type="text" />
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.map((f) => f.item.id)).toEqual(['q1', 'q2']);
  });
});
