import { describe, expect, it, vi } from 'vitest';
import { ApiError, extract } from '../api/client';
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
        fit: 'regular',
        hood: 'no hood',
      });
      expect(Object.keys(result.confidences).sort()).toEqual(
        ['category', 'color', 'fabric', 'fit', 'hood'].sort(),
      );
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
          hood: 'hood',
        },
        confidences: { category: 0.9, color: 0.8, fabric: 0.7, fit: 0.6, hood: 0.5 },
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
