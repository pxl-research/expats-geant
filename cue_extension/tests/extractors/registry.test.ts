import { beforeEach, describe, expect, it } from 'vitest';

import { runExtraction } from '../../src/extractors/registry.js';

describe('runExtraction (three-tier fall-through)', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('selects google-forms when the URL matches and listitems are present', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <label for="x">Q</label>
        <input id="x" type="text" />
      </div>
    `;
    const result = await runExtraction(
      'https://docs.google.com/forms/d/abc/viewform',
      document,
      {},
    );
    expect(result.extractorName).toBe('google-forms');
    expect(result.fields.length).toBe(1);
  });

  it('falls back to semantic-html on non-Google pages', async () => {
    document.documentElement.innerHTML = `
      <form>
        <label for="a">A</label>
        <input id="a" type="text" />
      </form>
    `;
    const result = await runExtraction('https://example.com/form', document, {});
    expect(result.extractorName).toBe('semantic-html');
    expect(result.fields.length).toBe(1);
  });

  it('falls through to LLM fallback when semantic-html returns zero fields', async () => {
    document.documentElement.innerHTML = '<body><p>no controls</p></body>';
    const callExtractFormAPI = async () => [
      { id: 'q1', type: 'open_ended' as const, prompt: 'placeholder' },
    ];
    const result = await runExtraction('https://example.com/anything', document, {
      callExtractFormAPI,
    });
    expect(result.extractorName).toBe('llm-fallback');
  });

  it('returns the LLM-fallback name even when no helper is supplied (empty result)', async () => {
    document.documentElement.innerHTML = '<body><p>no controls</p></body>';
    const result = await runExtraction('https://example.com/anything', document, {});
    expect(result.extractorName).toBe('llm-fallback');
    expect(result.fields).toEqual([]);
  });
});
