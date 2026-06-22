import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { beforeEach, describe, expect, it } from 'vitest';

import { microsoftFormsExtractor } from '../../src/extractors/microsoft-forms.js';
import { runExtraction } from '../../src/extractors/registry.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturePath = path.resolve(
  __dirname,
  '../../../tests/test_data/html_forms/microsoft_forms_sample.html',
);
const fixtureHtml = readFileSync(fixturePath, 'utf8');

const FORMS_OFFICE_URL = 'https://forms.office.com/r/abc123';
const FORMS_CLOUD_URL = 'https://forms.cloud.microsoft/r/abc123';

describe('microsoftFormsExtractor.detect', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('matches forms.office.com URLs when questionItems are present', () => {
    document.documentElement.innerHTML = fixtureHtml;
    expect(microsoftFormsExtractor.detect(FORMS_OFFICE_URL, document)).toBe(true);
  });

  it('matches forms.cloud.microsoft URLs when questionItems are present', () => {
    document.documentElement.innerHTML = fixtureHtml;
    expect(microsoftFormsExtractor.detect(FORMS_CLOUD_URL, document)).toBe(true);
  });

  it('rejects other Microsoft hosts', () => {
    document.documentElement.innerHTML = fixtureHtml;
    expect(microsoftFormsExtractor.detect('https://office.com/forms/x', document)).toBe(false);
    expect(microsoftFormsExtractor.detect('https://microsoft.com/forms/x', document)).toBe(false);
    expect(microsoftFormsExtractor.detect('https://forms.example.com/x', document)).toBe(false);
  });

  it('rejects forms.office.com pages without questionItems (loading shell)', () => {
    document.documentElement.innerHTML = `
      <div id="content-root">
        <div class="page-loading-background">Loading…</div>
      </div>
    `;
    expect(microsoftFormsExtractor.detect(FORMS_OFFICE_URL, document)).toBe(false);
  });
});

describe('microsoftFormsExtractor.extract', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('extracts all five questions with the right types from the fixture', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await microsoftFormsExtractor.extract(document, {});
    const prompts = fields.map((f) => f.item.prompt);
    expect(prompts).toContain('Voornaam');
    expect(prompts).toContain('Naam');
    expect(prompts).toContain('E-mailadres');
    expect(prompts).toContain('Dieetvoorkeuren / allergieën');
    expect(prompts).toContain('Ik heb de bijdrage van 15 euro gestort via PayConiq.');
    expect(prompts).not.toContain('Single line text');
    expect(prompts).not.toContain('Single choice');
  });

  it('strips the trailing " Single line text." marker from the question title', async () => {
    document.documentElement.innerHTML = `
      <div data-automation-id="questionItem">
        <div data-automation-id="questionTitle">My label Single line text.</div>
        <input type="text" data-automation-id="textInput" />
      </div>
    `;
    const fields = await microsoftFormsExtractor.extract(document, {});
    expect(fields[0].item.prompt).toBe('My label');
  });

  it('strips the trailing " Multi-line text." marker', async () => {
    document.documentElement.innerHTML = `
      <div data-automation-id="questionItem">
        <div data-automation-id="questionTitle">Tell us more Multi-line text.</div>
        <input type="text" data-automation-id="textInput" />
      </div>
    `;
    const fields = await microsoftFormsExtractor.extract(document, {});
    expect(fields[0].item.prompt).toBe('Tell us more');
  });

  it('strips the trailing " Single choice." marker', async () => {
    document.documentElement.innerHTML = `
      <div data-automation-id="questionItem">
        <div data-automation-id="questionTitle">Pick one Single choice.</div>
        <div data-automation-id="choiceItem">Alpha</div>
        <input type="radio" name="x" value="Alpha" />
        <div data-automation-id="choiceItem">Beta</div>
        <input type="radio" name="x" value="Beta" />
      </div>
    `;
    const fields = await microsoftFormsExtractor.extract(document, {});
    expect(fields[0].item.prompt).toBe('Pick one');
    expect(fields[0].item.type).toBe('single_choice');
  });

  it('does not strip when the marker is not actually trailing', async () => {
    document.documentElement.innerHTML = `
      <div data-automation-id="questionItem">
        <div data-automation-id="questionTitle">Why is Single choice. better than open ended?</div>
        <input type="text" data-automation-id="textInput" />
      </div>
    `;
    const fields = await microsoftFormsExtractor.extract(document, {});
    expect(fields[0].item.prompt).toBe(
      'Why is Single choice. better than open ended?',
    );
  });

  it('emits one BatchSuggestItem per radio group sharing a name attribute', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const fields = await microsoftFormsExtractor.extract(document, {});
    const dietField = fields.find((f) => f.item.prompt.startsWith('Dieet'));
    expect(dietField).toBeDefined();
    expect(dietField?.item.type).toBe('single_choice');
    const choiceIds = dietField?.item.choices?.map((c) => c.id) ?? [];
    expect(choiceIds).toContain('Geen');
    expect(choiceIds).toContain('Vegetarisch');
    expect(choiceIds).toContain('Vegan');
  });
});

describe('runExtraction with microsoft-forms registered', () => {
  beforeEach(() => {
    document.documentElement.innerHTML = '';
  });

  it('routes Microsoft Forms pages to the microsoft-forms extractor', async () => {
    document.documentElement.innerHTML = fixtureHtml;
    const result = await runExtraction(FORMS_OFFICE_URL, document, {});
    expect(result.extractorName).toBe('microsoft-forms');
    expect(result.fields.length).toBeGreaterThanOrEqual(4);
  });

  it('still routes Google Forms pages to google-forms (no regression)', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Naam</div>
        <input type="text" />
      </div>
    `;
    const result = await runExtraction(
      'https://docs.google.com/forms/d/abc/viewform',
      document,
      {},
    );
    expect(result.extractorName).toBe('google-forms');
  });
});
