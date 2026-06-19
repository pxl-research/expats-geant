import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it } from 'vitest';

import { semanticHtmlExtractor } from '../../src/extractors/semantic-html.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(
  __dirname,
  '../../../tests/test_data/html_forms/simple_form.html',
);
const fixtureHtml = readFileSync(fixturePath, 'utf8');

describe('semanticHtmlExtractor', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('extracts all expected types from the volunteer signup fixture', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await semanticHtmlExtractor.extract(document, {});
    expect(fields.length).toBeGreaterThanOrEqual(6);
    const types = fields.map((f) => f.item.type);
    expect(types).toContain('open_ended');
    expect(types).toContain('single_choice');
    expect(types).toContain('multiple_choice');
    expect(types).toContain('slider');
  });

  it('preserves radio-group choices in document order', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await semanticHtmlExtractor.extract(document, {});
    const shift = fields.find((f) => f.item.prompt.toLowerCase().includes('shift'));
    expect(shift?.item.type).toBe('single_choice');
    expect(shift?.item.choices?.map((c) => c.id)).toEqual(['morning', 'afternoon', 'evening']);
  });

  it('emits multiple_choice for checkbox groups with multiple options', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await semanticHtmlExtractor.extract(document, {});
    const skills = fields.find((f) => f.item.prompt.toLowerCase().includes('skills'));
    expect(skills?.item.type).toBe('multiple_choice');
    expect(skills?.item.choices?.length).toBe(3);
  });

  it('emits single_choice for a non-multiple <select>', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await semanticHtmlExtractor.extract(document, {});
    const role = fields.find((f) => f.item.prompt.toLowerCase().includes('role'));
    expect(role?.item.type).toBe('single_choice');
    expect(role?.item.choices?.map((c) => c.id)).toContain('host');
    expect(role?.item.choices?.map((c) => c.id)).not.toContain('');
  });

  it('emits slider for range inputs', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await semanticHtmlExtractor.extract(document, {});
    const hours = fields.find((f) => f.item.type === 'slider');
    expect(hours).toBeDefined();
    expect(hours?.item.prompt.toLowerCase()).toContain('hours');
  });

  it('skips hidden, disabled, and submit inputs', async () => {
    document.documentElement.innerHTML = `
      <form>
        <label for="visible">Visible</label>
        <input id="visible" type="text" />
        <input type="hidden" name="csrf" />
        <label for="disabled">Disabled</label>
        <input id="disabled" type="text" disabled />
        <input type="submit" value="Go" />
      </form>
    `;
    const fields = await semanticHtmlExtractor.extract(document, {});
    expect(fields.map((f) => f.item.prompt)).toEqual(['Visible']);
  });

  it('resolves prompt from associated label, parent label, aria-label, placeholder', async () => {
    document.documentElement.innerHTML = `
      <form>
        <label for="a">Associated</label>
        <input id="a" type="text" />
        <label>
          Wrapped
          <input type="text" />
        </label>
        <input type="text" aria-label="Aria" />
        <input type="text" placeholder="Placeholder" />
      </form>
    `;
    const fields = await semanticHtmlExtractor.extract(document, {});
    const prompts = fields.map((f) => f.item.prompt);
    expect(prompts).toEqual(['Associated', 'Wrapped', 'Aria', 'Placeholder']);
  });

  it('returns empty list when no form controls are present', async () => {
    document.documentElement.innerHTML = '<body><p>No form</p></body>';
    const fields = await semanticHtmlExtractor.extract(document, {});
    expect(fields).toEqual([]);
  });

  it('skips lone checkboxes (no yes/no question type to map to)', async () => {
    document.documentElement.innerHTML = `
      <form>
        <label><input type="checkbox" name="opt_in" /> Subscribe</label>
      </form>
    `;
    const fields = await semanticHtmlExtractor.extract(document, {});
    expect(fields).toEqual([]);
  });
});
