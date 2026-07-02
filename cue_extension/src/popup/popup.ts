import browser from 'webextension-polyfill';

import { CueApiClient } from '../api/client.js';
import type { BatchSuggestItem, ItemSuggestion } from '../types.js';
import { classifyWriteBackState } from './writeback-state.js';

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
  applied: Record<string, boolean>;
  optional: Record<string, boolean>;
}

interface WriteBackResponse {
  ok: boolean;
  applied?: boolean;
  error?: string;
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
  optionalItemIds?: string[];
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
  byId('reset-session-btn').addEventListener('click', () => void onResetSession());
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
    const label = document.createElement('span');
    label.textContent = doc.name;
    li.append(label);
    const removeBtn = document.createElement('button');
    removeBtn.className = 'doc-remove';
    removeBtn.type = 'button';
    removeBtn.title = `Remove ${doc.name}`;
    removeBtn.setAttribute('aria-label', `Remove ${doc.name}`);
    removeBtn.textContent = '✕';
    removeBtn.addEventListener('click', () => void onRemoveDocument(doc.name));
    li.append(removeBtn);
    list.append(li);
  }
}

async function onRemoveDocument(name: string): Promise<void> {
  try {
    await client.removeDocument(name);
    clearError();
    await refreshDocumentList();
  } catch (err) {
    showError((err as Error).message);
  }
}

