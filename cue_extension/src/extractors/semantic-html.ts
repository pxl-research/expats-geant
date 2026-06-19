import type { Extractor, ExtractedField } from './base.js';
import {
  makeIdGen,
  mapCheckboxGroup,
  mapInput,
  mapRadioGroup,
  mapSelect,
  mapTextarea,
} from './dom-mapping.js';

export const semanticHtmlExtractor: Extractor = {
  name: 'semantic-html',

  detect(): boolean {
    // Semantic HTML is the universal floor — always applicable. Tier
    // selection in the orchestrator decides whether to actually run it.
    return true;
  },

  async extract(document: Document): Promise<ExtractedField[]> {
    const containers: ParentNode[] = [];
    const forms = document.querySelectorAll('form');
    if (forms.length > 0) {
      for (const f of Array.from(forms)) containers.push(f);
    } else if (document.body) {
      containers.push(document.body);
    }
    return extractFromContainers(containers);
  },
};

export function extractFromContainers(containers: ParentNode[]): ExtractedField[] {
  const idGen = makeIdGen();
  const fields: ExtractedField[] = [];
  const handled = new WeakSet<HTMLElement>();

  for (const container of containers) {
    const radios = Array.from(
      container.querySelectorAll<HTMLInputElement>('input[type=radio]'),
    );
    for (const [, group] of groupBy(radios, (r) => r.name)) {
      const f = mapRadioGroup(group, idGen);
      if (f) {
        fields.push(f);
        for (const member of group) handled.add(member);
      }
    }

    const checkboxes = Array.from(
      container.querySelectorAll<HTMLInputElement>('input[type=checkbox]'),
    );
    for (const [, group] of groupBy(checkboxes, (c) => c.name)) {
      const f = mapCheckboxGroup(group, idGen);
      if (f) {
        fields.push(f);
        for (const member of group) handled.add(member);
      }
    }

    for (const input of Array.from(container.querySelectorAll<HTMLInputElement>('input'))) {
      if (handled.has(input)) continue;
      const f = mapInput(input, idGen);
      if (f) fields.push(f);
    }
    for (const ta of Array.from(container.querySelectorAll<HTMLTextAreaElement>('textarea'))) {
      if (handled.has(ta)) continue;
      const f = mapTextarea(ta, idGen);
      if (f) fields.push(f);
    }
    for (const sel of Array.from(container.querySelectorAll<HTMLSelectElement>('select'))) {
      if (handled.has(sel)) continue;
      const f = mapSelect(sel, idGen);
      if (f) fields.push(f);
    }
  }
  return fields;
}

function groupBy<T, K>(items: T[], keyFn: (t: T) => K): Map<K, T[]> {
  const map = new Map<K, T[]>();
  for (const item of items) {
    const key = keyFn(item);
    const bucket = map.get(key);
    if (bucket) bucket.push(item);
    else map.set(key, [item]);
  }
  return map;
}
