import browser from 'webextension-polyfill';

import type {
  AuthTokenResponse,
  BatchSuggestItem,
  BatchSuggestRequest,
  BatchSuggestResponse,
  ItemSuggestion,
  NewSessionResponse,
  RemoveSourceResponse,
  SessionStatsResponse,
  UploadResponse,
} from '../types.js';
import { consumeSseStream } from './sse.js';

const JWT_STORAGE_KEY = 'cue.jwt';
const BASE_URL_STORAGE_KEY = 'cue.baseUrl';
const USER_STORAGE_KEY = 'cue.userId';

export interface StreamCallbacks {
  onSuggestion: (s: ItemSuggestion) => void;
  onError?: (detail: string) => void;
  onDone?: () => void;
}

export class CueApiClient {
  private baseUrl = '';
  private jwt: string | null = null;
  private userId: string | null = null;

  async init(): Promise<void> {
    const stored = await browser.storage.local.get([
      JWT_STORAGE_KEY,
      BASE_URL_STORAGE_KEY,
      USER_STORAGE_KEY,
    ]);
    this.baseUrl = (stored[BASE_URL_STORAGE_KEY] as string | undefined) ?? '';
    this.jwt = (stored[JWT_STORAGE_KEY] as string | undefined) ?? null;
    this.userId = (stored[USER_STORAGE_KEY] as string | undefined) ?? null;
    // Auto-generate a stable per-install user_id so the user only has to
    // supply the operator-distributed API secret. Persists across logout —
    // logging out clears the JWT but keeps the account identity.
    if (!this.userId) {
      this.userId = crypto.randomUUID();
      await browser.storage.local.set({ [USER_STORAGE_KEY]: this.userId });
    }
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  getUserId(): string | null {
    return this.userId;
  }

  async setBaseUrl(url: string): Promise<void> {
    this.baseUrl = url.replace(/\/+$/, '');
    await browser.storage.local.set({ [BASE_URL_STORAGE_KEY]: this.baseUrl });
  }

  hasCredentials(): boolean {
    return Boolean(this.baseUrl && this.jwt);
  }

  async logout(): Promise<void> {
    this.jwt = null;
    await browser.storage.local.remove([JWT_STORAGE_KEY]);
  }

  async login(apiSecret: string): Promise<void> {
    if (!this.baseUrl) throw new Error('Cue base URL not configured');
    if (!this.userId) throw new Error('Account ID is missing');
    const response = await fetch(`${this.baseUrl}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: this.userId, api_secret: apiSecret }),
    });
    if (!response.ok) {
      throw new Error(`Login failed (HTTP ${response.status})`);
    }
    const payload = (await response.json()) as AuthTokenResponse;
    this.jwt = payload.token;
    this.userId = payload.user_id;
    await browser.storage.local.set({
      [JWT_STORAGE_KEY]: payload.token,
      [USER_STORAGE_KEY]: payload.user_id,
    });
  }

  async getSessionStats(): Promise<SessionStatsResponse> {
    this.requireAuth();
    const response = await fetch(`${this.baseUrl}/session/stats`, {
      headers: { Authorization: `Bearer ${this.jwt!}` },
    });
    return this.unwrapJson<SessionStatsResponse>(response, 'Could not fetch session stats');
  }

  async removeDocument(name: string): Promise<RemoveSourceResponse> {
    this.requireAuth();
    const response = await fetch(
      `${this.baseUrl}/session/documents/${encodeURIComponent(name)}`,
      { method: 'DELETE', headers: { Authorization: `Bearer ${this.jwt!}` } },
    );
    return this.unwrapJson<RemoveSourceResponse>(response, 'Could not remove source');
  }

  // Reset to a fresh, empty session: DELETE the current session (server
  // hands back a session-less JWT) and then create a new session under the
  // same user_id. Local JWT is rotated in place; the caller is responsible
  // for clearing any cached UI state. On failure, the JWT is cleared so the
  // popup falls back to the login flow.
  async resetSession(): Promise<void> {
    this.requireAuth();
    const oldSessionId = decodeJwtSessionId(this.jwt!);
    if (oldSessionId) {
      const delResponse = await fetch(
        `${this.baseUrl}/sessions/${encodeURIComponent(oldSessionId)}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${this.jwt!}` } },
      );
      if (delResponse.ok) {
        const body = (await delResponse.json()) as { token?: string };
        if (body.token) this.jwt = body.token;
      }
    }
    const newResponse = await fetch(`${this.baseUrl}/sessions/new`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.jwt!}` },
    });
    if (!newResponse.ok) {
      this.jwt = null;
      await browser.storage.local.remove([JWT_STORAGE_KEY]);
      throw new Error(`Session reset failed (HTTP ${newResponse.status}). Please log in again.`);
    }
    const fresh = (await newResponse.json()) as NewSessionResponse;
    this.jwt = fresh.token;
    await browser.storage.local.set({ [JWT_STORAGE_KEY]: this.jwt });
  }

  async uploadDocument(file: File): Promise<UploadResponse> {
    this.requireAuth();
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`${this.baseUrl}/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.jwt!}` },
      body: form,
    });
    return this.unwrapJson<UploadResponse>(response, 'Upload failed');
  }

  async extractForm(pageText: string, url: string): Promise<BatchSuggestItem[]> {
    this.requireAuth();
    const response = await fetch(`${this.baseUrl}/extract-form`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.jwt!}`,
      },
      body: JSON.stringify({ url, page_text: pageText }),
    });
    return this.unwrapJson<BatchSuggestItem[]>(response, 'Form extraction failed');
  }

  async suggestBatch(request: BatchSuggestRequest): Promise<BatchSuggestResponse> {
    this.requireAuth();
    const response = await fetch(`${this.baseUrl}/suggest/batch`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.jwt!}`,
      },
      body: JSON.stringify(request),
    });
    return this.unwrapJson<BatchSuggestResponse>(response, 'Batch suggest failed');
  }

  // Streams suggestions one at a time. Throws on stream init failure so the
  // caller can decide whether to fall back to suggestBatch. After init, any
  // mid-stream error is delivered to `callbacks.onError` and the stream ends.
  async suggestStream(request: BatchSuggestRequest, callbacks: StreamCallbacks): Promise<void> {
    this.requireAuth();
    const response = await fetch(`${this.baseUrl}/suggest/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: `Bearer ${this.jwt!}`,
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      throw new Error(`Stream init failed (HTTP ${response.status})`);
    }
    await consumeSseStream(response, (event) => {
      try {
        if (event.event === 'suggestion') {
          const parsed = JSON.parse(event.data) as ItemSuggestion;
          callbacks.onSuggestion(parsed);
        } else if (event.event === 'error') {
          const parsed = JSON.parse(event.data) as { detail?: string };
          callbacks.onError?.(parsed.detail ?? 'unknown error');
        } else if (event.event === 'done') {
          callbacks.onDone?.();
        }
      } catch (err) {
        callbacks.onError?.((err as Error).message);
      }
    });
  }

  async getAuditReport(format = 'json'): Promise<string> {
    this.requireAuth();
    const response = await fetch(
      `${this.baseUrl}/audit-report?format=${encodeURIComponent(format)}`,
      {
        method: 'GET',
        headers: { Authorization: `Bearer ${this.jwt!}` },
      },
    );
    if (!response.ok) {
      throw new Error(`Audit report fetch failed (HTTP ${response.status})`);
    }
    return await response.text();
  }

  private requireAuth(): void {
    if (!this.baseUrl) throw new Error('Cue base URL not configured');
    if (!this.jwt) throw new Error('Not authenticated');
  }

  private async unwrapJson<T>(response: Response, errorPrefix: string): Promise<T> {
    if (response.ok) {
      return (await response.json()) as T;
    }
    let detail = '';
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? '';
    } catch {
      try {
        detail = await response.text();
      } catch {
        detail = '';
      }
    }
    throw new Error(`${errorPrefix} (HTTP ${response.status}${detail ? `: ${detail}` : ''})`);
  }
}

// Decode the JWT payload to extract the session_id claim without validating
// the signature (validation is the server's job; we only need the id to
// address DELETE /sessions/{id}).
function decodeJwtSessionId(jwt: string): string | null {
  try {
    const parts = jwt.split('.');
    if (parts.length !== 3) return null;
    const padded = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(padded));
    return typeof payload.session_id === 'string' ? payload.session_id : null;
  } catch {
    return null;
  }
}
