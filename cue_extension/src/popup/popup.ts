import browser from 'webextension-polyfill';

import { CueApiClient } from '../api/client.js';
import type { BatchSuggestItem, ItemSuggestion } from '../types.js';

const PRIVACY_ACK_KEY = 'cue.privacyAck';
const LAST_RUN_KEY = 'cue.lastRun';
// Stale-run guard: a cached analysis older than this is dropped on popup
// open instead of being re-rendered. Users who come back hours later see a
// clean slate.
const LAST_RUN_TTL_MS = 60 * 60 * 1000;

interface CachedRun {
  ts: number;
  status: string;
  items: BatchSuggestItem[];
  suggestions: ItemSuggestion[];
}

interface ExtractFormApiMessage {
  type: 'extractFormViaAPI';
  pageText: string;
  url: string;
}

interface ContentExtractResponse {
  ok: boolean;
  extractorName?: string;
  items?: BatchSuggestItem[];
  error?: string;
}

const client = new CueApiClient();

document.addEventListener('DOMContentLoaded', () => {
  void initPopup();
});

async function initPopup(): Promise<void> {
  await client.init();
  installRuntimeBridge();
  await maybeShowPrivacyDialog();
  renderState();
  if (client.hasCredentials()) {
    void refreshDocumentList();
    void rehydrateLastRun();
  }

  byId('cue-url-save').addEventListener('click', () => void onSaveCueUrl());
  byId('login-btn').addEventListener('click', () => void onLogin());
  byId('upload-btn').addEventListener('click', () => void onUpload());
  byId('trigger-btn').addEventListener('click', () => void onTrigger());
  byId('logout-btn').addEventListener('click', () => void onLogout());
  byId('audit-link').addEventListener('click', (event) => {
    event.preventDefault();
    void onAuditReport();
  });
  byId('privacy-accept').addEventListener('click', onPrivacyAccept);
}

async function refreshDocumentList(): Promise<void> {
  try {
    const stats = await client.getSessionStats();
    renderDocumentList(stats.documents);
  } catch (err) {
    // 404 here is fine — session may not exist yet for fresh logins; the
    // first successful upload will create it. Other errors surface to the
    // user so they're not stuck on a stale view.
    const message = (err as Error).message;
    if (!message.includes('404')) {
      showError(message);
    }
  }
}

function renderDocumentList(documents: { name: string }[]): void {
  const list = byId('document-list');
  list.innerHTML = '';
  if (documents.length === 0) {
    const placeholder = document.createElement('li');
    placeholder.className = 'placeholder';
    placeholder.textContent = 'No documents yet.';
    list.append(placeholder);
    return;
  }
  for (const doc of documents) {
    const li = document.createElement('li');
    li.textContent = doc.name;
    list.append(li);
  }
}

function installRuntimeBridge(): void {
  // The content script's LLM fallback asks the popup to call POST
  // /extract-form on its behalf (the popup holds the JWT).
  browser.runtime.onMessage.addListener((message: unknown) => {
    if (!isExtractFormApiMessage(message)) return undefined;
    return client
      .extractForm(message.pageText, message.url)
      .then((items) => ({ items }))
      .catch((err: Error) => ({ items: [], error: err.message }));
  });
}

function isExtractFormApiMessage(msg: unknown): msg is ExtractFormApiMessage {
  return (
    !!msg &&
    typeof msg === 'object' &&
    (msg as { type?: unknown }).type === 'extractFormViaAPI'
  );
}

async function maybeShowPrivacyDialog(): Promise<void> {
  const stored = await browser.storage.local.get(PRIVACY_ACK_KEY);
  if (stored[PRIVACY_ACK_KEY]) return;
  const dialog = byId('privacy-dialog') as HTMLDialogElement;
  dialog.showModal();
}

function onPrivacyAccept(): void {
  void browser.storage.local.set({ [PRIVACY_ACK_KEY]: true });
  (byId('privacy-dialog') as HTMLDialogElement).close();
}

function renderState(): void {
  const url = client.getBaseUrl();
  const authed = client.hasCredentials();
  toggleHidden('onboarding', Boolean(url));
  toggleHidden('login', !url || authed);
  toggleHidden('ready', !authed);
  toggleHidden('logout-btn', !authed);
  if (url && !authed) {
    try {
      byId('login-host').textContent = new URL(url).host;
    } catch {
      byId('login-host').textContent = url;
    }
    byId('login-user-display').textContent = client.getUserId() ?? '(generating…)';
  }
}

async function onSaveCueUrl(): Promise<void> {
  const value = (byId('cue-url-input') as HTMLInputElement).value.trim();
  if (!value) {
    showError('Enter a Cue URL.');
    return;
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    showError('That is not a valid URL.');
    return;
  }
  const origin = `${parsed.protocol}//${parsed.host}/*`;
  const granted = await browser.permissions.request({ origins: [origin] });
  if (!granted) {
    showError('Permission denied — extension cannot reach this host.');
    return;
  }
  await client.setBaseUrl(value);
  clearError();
  renderState();
}

async function onLogin(): Promise<void> {
  const secret = (byId('login-secret') as HTMLInputElement).value;
  if (!secret) {
    showError('API secret is required.');
    return;
  }
  try {
    await client.login(secret);
    (byId('login-secret') as HTMLInputElement).value = '';
    clearError();
    renderState();
  } catch (err) {
    showError((err as Error).message);
  }
}

