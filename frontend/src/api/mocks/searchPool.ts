import { COLOR_SWATCHES, MULTICOLOR_STOPS } from '../../lib/colorSwatches';
import type { Attributes, SearchResult } from '../types';

/** A fake listing plus the attributes the mock ranks it by. `attributes` never leaves the mock. */
export interface MockListing extends SearchResult {
  attributes: Attributes;
}

type Spec = [
  category: string,
  color: string,
  fabric: string,
  fit: string,
  others: string[] | null,
  price: number | null, // null = a local archive item
];

// Every value comes from backend/app/ml/attributes.yaml (checked in mockSearch.test.ts).
// The pool is built around the extract fixture (black denim regular-fit jacket with a hood)
// so that a single edit — black → brown, or removing the hood — reshuffles the top 10.
const SPECS: Spec[] = [
  ['jacket', 'black', 'denim', 'regular fit', ['hood'], 48],
  ['trucker jacket', 'black', 'denim', 'regular fit', ['buttons'], null],
  ['jacket', 'black', 'denim', 'slim fit', ['hood', 'zipper'], 55],
  ['jacket', 'brown', 'suede', 'regular fit', ['hood'], 62],
  ['jacket', 'brown', 'denim', 'regular fit', null, null],
  ['trucker jacket', 'brown', 'suede', 'regular fit', ['buttons'], 85],
  ['jacket', 'brown', 'leather', 'oversized', ['zipper'], null],
  ['bomber jacket', 'black', 'nylon', 'regular fit', ['zipper'], 40],
  ['parka', 'black', 'nylon', 'oversized', ['hood', 'fur trim'], 95],
  ['jacket', 'black', 'leather', 'slim fit', null, 70],
  ['jacket', 'black', 'denim', 'cropped', null, null],
  ['jacket', 'brown', 'denim', 'cropped', ['hood'], 38],
  ['coat', 'black', 'wool', 'regular fit', null, null],
  ['windbreaker', 'black', 'nylon', 'regular fit', ['hood'], 30],
  ['jacket', 'tan', 'suede', 'regular fit', ['hood'], null],
  ['peacoat', 'navy', 'wool', 'regular fit', ['double-breasted', 'buttons'], 75],
  ['puffer jacket', 'black', 'nylon', 'regular fit', ['hood', 'quilted'], 65],
  ['jacket', 'brown', 'corduroy', 'regular fit', ['buttons'], null],
  ['fleece jacket', 'gray', 'fleece', 'regular fit', ['zipper'], 28],
  ['trench coat', 'tan', 'cotton', 'longline', ['belt', 'buttons'], null],
  ['jacket', 'black', 'denim', 'regular fit', null, 52],
  ['jacket', 'olive', 'canvas', 'regular fit', ['hood', 'cargo pockets'], 58],
  ['varsity jacket', 'burgundy', 'wool', 'regular fit', ['patches'], null],
  ['jacket', 'brown', 'denim', 'regular fit', ['hood'], null],
  ['shacket', 'black', 'corduroy', 'oversized', ['plaid', 'buttons'], 34],
  ['jacket', 'black', 'suede', 'regular fit', ['fur trim'], null],
  ['jacket', 'multicolor', 'nylon', 'oversized', ['color-block', 'zipper'], 44],
  ['blazer', 'cream', 'wool', 'slim fit', null, null],
];

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** e.g. "Brown suede trucker jacket", "Cropped black denim jacket with a hood". */
function titleFor({ category, color, fabric, fit, others }: Attributes): string {
  const words = [fit === 'regular fit' ? '' : fit.replace(' fit', ''), color, fabric, category];
  const hood = others?.includes('hood') ? ' with a hood' : '';
  return capitalize(words.filter(Boolean).join(' ') + hood);
}

/** Relative luminance from a #rrggbb hex, enough to pick a readable label color. */
function isLight(hex: string): boolean {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55;
}

/** A placeholder "photo": the item's color with its category name. No real images. */
function placeholderImage(color: string, category: string): string {
  const fill = COLOR_SWATCHES[color];
  const gradient =
    color === 'multicolor'
      ? `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">${MULTICOLOR_STOPS.map(
          (stop, i) => `<stop offset="${i / (MULTICOLOR_STOPS.length - 1)}" stop-color="${stop}"/>`,
        ).join('')}</linearGradient></defs>`
      : '';
  const ink = color !== 'multicolor' && isLight(fill) ? '#0f2240' : '#ffffff';
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500">${gradient}` +
    `<rect width="400" height="500" fill="${gradient ? 'url(#g)' : fill}"/>` +
    // A simple jacket outline so the tile reads as clothing, not a flat color chip.
    `<path d="M150 90 200 120 250 90 330 130 350 330 300 340 300 420 100 420 100 340 50 330 70 130Z" ` +
    `fill="none" stroke="${ink}" stroke-opacity="0.45" stroke-width="6" stroke-linejoin="round"/>` +
    `<path d="M200 120V420" stroke="${ink}" stroke-opacity="0.45" stroke-width="4"/>` +
    `<text x="200" y="470" fill="${ink}" font-family="Georgia, serif" font-size="28" ` +
    `text-anchor="middle">${category}</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export const MOCK_POOL: MockListing[] = SPECS.map(
  ([category, color, fabric, fit, others, price], index) => {
    const id = `mock-${String(index + 1).padStart(2, '0')}`;
    const attributes: Attributes = { category, color, fabric, fit, others };
    const isEbay = price !== null;
    return {
      id,
      title: titleFor(attributes),
      price,
      image_url: placeholderImage(color, category),
      listing_url: isEbay ? `https://example.com/mock-listing/${id}` : null,
      source: isEbay ? 'ebay' : 'local',
      match_score: 0,
      attributes,
    };
  },
);
