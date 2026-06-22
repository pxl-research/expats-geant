// Decode the JWT payload to extract the session_id claim without validating
// the signature (validation is the server's job; we only need the id to
// address DELETE /sessions/{id}).
export function decodeJwtSessionId(jwt: string): string | null {
  try {
    const parts = jwt.split('.');
    if (parts.length !== 3) return null;
    // base64url → base64 then re-pad: atob requires the input length to be a
    // multiple of 4, but JWT payloads use base64url which omits the '='.
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
    const payload = JSON.parse(atob(padded));
    return typeof payload.session_id === 'string' ? payload.session_id : null;
  } catch {
    return null;
  }
}