async function onUpload(): Promise<void> {
  const input = byId('file-input') as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    showError('Choose a file first.');
    return;
  }
  try {
    await client.uploadDocument(file);
    input.value = '';
    clearError();
    await refreshDocumentList();
  } catch (err) {
    showError((err as Error).message);
  }
}

async function onTrigger(): Promise<void> {
  const trigger = byId('trigger-btn') as HTMLButtonElement;
  trigger.disabled = true;
  clearError();
  clearSuggestions();
  const run: CachedRun = { ts: Date.now(), status: '', items: [], suggestions: [] };
  await setStatus('Locating active tab…', run);
  try {
    const tabId = await getActiveTabId();
    await setStatus('Injecting content script…', run);
    await browser.scripting.executeScript({ target: { tabId }, files: ['content.js'] });

    await setStatus('Extracting form fields…', run);
    const response = (await browser.tabs.sendMessage(tabId, {
      type: 'extract',
      url: '',
    })) as ContentExtractResponse | undefined;
    if (!response || !response.ok) {
      throw new Error(response?.error ?? 'Extraction failed');
    }
    const items = response.items ?? [];
    run.items = items;
    if (items.length === 0) {
      await setStatus('No form fields detected on this page.', run);
      return;
    }
    await setStatus(
      `Extractor: ${response.extractorName} — ${items.length} field(s). Streaming suggestions…`,
      run,
    );

    let received = 0;
    await client.suggestStream(
      { assessment_id: `cue-extension-${Date.now().toString(36)}`, items },
      {
        onSuggestion: (suggestion) => {
          received += 1;
          run.suggestions.push(suggestion);
          renderSuggestion(items, suggestion);
          void persistRun(run);
          void browser.tabs.sendMessage(tabId, { type: 'writeBack', suggestion });
        },
        onError: (detail) => showError(`Stream error: ${detail}`),
        onDone: () =>
          void setStatus(`Done — ${received}/${items.length} suggestion(s) delivered.`, run),
      },
    );
  } catch (err) {
    showError((err as Error).message);
  } finally {
    trigger.disabled = false;
  }
}

async function onAuditReport(): Promise<void> {
  try {
    const json = await client.getAuditReport('json');
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cue-audit-${Date.now()}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    showError((err as Error).message);
  }
}

async function onLogout(): Promise<void> {
  await client.logout();
  await browser.storage.local.remove(LAST_RUN_KEY);
  clearSuggestions();
  await setStatus('');
  renderState();
}

async function getActiveTabId(): Promise<number> {
  const tabs = await browser.tabs.query({ active: true, currentWindow: true });
  const tab = tabs[0];
  if (!tab?.id) throw new Error('Could not locate the active tab.');
  return tab.id;
}

function renderSuggestion(items: BatchSuggestItem[], suggestion: ItemSuggestion): void {
  const dl = byId('suggestions');
  const item = items.find((i) => i.id === suggestion.item_id);
  const dt = document.createElement('dt');
  dt.textContent = item?.prompt ?? suggestion.item_id;
  dl.append(dt);

  const dd = document.createElement('dd');
  const answerText = readableAnswer(suggestion);
  if (answerText === null) {
    dd.className = 'no-answer';
    dd.textContent = '(no answer)';
  } else {
    dd.textContent = answerText;
  }
  dl.append(dd);

  if (suggestion.reasoning && suggestion.reasoning.trim()) {
    const reasoning = document.createElement('div');
    reasoning.className = 'reasoning';
    reasoning.textContent = suggestion.reasoning.trim();
    dl.append(reasoning);
  }

  for (const citation of suggestion.citations) {
    const note = document.createElement('div');
    note.className = 'citation';
    const positionPct = (citation.position * 100).toFixed(0);
    note.textContent = `${citation.source} · ${positionPct}%: ${citation.excerpt}`;
    dl.append(note);
  }
}

function readableAnswer(suggestion: ItemSuggestion): string | null {
  if (suggestion.suggestion !== null && suggestion.suggestion.trim()) {
    return suggestion.suggestion;
  }
  if (suggestion.selected_ids && suggestion.selected_ids.length > 0) {
    return suggestion.selected_ids.join(', ');
  }
  if (suggestion.selected_id) {
    return suggestion.selected_id;
  }
  return null;
}

function toggleHidden(id: string, hidden: boolean): void {
  if (hidden) byId(id).setAttribute('hidden', '');
  else byId(id).removeAttribute('hidden');
}

function clearSuggestions(): void {
  byId('suggestions').innerHTML = '';
}

async function setStatus(text: string, run?: CachedRun): Promise<void> {
  byId('status').textContent = text;
  if (run) {
    run.status = text;
    await persistRun(run);
  }
}

async function persistRun(run: CachedRun): Promise<void> {
  await browser.storage.local.set({ [LAST_RUN_KEY]: run });
}

async function rehydrateLastRun(): Promise<void> {
  const stored = await browser.storage.local.get(LAST_RUN_KEY);
  const run = stored[LAST_RUN_KEY] as CachedRun | undefined;
  if (!run) return;
  if (Date.now() - run.ts > LAST_RUN_TTL_MS) {
    await browser.storage.local.remove(LAST_RUN_KEY);
    return;
  }
  if (run.status) byId('status').textContent = run.status;
  for (const suggestion of run.suggestions) {
    renderSuggestion(run.items, suggestion);
  }
}

function showError(message: string): void {
  const el = byId('error-banner');
  el.textContent = message;
  el.removeAttribute('hidden');
}

function clearError(): void {
  byId('error-banner').setAttribute('hidden', '');
}

function byId(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`No element with id ${id}`);
  return el;
}
