import { describe, expect, it } from 'vitest';

import { decodeJwtSessionId } from '../../src/api/jwt.js';

// Build an unsigned JWT-shaped string with the given payload. The signature
// segment is irrelevant for decodeJwtSessionId (we never verify) — just needs
// to be present so .split('.') yields three parts.
function makeJwt(payload: object): string {
  const json = JSON.stringify(payload);
  // Node's Buffer + base64url encoding mirrors what a real JWT signer emits.
  const payloadB64Url = Buffer.from(json, 'utf-8').toString('base64url');
  return `eyJhbGciOiJIUzI1NiJ9.${payloadB64Url}.fake-signature`;
}

describe('decodeJwtSessionId', () => {
  it('returns the session_id claim for a payload that needs no padding', () => {
    // 18-byte payload → base64 length 24 (multiple of 4, no pad needed).
    const jwt = makeJwt({ session_id: 'xy' });
    expect(decodeJwtSessionId(jwt)).toBe('xy');
  });

  it('returns the session_id claim for a payload that needs one pad char', () => {
    // 17-byte payload → base64url length 23 → needs one trailing '='.
    const jwt = makeJwt({ session_id: 'x' });
    expect(decodeJwtSessionId(jwt)).toBe('x');
  });

  it('returns the session_id claim for a payload that needs two pad chars', () => {
    // 19-byte payload → base64url length 26 → needs two trailing '='.
    const jwt = makeJwt({ session_id: 'xyz' });
    expect(decodeJwtSessionId(jwt)).toBe('xyz');
  });

  it('handles payloads containing base64url-specific - and _ characters', () => {
    // session_id chosen so the JSON's base64 representation contains '+' and
    // '/' (i.e. the base64url form contains '-' and '_'), exercising the
    // unescape path.
    const jwt = makeJwt({ session_id: '????>>>' });
    expect(decodeJwtSessionId(jwt)).toBe('????>>>');
  });

  it('returns null for a malformed JWT (wrong segment count)', () => {
    expect(decodeJwtSessionId('not.a.jwt.at.all')).toBeNull();
    expect(decodeJwtSessionId('only-one-segment')).toBeNull();
  });

  it('returns null when session_id is missing from the payload', () => {
    const jwt = makeJwt({ user_id: 'alice' });
    expect(decodeJwtSessionId(jwt)).toBeNull();
  });

  it('returns null when session_id is not a string', () => {
    const jwt = makeJwt({ session_id: 12345 });
    expect(decodeJwtSessionId(jwt)).toBeNull();
  });

  it('returns null on completely garbage payload (atob throws)', () => {
    expect(decodeJwtSessionId('header.???*not_base64*???.sig')).toBeNull();
  });
});
