import { describe, expect, it } from 'vitest';

import { classifyWriteBackState } from '../../src/popup/writeback-state.js';

describe('classifyWriteBackState', () => {
  it('is "applied" whenever a value was written, regardless of optionality', () => {
    expect(classifyWriteBackState(true, false)).toBe('applied');
    expect(classifyWriteBackState(true, true)).toBe('applied');
  });

  it('is "needs-attention" for an unapplied regular question', () => {
    expect(classifyWriteBackState(false, false)).toBe('needs-attention');
  });

  it('is "optional-empty" for an unapplied Other companion question', () => {
    expect(classifyWriteBackState(false, true)).toBe('optional-empty');
  });
});
