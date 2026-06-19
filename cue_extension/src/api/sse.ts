// Server-Sent Events parser over fetch + ReadableStream.
//
// The native EventSource API cannot carry an Authorization header, so the
// Cue API client consumes /suggest/stream via fetch and feeds the response
// body through this parser. Each emitted event mirrors the SSE wire format:
// `event: <name>` line + one or more `data:` lines, terminated by a blank
// line.

export interface SseEvent {
  event: string;
  data: string;
}

export async function consumeSseStream(
  response: Response,
  onEvent: (event: SseEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error('SSE response has no body');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = drainEvents(buffer, onEvent);
    }
    buffer += decoder.decode();
    drainEvents(buffer + '\n\n', onEvent);
  } finally {
    reader.releaseLock();
  }
}

function drainEvents(buffer: string, onEvent: (event: SseEvent) => void): string {
  let boundary = buffer.indexOf('\n\n');
  while (boundary !== -1) {
    const raw = buffer.slice(0, boundary);
    buffer = buffer.slice(boundary + 2);
    const event = parseSseEvent(raw);
    if (event) onEvent(event);
    boundary = buffer.indexOf('\n\n');
  }
  return buffer;
}

export function parseSseEvent(raw: string): SseEvent | null {
  let event = 'message';
  const dataLines: string[] = [];
  for (const line of raw.split('\n')) {
    if (line.startsWith(':')) continue; // SSE comment line
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(' ') ? value.slice(1) : value);
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join('\n') };
}
