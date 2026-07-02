import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { beforeEach, describe, expect, it } from 'vitest';

import { googleFormsExtractor } from '../../src/extractors/google-forms.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const checkboxFixturePath = path.resolve(
  __dirname,
  '../../../tests/test_data/html_forms/google_forms_checkbox_sample.html',
);
const checkboxFixtureHtml = readFileSync(checkboxFixturePath, 'utf8');

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

  it('excludes "Andere antwoord" from choices and extracts it as an Other companion question', async () => {
    // Regression: Google Forms renders the "Other" option as a nested
    // listitem holding a checkbox AND a text input for the user's custom
    // answer. It must not appear as a selectable choice (its label is just
    // Google's internal sentinel), and it must not be dropped either — it
    // becomes a second, separate open_ended question pointing at the real
    // text input, so the LLM can still supply an answer when the fixed
    // choices don't cover it.
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
            <div role="checkbox" data-other-checkbox="true" data-answer-value="__other_option__"></div>
            <input type="text" aria-label="Andere antwoord" />
          </div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(2);
    expect(fields[0].item.type).toBe('multiple_choice');
    expect(fields[0].item.prompt).toBe('Wat neem je mee?');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual(['Hoofdgerecht', 'Dessert']);
    expect(fields.map((f) => f.item.prompt)).not.toContain('Andere antwoord');

    expect(fields[1].item.type).toBe('open_ended');
    expect(fields[1].isOptionalOther).toBe(true);
    expect(fields[1].item.prompt).toContain('Wat neem je mee?');
    expect(fields[1].item.prompt).toContain('Hoofdgerecht');
    expect(fields[1].element.getAttribute('aria-label')).toBe('Andere antwoord');
  });

  it('does not fabricate an Other companion when no Other widget is present', async () => {
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
    expect(fields.length).toBe(1);
  });

  it('extracts a radio-based "Anders" option as an Other companion, excluded from choices', async () => {
    // Verified real shape: unlike checkbox options, radio options are not
    // individually wrapped in role="listitem", and the "Anders" radio
    // carries only data-value="__other_option__" — no data-other-checkbox
    // attribute at all (confirmed via live DOM capture).
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Type middelbaar onderwijs</div>
        <div role="radiogroup">
          <div role="radio" data-value="TSO"></div>
          <div role="radio" data-value="ASO"></div>
          <div role="radio" data-value="__other_option__"></div>
          <input type="text" aria-label="Andere antwoord" />
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(2);
    expect(fields[0].item.type).toBe('single_choice');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual(['TSO', 'ASO']);

    expect(fields[1].item.type).toBe('open_ended');
    expect(fields[1].isOptionalOther).toBe(true);
    expect(fields[1].item.prompt).toContain('Type middelbaar onderwijs');
    expect(fields[1].element.getAttribute('aria-label')).toBe('Andere antwoord');
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

  it('extracts a star rating as single_choice, falling back to aria-label for icon-only widgets', async () => {
    // Rating widgets (stars/hearts/thumbs) render as role="radio" like Linear
    // Scale, but the icon itself carries no data-value/text — only aria-label.
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Hoe zou je onze service beoordelen?</div>
        <div role="radiogroup">
          <div role="radio" aria-label="1 ster"></div>
          <div role="radio" aria-label="2 sterren"></div>
          <div role="radio" aria-label="3 sterren"></div>
          <div role="radio" aria-label="4 sterren"></div>
          <div role="radio" aria-label="5 sterren"></div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('single_choice');
    expect(fields[0].item.prompt).toBe('Hoe zou je onze service beoordelen?');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual([
      '1 ster',
      '2 sterren',
      '3 sterren',
      '4 sterren',
      '5 sterren',
    ]);
    expect(fields[0].item.choices?.map((c) => c.id)).toEqual(['c1', 'c2', 'c3', 'c4', 'c5']);
  });

  it('extracts a linear scale as single_choice with numeric choice ids', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Hoe tevreden ben je?</div>
        <div role="radiogroup">
          <div role="radio" data-value="1"></div>
          <div role="radio" data-value="2"></div>
          <div role="radio" data-value="3"></div>
          <div role="radio" data-value="4"></div>
          <div role="radio" data-value="5"></div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('single_choice');
    expect(fields[0].item.prompt).toBe('Hoe tevreden ben je?');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual(['1', '2', '3', '4', '5']);
    expect(fields[0].item.choices?.map((c) => c.id)).toEqual(['c1', 'c2', 'c3', 'c4', 'c5']);
  });

  it('extracts a dropdown (role="listbox") as single_choice', async () => {
    document.documentElement.innerHTML = `
      <div role="listitem">
        <div role="heading">Wat is je afdeling?</div>
        <div role="combobox" aria-haspopup="listbox" aria-expanded="false">Kies</div>
        <div role="listbox" aria-hidden="true">
          <div role="option">Engineering</div>
          <div role="option">Design</div>
          <div role="option">Marketing</div>
        </div>
      </div>
    `;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(1);
    expect(fields[0].item.type).toBe('single_choice');
    expect(fields[0].item.prompt).toBe('Wat is je afdeling?');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual([
      'Engineering',
      'Design',
      'Marketing',
    ]);
    expect(fields[0].item.choices?.map((c) => c.id)).toEqual(['c1', 'c2', 'c3']);
    expect(fields[0].element.getAttribute('role')).toBe('combobox');
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

  it('extracts multiple_choice with all real choices from an actual Google Forms checkbox question', async () => {
    // Regression fixture for the "does our checkbox extraction really emit
    // multiple_choice?" question raised while debugging why multi-select
    // answers weren't landing. This is the verbatim outerHTML captured from
    // a live Google Form (google_forms_checkbox_sample.html) — real
    // jsaction/class noise included — not a hand-simplified approximation.
    document.documentElement.innerHTML = checkboxFixtureHtml;
    const fields = await googleFormsExtractor.extract(document, {});
    expect(fields.length).toBe(2);
    expect(fields[0].item.type).toBe('multiple_choice');
    expect(fields[0].item.prompt).toBe('Voorkennis vakinhoud Statistics for IT');
    expect(fields[0].item.choices?.map((c) => c.label)).toEqual([
      'Geen voorkennis',
      'Beschrijvende statistiek : datarepresentatie / frequentieverdelingen / centrummaten / spreidingsmaten / ...',
      'Kansverdelingen: de normale verdeling',
      'Betrouwbaarheidsintervallen',
      'Hypothesetoetsen',
      'Relaties tussen variabelen (correlatie / regressie / ...)',
    ]);
    // The "Anders:" (other) checkbox must not appear as a 7th choice.
    expect(fields.map((f) => f.item.prompt)).not.toContain('Andere antwoord');

    // It's extracted as a separate Other companion question instead, pointed
    // at the real "Andere antwoord" input from the fixture.
    expect(fields[1].item.type).toBe('open_ended');
    expect(fields[1].isOptionalOther).toBe(true);
    expect(fields[1].item.prompt).toContain('Voorkennis vakinhoud Statistics for IT');
    expect(fields[1].item.prompt).toContain('Geen voorkennis');
    expect(fields[1].element.getAttribute('aria-label')).toBe('Andere antwoord');
  });
});
