import { describe, expect, it } from 'vitest';
import { COLOR_SWATCHES, swatchBackground, UNKNOWN_SWATCH } from '../lib/colorSwatches';
import { VOCABULARY } from '../lib/vocabulary';

describe('color swatches', () => {
  it('has a hex swatch for every vocabulary color', () => {
    for (const color of VOCABULARY.color) {
      expect(COLOR_SWATCHES[color], color).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it('draws multicolor as a gradient and unknown colors as a neutral fill', () => {
    expect(swatchBackground('multicolor')).toMatch(/^linear-gradient\(/);
    expect(swatchBackground('brown')).toBe(COLOR_SWATCHES.brown);
    expect(swatchBackground('teal')).toBe(UNKNOWN_SWATCH);
  });
});
