import { describe, expect, it } from 'vitest';
import { mockSearch, rankListings } from '../api/mocks/mockApi';
import { MOCK_POOL } from '../api/mocks/searchPool';
import type { Attributes, SearchRequest } from '../api/types';
import { VOCABULARY } from '../lib/vocabulary';

const FIXTURE: Attributes = {
  category: 'jacket',
  color: 'black',
  fabric: 'denim',
  fit: 'regular fit',
  others: ['hood'],
};

function request(edited: Attributes, text?: string): SearchRequest {
  return { query_id: 'q-1', original_attributes: FIXTURE, edited_attributes: edited, text };
}

const ids = (attrs: Attributes) => rankListings(MOCK_POOL, attrs).results.map((r) => r.id);

describe('mock search pool', () => {
  it('has 20–30 listings, all built from vocabulary values', () => {
    expect(MOCK_POOL.length).toBeGreaterThanOrEqual(20);
    expect(MOCK_POOL.length).toBeLessThanOrEqual(30);
    for (const { attributes } of MOCK_POOL) {
      expect(VOCABULARY.category).toContain(attributes.category);
      expect(VOCABULARY.color).toContain(attributes.color);
      expect(VOCABULARY.fabric).toContain(attributes.fabric);
      expect(VOCABULARY.fit).toContain(attributes.fit);
      expect(attributes.others).not.toEqual([]);
      for (const feature of attributes.others ?? []) expect(VOCABULARY.features).toContain(feature);
    }
  });

  it('gives eBay items a price and mock link, and local items neither', () => {
    const sources = new Set(MOCK_POOL.map((item) => item.source));
    expect(sources).toEqual(new Set(['ebay', 'local']));
    for (const item of MOCK_POOL) {
      expect(item.image_url).toMatch(/^data:image\/svg\+xml/);
      if (item.source === 'ebay') {
        expect(typeof item.price).toBe('number');
        expect(item.listing_url).toBe(`https://example.com/mock-listing/${item.id}`);
      } else {
        expect(item.price).toBeNull();
        expect(item.listing_url).toBeNull();
      }
    }
  });
});

describe('mockSearch ranking', () => {
  it('is deterministic, capped at 10, and sorted by score then id', async () => {
    const first = await mockSearch(request(FIXTURE));
    const second = await mockSearch(request(FIXTURE));
    expect(second).toEqual(first);
    expect(first.results.length).toBeLessThanOrEqual(10);
    expect(first.results.length).toBeGreaterThan(0);

    for (const [i, result] of first.results.entries()) {
      expect(result.match_score).toBeGreaterThanOrEqual(0);
      expect(result.match_score).toBeLessThanOrEqual(100);
      const next = first.results[i + 1];
      if (!next) continue;
      expect(result.match_score).toBeGreaterThanOrEqual(next.match_score);
      if (result.match_score === next.match_score) expect(result.id < next.id).toBe(true);
    }
    expect(first.results[0]).toMatchObject({ id: 'mock-01', match_score: 100 });
  });

  it('returns exactly the SearchResult fields, with no mock attributes', async () => {
    const { results } = await mockSearch(request(FIXTURE));
    for (const result of results) {
      expect(Object.keys(result).sort()).toEqual(
        ['id', 'image_url', 'listing_url', 'match_score', 'price', 'source', 'title'].sort(),
      );
    }
  });

  it('scores 20 per matching scalar plus 20 × Jaccard of the features', () => {
    const byId = Object.fromEntries(MOCK_POOL.map(({ id }) => [id, 0] as [string, number]));
    for (const result of rankListings(MOCK_POOL, FIXTURE).results)
      byId[result.id] = result.match_score;
    // mock-03: jacket, black, denim, slim fit, [hood, zipper] → 60 + 20 × 1/2.
    expect(byId['mock-03']).toBe(70);
    // mock-21: same as the fixture but no features → 80 + 20 × 0.
    expect(byId['mock-21']).toBe(80);
  });

  it('reshuffles the top results when the color changes black → brown', () => {
    const before = ids(FIXTURE);
    const after = ids({ ...FIXTURE, color: 'brown' });
    expect(after).not.toEqual(before);
    expect(after[0]).not.toBe(before[0]);
  });

  it('reshuffles the top results when the hood is removed', () => {
    const before = ids(FIXTURE);
    const after = ids({ ...FIXTURE, others: null });
    expect(after).not.toEqual(before);
    expect(after[0]).not.toBe(before[0]);
  });
});
