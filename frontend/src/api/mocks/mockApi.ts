import { ApiError } from '../errors';
import type {
  Attributes,
  AttributeComparison,
  ExtractResponse,
  ItemDetails,
  SearchRequest,
  SearchResponse,
} from '../types';
import fixture from './extract.json';
import { MOCK_POOL } from './searchPool';
import type { MockListing } from './searchPool';

/** Submitting exactly this text makes the mock fail, so the error UI can be demoed. */
export const MOCK_ERROR_TRIGGER = '__error__';

/** This description extracts fine, then makes the mock search fail. */
export const MOCK_SEARCH_ERROR_TRIGGER = '__search_error__';

const DEFAULT_DELAY_MS = 600;

function mockDelayMs(): number {
  const parsed = Number(import.meta.env.VITE_MOCK_DELAY_MS);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_DELAY_MS;
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// crypto.randomUUID only exists in secure contexts, and phones testing over LAN use plain http.
function mockQueryId(): string {
  const id =
    typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2, 12);
  return `mock-${id}`;
}

export async function mockExtract(input: {
  image?: File;
  text?: string;
}): Promise<ExtractResponse> {
  await wait(mockDelayMs());
  if (input.text === MOCK_ERROR_TRIGGER) {
    throw new ApiError(500, "We couldn't read your item. Try again.");
  }
  const response = structuredClone(fixture) as ExtractResponse;
  return { ...response, query_id: mockQueryId() };
}

const SCALARS = ['category', 'color', 'fabric', 'fit'] as const;
const MAX_RESULTS = 10;

/** |A ∩ B| / |A ∪ B|, with null as the empty set and two empty sets counting as a full match. */
function jaccard(a: string[] | null, b: string[] | null): number {
  const left = new Set(a ?? []);
  const right = new Set(b ?? []);
  const union = new Set([...left, ...right]);
  if (union.size === 0) return 1;
  let shared = 0;
  for (const item of left) if (right.has(item)) shared++;
  return shared / union.size;
}

/**
 * Equal-weight overlap, 0–100: 20 points each for matching category, color, fabric, and fit,
 * plus 20 × Jaccard similarity of the `others` features. Stands in for the S2-5 re-ranker.
 */
export function mockMatchScore(listing: Attributes, query: Attributes): number {
  const scalarPoints = SCALARS.filter((name) => listing[name] === query[name]).length * 20;
  return scalarPoints + 20 * jaccard(listing.others, query.others);
}

/** Top 10 by score, ties broken by id, with the mock-only `attributes` stripped off. */
export function rankListings(pool: MockListing[], query: Attributes): SearchResponse {
  const ranked = pool
    .map(({ attributes, ...result }) => ({
      ...result,
      match_score: mockMatchScore(attributes, query),
    }))
    .sort((a, b) => b.match_score - a.match_score || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return { results: ranked.slice(0, MAX_RESULTS) };
}

export async function mockSearch(request: SearchRequest): Promise<SearchResponse> {
  await wait(mockDelayMs());
  if (request.text === MOCK_SEARCH_ERROR_TRIGGER) {
    throw new ApiError(500, "We couldn't load your matches. Try again.");
  }
  return rankListings(MOCK_POOL, request.edited_attributes);
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * GET /api/item/{id} in mock mode. Like the backend, only archive (`local`) items have details;
 * mock eBay items and unknown ids are 404. Mock labels are already in our vocabulary, so a
 * match is plain equality.
 */
export async function mockGetItem(id: string, searched?: Attributes): Promise<ItemDetails> {
  await wait(mockDelayMs());
  const listing = MOCK_POOL.find((item) => item.id === id && item.source === 'local');
  if (!listing) throw new ApiError(404, "This listing isn't available anymore.");
  const { attributes } = listing;
  const comparison: AttributeComparison[] = searched
    ? SCALARS.map((name) => ({
        attribute: name,
        yours: searched[name],
        listing: attributes[name],
        match: attributes[name] === searched[name],
      }))
    : [];
  return {
    id: listing.id,
    title: listing.title,
    image_url: listing.image_url,
    source: 'local',
    dataset_labels: {
      type: capitalize(attributes.category),
      category: null,
      colors: [capitalize(attributes.color)],
      material: attributes.fabric,
      cut: capitalize(attributes.fit.replace(' fit', '')),
      pattern: null,
      brand: null,
    },
    comparison,
    credit: {
      text: 'Second-Hand Fashion dataset, Nauman (2024), CC BY 4.0. Photo resized.',
      url: 'https://huggingface.co/datasets/fnauman/fashion-second-hand-front-only-rgb',
    },
  };
}
