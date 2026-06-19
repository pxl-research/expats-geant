import browser from 'webextension-polyfill';

import { CueApiClient } from '../api/client.js';
import type { BatchSuggestItem, ItemSuggestion } from '../types.js';

const PRIVACY_ACK_KEY = 'cue.privacyAck';

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
  client.setBaseUrl(value);
  clearError();
  renderState();
}

async function onLogin(): Promise<void> {
  const userId = (byId('login-user') as HTMLInputElement).value.trim();
  const secret = (byId('login-secret') as HTMLInputElement).value;
  if (!userId || !secret) {
    showError('User ID and API secret are required.');
    return;
  }
  try {
    await client.login(userId, secret);
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
    const result = await client.uploadDocument(file);
    appendUploadLog(`${result.filename} (${result.size_bytes.toLocaleString()} bytes)`);
    input.value = '';
    clearError();
  } catch (err) {
    showError((err as Error).message);
  }
}

async function onTrigger(): Promise<void> {
  const trigger = byId('trigger-btn') as HTMLButtonElement;
  trigger.disabled = true;
  clearError();
  clearSuggestions();
  setStatus('Locating active tab…');
  try {
    const tabId = await getActiveTabId();
    setStatus('Injecting content script…');
    await browser.scripting.executeScript({ target: { tabId }, files: ['content.js'] });

    setStatus('Extracting form fields…');
    const response = (await browser.tabs.sendMessage(tabId, {
      type: 'extract',
      url: '',
    })) as ContentExtractResponse | undefined;
    if (!response || !response.ok) {
      throw new Error(response?.error ?? 'Extraction failed');
    }
    const items = response.items ?? [];
    if (items.length === 0) {
      setStatus('No form fields detected on this page.');
      return;
    }
    setStatus(
      `Extractor: ${response.extractorName} — ${items.length} field(s). Streaming suggestions…`,
    );

    let received = 0;
    await client.suggestStream(
      { assessment_id: `cue-extension-${Date.now().toString(36)}`, items },
      {
        onSuggestion: (suggestion) => {
          received += 1;
          renderSuggestion(items, suggestion);
          void browser.tabs.sendMessage(tabId, { type: 'writeBack', suggestion });
        },
        onError: (detail) => showError(`Stream error: ${detail}`),
        onDone: () =>
          setStatus(`Done — ${received}/${items.length} suggestion(s) delivered.`),
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
  clearSuggestions();
  setStatus('');
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
  const dd = document.createElement('dd');
  if (suggestion.suggestion !== null) {
    dd.textContent = suggestion.suggestion;
  } else if (suggestion.selected_ids?.length) {
    dd.textContent = suggestion.selected_ids.join(', ');
  } else if (suggestion.selected_id) {
    dd.textContent = suggestion.selected_id;
  } else {
    dd.textContent = '(no answer)';
  }
  dl.append(dt, dd);
  for (const citation of suggestion.citations) {
    const note = document.createElement('div');
    note.className = 'citation';
    const positionPct = (citation.position * 100).toFixed(0);
    note.textContent = `${citation.source} · ${positionPct}%: ${citation.excerpt}`;
    dl.append(note);
  }
}

function toggleHidden(id: string, hidden: boolean): void {
  if (hidden) byId(id).setAttribute('hidden', '');
  else byId(id).removeAttribute('hidden');
}

function clearSuggestions(): void {
  byId('suggestions').innerHTML = '';
}

function setStatus(text: string): void {
  byId('status').textContent = text;
}

function appendUploadLog(text: string): void {
  const li = document.createElement('li');
  li.textContent = text;
  byId('upload-log').append(li);
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
