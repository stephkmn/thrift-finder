import { describe, expect, it, vi } from 'vitest';
import { ApiError, extract, search } from '../api/client';
import type { SearchRequest } from '../api/types';
import { makeFile } from './helpers';

describe('extract()', () => {
  it('rejects when neither image nor text is given', async () => {
    await expect(extract({ text: '   ' })).rejects.toThrow();
  });

  describe('with mocks on', () => {
    it('returns the fixture shape without calling fetch', async () => {
      vi.stubEnv('VITE_USE_MOCKS', 'true');
      const fetchSpy = vi.spyOn(globalThis, 'fetch');

      const result = await extract({ text: 'black denim jacket' });

      expect(fetchSpy).not.toHaveBeenCalled();
      expect(result.attributes).toEqual({
        category: 'jacket',
        color: 'black',
        fabric: 'denim',
        fit: 'regular fit',
        others: ['hood'],
      });
      expect(Object.keys(result.confidences).sort()).toEqual(
        ['category', 'color', 'fabric', 'fit', 'others'].sort(),
      );
      expect(result.confidences.others).toEqual({ hood: 0.82 });
      expect(result.query_id).toMatch(/^mock-/);
    });

    it('generates a fresh query_id per call', async () => {
      vi.stubEnv('VITE_USE_MOCKS', 'true');
      const a = await extract({ text: 'coat' });
      const b = await extract({ text: 'coat' });
      expect(a.query_id).not.toBe(b.query_id);
    });

    it('rejects with a 500 ApiError for the __error__ trigger', async () => {
      vi.stubEnv('VITE_USE_MOCKS', 'true');
      const error = await extract({ text: '__error__' }).catch((e: unknown) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(500);
    });
  });

  describe('with mocks off', () => {
    it('POSTs multipart FormData to /api/extract with only the fields provided', async () => {
      vi.stubEnv('VITE_USE_MOCKS', 'false');
      const payload = {
        attributes: {
          category: 'coat',
          color: 'brown',
          fabric: 'wool',
          fit: 'oversized',
          others: null,
        },
        confidences: { category: 0.9, color: 0.8, fabric: 0.7, fit: 0.6, others: null },
        query_id: 'q-123',
      };
      const fetchSpy = vi
        .spyOn(globalThis, 'fetch')
        .mockImplementation(async () => new Response(JSON.stringify(payload), { status: 200 }));
      const image = makeFile('coat.jpg', 'image/jpeg');

      const result = await extract({ image, text: '  brown wool coat  ' });

      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [url, init] = fetchSpy.mock.calls[0];
      expect(url).toBe('/api/extract');
      expect(init?.method).toBe('POST');
      const body = init?.body as FormData;
      expect(body).toBeInstanceOf(FormData);
      expect((body.get('image') as File).name).toBe('coat.jpg');
      expect(body.get('text')).toBe('brown wool coat');
      expect(result).toEqual(payload);

      await extract({ text: 'parka' });
      const textOnly = fetchSpy.mock.calls[1][1]?.body as FormData;
      expect(textOnly.has('image')).toBe(false);
    });

    it('turns a non-2xx response into an ApiError with the status', async () => {
      vi.stubEnv('VITE_USE_MOCKS', 'false');
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('nope', { status: 503 }));

      const error = await extract({ text: 'parka' }).catch((e: unknown) => e);
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(503);
      expect((error as ApiError).message).not.toContain('nope');
    });
  });
});

describe('search()', () => {
  const searchRequest: SearchRequest = {
    query_id: 'q-1',
    original_attributes: {
      category: 'jacket',
      color: 'black',
      fabric: 'denim',
      fit: 'regular fit',
      others: ['hood'],
    },
    edited_attributes: {
      category: 'jacket',
      color: 'brown',
      fabric: 'denim',
      fit: 'regular fit',
      others: null,
    },
    text: 'black denim jacket',
  };

  it('returns at most 10 mock results without calling fetch when mocks are on', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    const { results } = await search(searchRequest);

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(results.length).toBeGreaterThan(0);
    expect(results.length).toBeLessThanOrEqual(10);
  });

  it('rejects with a 500 ApiError for the __search_error__ trigger', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'true');
    const error = await search({ ...searchRequest, text: '__search_error__' }).catch(
      (e: unknown) => e,
    );
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(500);
  });

  it('POSTs the exact request as JSON to /api/search when mocks are off', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'false');
    const payload = { results: [] };
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response(JSON.stringify(payload), { status: 200 }));

    const result = await search(searchRequest);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/search');
    expect(init?.method).toBe('POST');
    expect(new Headers(init?.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init?.body as string)).toEqual(searchRequest);
    expect(result).toEqual(payload);
  });

  it('turns a non-2xx response into an ApiError with the status', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'false');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('boom', { status: 502 }));

    const error = await search(searchRequest).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
    expect((error as ApiError).message).not.toContain('boom');
  });

  it('turns a network failure into an ApiError with status 0', async () => {
    vi.stubEnv('VITE_USE_MOCKS', 'false');
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await search(searchRequest).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
  });
});
