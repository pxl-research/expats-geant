import browser from 'webextension-polyfill';

import { runExtraction } from '../extractors/registry.js';
import type { BatchSuggestItem, ItemSuggestion } from '../types.js';
import { applySuggestion } from '../writers/dispatcher.js';

interface ExtractRequest {
  type: 'extract';
  url?: string;
}
interface ExtractResponse {
  ok: boolean;
  extractorName?: string;
  items?: BatchSuggestItem[];
  error?: string;
}
interface WriteBackRequest {
  type: 'writeBack';
  suggestion: ItemSuggestion;
}
interface WriteBackResponse {
  ok: boolean;
  applied?: boolean;
  error?: string;
}
interface ApiBridgeResponse {
  items: BatchSuggestItem[];
  error?: string;
}

declare global {
  interface Window {
    __cueExtensionAttached?: boolean;
  }
}

const elementMap = new Map<string, HTMLElement>();

function isExtractRequest(msg: unknown): msg is ExtractRequest {
  return !!msg && typeof msg === 'object' && (msg as { type?: unknown }).type === 'extract';
}

function isWriteBackRequest(msg: unknown): msg is WriteBackRequest {
  return !!msg && typeof msg === 'object' && (msg as { type?: unknown }).type === 'writeBack';
}

async function handleExtract(request: ExtractRequest): Promise<ExtractResponse> {
  elementMap.clear();
  const url = request.url || location.href;
  try {
    const result = await runExtraction(url, document, {
      callExtractFormAPI: async (pageText, sourceUrl) => {
        const response = (await browser.runtime.sendMessage({
          type: 'extractFormViaAPI',
          pageText,
          url: sourceUrl,
        })) as ApiBridgeResponse | undefined;
        if (!response || !Array.isArray(response.items)) {
          throw new Error(response?.error ?? 'No response from popup');
        }
        return response.items;
      },
    });
    for (const field of result.fields) {
      elementMap.set(field.item.id, field.element);
    }
    return {
      ok: true,
      extractorName: result.extractorName,
      items: result.fields.map((f) => f.item),
    };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

function handleWriteBack(request: WriteBackRequest): WriteBackResponse {
  const element = elementMap.get(request.suggestion.item_id);
  if (!element) {
    return { ok: false, error: `No element mapped for item ${request.suggestion.item_id}` };
  }
  try {
    const applied = applySuggestion(element, request.suggestion);
    return { ok: true, applied };
  } catch (err) {
    return { ok: false, error: (err as Error).message };
  }
}

if (!window.__cueExtensionAttached) {
  window.__cueExtensionAttached = true;
  browser.runtime.onMessage.addListener((message: unknown) => {
    if (isExtractRequest(message)) {
      return handleExtract(message);
    }
    if (isWriteBackRequest(message)) {
      return Promise.resolve(handleWriteBack(message));
    }
    return undefined;
  });
}
