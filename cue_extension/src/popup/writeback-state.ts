export type WriteBackState = 'applied' | 'needs-attention' | 'optional-empty';

// An "optional" item (the free-text "Other" companion to a choice question)
// coming back empty is the expected default outcome — most answers are
// already covered by the listed choices — so it shouldn't read as something
// the user needs to check, unlike a regular question with no answer.
export function classifyWriteBackState(applied: boolean, isOptional: boolean): WriteBackState {
  if (applied) return 'applied';
  return isOptional ? 'optional-empty' : 'needs-attention';
}