async function onResetSession(): Promise<void> {
  const confirmed = window.confirm(
    'Delete all uploaded documents, suggestions, and audit data, then start a fresh session?',
  );
  if (!confirmed) return;
  const button = byId('reset-session-btn') as HTMLButtonElement;
  button.disabled = true;
  try {
    await client.resetSession();
    await browser.storage.local.remove(LAST_RUN_KEY);
    clearSuggestions();
    await setStatus('');
    clearError();
    await refreshDocumentList();
  } catch (err) {
    showError((err as Error).message);
    renderState();
  } finally {
    button.disabled = false;
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
  const button = byId('upload-btn') as HTMLButtonElement;
  const file = input.files?.[0];
  if (!file) {
    showError('Choose a file first.');
    return;
  }
  const originalLabel = button.textContent ?? 'Upload';
  button.disabled = true;
  button.textContent = 'Uploading…';
  showUploadingPlaceholder(file.name);
  try {
    await client.uploadDocument(file);
    input.value = '';
    clearError();
    await refreshDocumentList();
  } catch (err) {
    showError((err as Error).message);
    // Drop the optimistic "uploading…" row when the server didn't accept it.
    await refreshDocumentList();
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function showUploadingPlaceholder(filename: string): void {
  const list = byId('document-list');
  const placeholder = list.querySelector('li.placeholder');
  if (placeholder) placeholder.remove();
  const li = document.createElement('li');
  li.className = 'uploading';
  li.textContent = `⏳ ${filename}`;
  list.prepend(li);
}

async function onTrigger(): Promise<void> {
  const trigger = byId('trigger-btn') as HTMLButtonElement;
  trigger.disabled = true;
  clearError();
  clearSuggestions();
  const run: CachedRun = {
    ts: Date.now(),
    status: '',
    items: [],
    suggestions: [],
    applied: {},
    optional: {},
  };
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
    const optionalIds = new Set(response.optionalItemIds ?? []);
    run.optional = Object.fromEntries(items.map((i) => [i.id, optionalIds.has(i.id)]));
    await setStatus(
      `Extractor: ${response.extractorName} — ${items.length} field(s). Streaming suggestions…`,
      run,
    );
    // Pre-render one card per item in DOM order so the popup mirrors the
    // form layout. Streamed suggestions then fill their matching slot in
    // place rather than appending in completion order.
    renderItemSlots(items);

    let received = 0;
    const writeBacks: Promise<void>[] = [];
    await client.suggestStream(
      { assessment_id: `cue-extension-${Date.now().toString(36)}`, items },
      {
        onSuggestion: (suggestion) => {
          received += 1;
          run.suggestions.push(suggestion);
          fillSuggestionSlot(items, suggestion, run.optional[suggestion.item_id] ?? false);
          void persistRun(run);
          writeBacks.push(
            browser.tabs
              .sendMessage(tabId, { type: 'writeBack', suggestion })
              .then((response) => {
                const applied = Boolean((response as WriteBackResponse | undefined)?.applied);
                run.applied[suggestion.item_id] = applied;
                markWriteBackResult(
                  suggestion.item_id,
                  applied,
                  run.optional[suggestion.item_id] ?? false,
                );
                void persistRun(run);
              }),
          );
        },
        onError: (detail) => showError(`Stream error: ${detail}`),
        onDone: () => {
          void (async () => {
            await Promise.all(writeBacks);
            const appliedCount = Object.values(run.applied).filter(Boolean).length;
            const optionalEmptyCount = Object.keys(run.optional).filter(
              (id) => run.optional[id] && run.applied[id] === false,
            ).length;
            const needsAttention = items.length - appliedCount - optionalEmptyCount;
            await setStatus(
              `Done — ${received}/${items.length} suggestion(s). ` +
                `${appliedCount} filled in automatically, ${needsAttention} need your attention` +
                (optionalEmptyCount ? `, ${optionalEmptyCount} optional (nothing extra found)` : '') +
                '.',
              run,
            );
          })();
        },
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

// Pre-allocate slots so streamed suggestions can fill them in DOM order
// regardless of LLM completion order. Rendered as <details> so a field that
// gets filled in automatically can collapse to a single line, while fields
// needing manual attention stay open by default.
function renderItemSlots(items: BatchSuggestItem[]): void {
  const container = byId('suggestions');
  container.innerHTML = '';
  for (const item of items) {
    const slot = document.createElement('details');
    slot.className = 'suggestion-slot pending';
    slot.dataset.itemId = item.id;
    slot.id = slotIdFor(item.id);
    slot.open = true;

    const summary = document.createElement('summary');
    const icon = document.createElement('span');
    icon.className = 'status-icon';
    icon.setAttribute('aria-hidden', 'true');
    summary.append(icon);
    const prompt = document.createElement('span');
    prompt.className = 'prompt';
    prompt.textContent = item.prompt;
    summary.append(prompt);
    slot.append(summary);

    const answer = document.createElement('div');
    answer.className = 'answer pending-answer';
    answer.textContent = '…';
    slot.append(answer);

    container.append(slot);
  }
}

// Reflects whether the content script could actually write the suggestion
// into the page. Applied fields collapse with a checkmark; fields that need
// the user to act (unsupported widget, no match found) stay expanded; the
// "Other" companion's empty case collapses quietly since that's the expected
// default outcome, not something to flag.
function markWriteBackResult(itemId: string, applied: boolean, isOptional: boolean): void {
  const slot = document.getElementById(slotIdFor(itemId)) as HTMLDetailsElement | null;
  if (!slot) return;
  const state = classifyWriteBackState(applied, isOptional);
  slot.classList.toggle('applied', state === 'applied');
  slot.classList.toggle('needs-attention', state === 'needs-attention');
  slot.classList.toggle('optional-empty', state === 'optional-empty');
  const icon = slot.querySelector<HTMLElement>('.status-icon');
  if (icon) icon.textContent = state === 'applied' ? '✓' : '';
  slot.open = state === 'needs-attention';
}

function fillSuggestionSlot(
  items: BatchSuggestItem[],
  suggestion: ItemSuggestion,
  isOptional = false,
): void {
  const slot = document.getElementById(slotIdFor(suggestion.item_id));
  if (!slot) return; // suggestion arrived for an item we didn't pre-render
  slot.classList.remove('pending');

  const answer = slot.querySelector<HTMLElement>('.answer');
  if (answer) {
    answer.classList.remove('pending-answer');
    const item = items.find((i) => i.id === suggestion.item_id);
    const text = readableAnswer(suggestion, item);
    if (text === null) {
      answer.classList.add('no-answer');
      answer.textContent = isOptional ? '(nothing extra found)' : '(no answer)';
    } else {
      answer.classList.remove('no-answer');
      answer.textContent = text;
    }
  }

  // Avoid duplicates if the slot is being re-filled (e.g. via rehydrate).
  for (const node of slot.querySelectorAll('.reasoning, .citation')) {
    node.remove();
  }

  if (suggestion.reasoning && suggestion.reasoning.trim()) {
    const reasoning = document.createElement('div');
    reasoning.className = 'reasoning';
    reasoning.textContent = suggestion.reasoning.trim();
    slot.append(reasoning);
  }

  for (const citation of suggestion.citations) {
    const note = document.createElement('div');
    note.className = 'citation';
    const positionPct = (citation.position * 100).toFixed(0);
    note.textContent = `${citation.source} · ${positionPct}%: ${citation.excerpt}`;
    slot.append(note);
  }
}

function slotIdFor(itemId: string): string {
  return `suggestion-slot-${itemId}`;
}

function readableAnswer(suggestion: ItemSuggestion, item?: BatchSuggestItem): string | null {
  if (suggestion.suggestion !== null && suggestion.suggestion.trim()) {
    return suggestion.suggestion;
  }
  // Recover the human label for the synthetic id; fall back to the id itself.
  const labelFor = (id: string): string =>
    item?.choices?.find((c) => c.id === id)?.label ?? id;
  if (suggestion.selected_ids && suggestion.selected_ids.length > 0) {
    return suggestion.selected_ids.map(labelFor).join(', ');
  }
  if (suggestion.selected_id) {
    return labelFor(suggestion.selected_id);
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
  if (run.items.length > 0) {
    renderItemSlots(run.items);
    for (const suggestion of run.suggestions) {
      fillSuggestionSlot(run.items, suggestion, run.optional?.[suggestion.item_id] ?? false);
      markWriteBackResult(
        suggestion.item_id,
        run.applied?.[suggestion.item_id] ?? false,
        run.optional?.[suggestion.item_id] ?? false,
      );
    }
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
