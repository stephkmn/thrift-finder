import { describe, expect, it } from 'vitest';
import { parseVocabulary, VOCABULARY } from '../lib/vocabulary';

describe('vocabulary', () => {
  it('loads every list from attributes.yaml, in file order', () => {
    for (const list of Object.values(VOCABULARY)) {
      expect(list.length).toBeGreaterThan(0);
    }
    expect(VOCABULARY.category[0]).toBe('jacket');
    expect(VOCABULARY.color).toHaveLength(17);
    expect(VOCABULARY.fit).toContain('regular fit');
    expect(VOCABULARY.features).toContain('hood');
    expect(VOCABULARY.features[0]).toBe('hood');
  });

  it('throws naming the missing key when the shape is wrong', () => {
    const good = {
      scalars: {
        category: { values: ['jacket'] },
        color: { values: ['black'] },
        fabric: { values: ['denim'] },
        fit: { values: ['regular fit'] },
      },
      others: { features: { hood: { phrase: 'a hood' } } },
    };
    expect(parseVocabulary(good).features).toEqual(['hood']);

    expect(() => parseVocabulary(null)).toThrow('(root)');
    expect(() => parseVocabulary({ ...good, others: {} })).toThrow('others.features');
    expect(() =>
      parseVocabulary({ ...good, scalars: { ...good.scalars, color: { templates: [] } } }),
    ).toThrow('scalars.color.values');
    expect(() =>
      parseVocabulary({ ...good, scalars: { ...good.scalars, fit: { values: [1] } } }),
    ).toThrow('scalars.fit.values[0]');
  });
});
