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

  it('rejects the editor URL even when listitem containers are present', () => {
    // Editor pages have listitems too, but they contain option-editor inputs
    // with aria-label="optiewaarde" that would poison the generic resolver.
    // Respondent form is /viewform; editor is /edit.
    document.documentElement.innerHTML = `<div role="listitem"><input type="text" /></div>`;
    expect(
      googleFormsExtractor.detect(
        'https://docs.google.com/forms/d/1FAIpQ/edit',
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

  it('prefers the listitem heading even when the input has a placeholder', async () => {
    // Regression: in live Google Forms the textarea fell through to the
    // generic "Jouw antwoord" placeholder. With heading override, the
    // listitem's `role="heading"` text always wins.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading"><span>Naam</span><span> *</span></div>
        <input type="text" placeholder="Jouw antwoord" />
      </div>
      <div role="listitem">
        <div role="heading">Adres *</div>
        <textarea placeholder="Jouw antwoord"></textarea>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(2);
    expect(fields[0].item.prompt).toBe('Naam');
    expect(fields[1].item.prompt).toBe('Adres');
    expect(fields.map((f) => f.item.prompt)).not.toContain('Jouw antwoord');
  });

  it('keeps the heading text when no required-asterisk is present', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Telefoonnummer</div>
        <input type="text" />
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.prompt).toBe('Telefoonnummer');
  });

  it('extracts a role="radio" widget question as single_choice (Google Forms shape)', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Kun je deelnemen?</div>
        <div role="radiogroup">
          <div role="radio" data-value="Ja, ik zal er zijn"></div>
          <div role="radio" data-value="Helaas, gaat me niet lukken"></div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('single_choice');
    expect(fields[0].item.prompt).toBe('Kun je deelnemen?');
    const ids = fields[0].item.choices?.map((c) => c.id);
    const labels = fields[0].item.choices?.map((c) => c.label);
    expect(ids).toEqual(['c1', 'c2']);
    expect(labels).toEqual(['Ja, ik zal er zijn', 'Helaas, gaat me niet lukken']);
    // The dispatcher side-table maps synthetic ids back to the DOM-side
    // token used to find the matching ARIA widget on write-back.
    expect(fields[0].choiceTokens).toEqual({
      c1: 'Ja, ik zal er zijn',
      c2: 'Helaas, gaat me niet lukken',
    });
  });

  it('extracts a role="checkbox" widget question as multiple_choice', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Wat neem je mee?</div>
        <div role="list">
          <div role="checkbox" data-answer-value="Hoofdgerecht"></div>
          <div role="checkbox" data-answer-value="Dessert"></div>
          <div role="checkbox" data-answer-value="Drankjes"></div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('multiple_choice');
    expect(fields[0].item.choices?.map((c) => c.id)).toEqual(['c1', 'c2', 'c3']);
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual([
      'Hoofdgerecht',
      'Dessert',
      'Drankjes',
    ]);
  });

  it('emits fields in DOM order even when ARIA widgets interleave with text inputs', async () => {
    // Regression: ARIA widgets used to all bubble to the top regardless
    // of where they sit on the page (the audit showed Kun je deelnemen?
    // and Wat neem je mee? as q1/q2 ahead of Wat is je naam?). Iterating
    // per container in DOM order keeps the popup mirroring the form.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Wat is je naam?</div>
        <input type="text" />
      </div>
      <div role="listitem">
        <div role="heading">Kun je deelnemen?</div>
        <div role="radiogroup">
          <div role="radio" data-value="Ja"></div>
          <div role="radio" data-value="Nee"></div>
        </div>
      </div>
      <div role="listitem">
        <div role="heading">Wat is je e-mail?</div>
        <input type="email" />
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    const prompts = fields.map((f) => f.item.prompt);
    expect(prompts).toEqual(['Wat is je naam?', 'Kun je deelnemen?', 'Wat is je e-mail?']);
    expect(fields.map((f) => f.item.id)).toEqual(['q1', 'q2', 'q3']);
    expect(fields[1].item.type).toBe('single_choice');
  });

  it('skips the "Andere antwoord" text input Google injects under choice questions', async () => {
    // Regression: Google Forms renders the "Other" option as a nested
    // listitem holding a checkbox AND a text input for the user's custom
    // answer. The nested listitem has no [role="heading"], so it must NOT
    // be emitted as its own question — otherwise the popup shows an extra
    // "Andere antwoord" entry and the LLM tries to answer it in isolation.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Wat neem je mee?</div>
        <div role="list">
          <div role="listitem">
            <div role="checkbox" data-answer-value="Hoofdgerecht"></div>
          </div>
          <div role="listitem">
            <div role="checkbox" data-answer-value="Dessert"></div>
          </div>
          <div role="listitem">
            <div role="checkbox" data-answer-value="__other_option__"></div>
            <input type="text" aria-label="Andere antwoord" />
          </div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('multiple_choice');
    expect(fields[0].item.prompt).toBe('Wat neem je mee?');
    expect(fields.map((f) => f.item.prompt)).not.toContain('Andere antwoord');
  });

  it('emits unique sequential ids across ARIA widget and input phases', async () => {
    // Regression: before this fix the ARIA-widget pass and the
    // extractFromContainers pass each ran their own idGen, so q1 and q2
    // collided. The popup keys answers by item_id, so duplicates caused
    // the rendering to pair prompts with the wrong streamed answers.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Kun je deelnemen?</div>
        <div role="radiogroup">
          <div role="radio" data-value="Ja"></div>
          <div role="radio" data-value="Nee"></div>
        </div>
      </div>
      <div role="listitem">
        <div role="heading">Wat is je naam?</div>
        <input type="text" />
      </div>
      <div role="listitem">
        <div role="heading">Wat is je e-mail?</div>
        <input type="email" />
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    const ids = fields.map((f) => f.item.id);
    expect(ids).toEqual(['q1', 'q2', 'q3']);
    expect(new Set(ids).size).toBe(3);
  });

  it('routes the dispatcher to the first widget element of a role="radio" group', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Kun je deelnemen?</div>
        <div role="radiogroup">
          <div role="radio" data-value="Ja"></div>
          <div role="radio" data-value="Nee"></div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields[0].element.getAttribute('role')).toBe('radio');
    expect(fields[0].element.getAttribute('data-value')).toBe('Ja');
  });

  it('skips an empty leading heading and uses the next non-empty one', async () => {
    // Regression: live Google Forms sometimes renders an empty jsname-only
    // heading before the real question heading inside the same listitem.
    // Picking the first non-empty heading keeps the prompt meaningful.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading" jsname="uwkwCe"></div>
        <div role="heading">Echte vraag</div>
        <input type="text" />
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.prompt).toBe('Echte vraag');
  });
});
