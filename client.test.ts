import { describe, expect, it } from 'vitest';
import { ApiError, buildUrl, createClient, errorMessage } from './client';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('buildUrl', () => {
  it('skips empty query values and trims the base slash', () => {
    expect(buildUrl('http://x/', '/search', { q: 'a b', page: 2, tag: undefined, s: '' })).toBe(
      'http://x/api/v1/search?q=a+b&page=2'
    );
  });
});

describe('createClient', () => {
  it('returns parsed JSON and sends JSON bodies', async () => {
    let seen: RequestInit | undefined;
    const request = createClient(async (_url, init) => ((seen = init), json({ ok: 1 })));
    expect(await request('/x', { method: 'POST', body: { a: 1 } })).toEqual({ ok: 1 });
    expect(seen?.body).toBe('{"a":1}');
  });

  it('handles 204', async () => {
    const request = createClient(async () => new Response(null, { status: 204 }));
    expect(await request('/x', { method: 'DELETE' })).toBeUndefined();
  });

  it('maps the error envelope to ApiError', async () => {
    const request = createClient(async () =>
      json({ error: { code: 'conflict', message: 'exists', details: [{ field: 'title', message: 'dup' }] } }, 409)
    );
    const error = await request('/x').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: 'conflict' });
    expect(errorMessage(error)).toBe('exists: title – dup');
  });

  it('survives non-JSON failures and network errors', async () => {
    const bad = createClient(async () => new Response('<html>', { status: 502 }));
    await expect(bad('/x')).rejects.toMatchObject({ status: 502, code: 'http_error' });
    const down = createClient(async () => {
      throw new TypeError('fetch failed');
    });
    await expect(down('/x')).rejects.toMatchObject({ status: 0, code: 'network_error' });
  });
});
