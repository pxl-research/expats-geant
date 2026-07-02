import { describe, expect, it } from 'vitest';

import { consumeSseStream, parseSseEvent } from '../../src/api/sse.js';

describe('parseSseEvent', () => {
  it('parses an event line and a data line', () => {
    expect(parseSseEvent('event: suggestion\ndata: {"id":"q1"}')).toEqual({
      event: 'suggestion',
      data: '{"id":"q1"}',
    });
  });

  it('defaults to "message" event when only data is supplied', () => {
    expect(parseSseEvent('data: hello')).toEqual({ event: 'message', data: 'hello' });
  });

  it('joins multiple data lines with newlines', () => {
    expect(parseSseEvent('event: x\ndata: line1\ndata: line2')).toEqual({
      event: 'x',
      data: 'line1\nline2',
    });
  });

  it('returns null when no data line is present', () => {
    expect(parseSseEvent('event: hello')).toBeNull();
  });

  it('strips a single leading space after "data:"', () => {
    expect(parseSseEvent('data: foo')?.data).toBe('foo');
    expect(parseSseEvent('data:foo')?.data).toBe('foo');
  });

  it('ignores comment lines starting with ":"', () => {
    const parsed = parseSseEvent(':comment\nevent: x\ndata: payload');
    expect(parsed).toEqual({ event: 'x', data: 'payload' });
  });
});

describe('consumeSseStream', () => {
  it('emits events parsed from a single chunk', async () => {
    const events: Array<{ event: string; data: string }> = [];
    const body = streamOf(['event: a\ndata: 1\n\n', 'event: b\ndata: 2\n\n']);
    await consumeSseStream(new Response(body), (e) => events.push(e));
    expect(events).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
    ]);
  });

  it('handles events split across chunks', async () => {
    const events: Array<{ event: string; data: string }> = [];
    const body = streamOf(['event: ab', 'c\ndata: ', 'hello\n\n']);
    await consumeSseStream(new Response(body), (e) => events.push(e));
    expect(events).toEqual([{ event: 'abc', data: 'hello' }]);
  });

  it('throws when the response body is empty', async () => {
    const response = new Response(null);
    await expect(consumeSseStream(response, () => {})).rejects.toThrow();
  });
});

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}
