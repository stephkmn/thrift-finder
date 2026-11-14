import { ApiError } from './errors';
import { mockExtract, mockGetItem, mockSearch } from './mocks/mockApi';
import type {
  Attributes,
  ExtractResponse,
  ItemDetails,
  SearchRequest,
  SearchResponse,
} from './types';

export { ApiError } from './errors';

export interface ExtractInput {
  image?: File;
  text?: string;
}

// Read at call time (not module load) so tests can flip the flag with vi.stubEnv.
function mocksEnabled(): boolean {
  return import.meta.env.VITE_USE_MOCKS === 'true';
}

const RATE_LIMITED = 'Too many requests right now. Wait a moment and try again.';

function extractMessageForStatus(status: number): string {
  if (status === 413) return 'That photo is too large for the server. Try a smaller image.';
  if (status === 415 || status === 422)
    return "The server couldn't read that photo. Try a JPG or PNG.";
  if (status === 429) return RATE_LIMITED;
  return 'Your item could not be analyzed. Please try again.';
}

function searchMessageForStatus(status: number): string {
  if (status === 429) return RATE_LIMITED;
  return 'Your matches could not be loaded. Please try again.';
}

/** fetch() that turns network failures and non-2xx responses into user-safe ApiErrors. */
async function request<T>(
  url: string,
  init: RequestInit,
  messageForStatus: (status: number) => string,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check that the backend is running.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, messageForStatus(response.status));
  }
  return (await response.json()) as T;
}

/** POST /api/extract — photo and/or text in, attributes with confidences out. */
export async function extract(input: ExtractInput): Promise<ExtractResponse> {
  const image = input.image;
  const text = input.text?.trim() || undefined;
  if (!image && !text) {
    throw new Error('extract() needs an image, text, or both.');
  }

  if (mocksEnabled()) {
    return mockExtract({ image, text });
  }

  const body = new FormData();
  if (image) body.append('image', image);
  if (text) body.append('text', text);

  return request<ExtractResponse>(
    '/api/extract',
    { method: 'POST', body },
    extractMessageForStatus,
  );
}

/** POST /api/search — original and edited attributes in, up to 10 ranked listings out. */
export async function search(searchRequest: SearchRequest): Promise<SearchResponse> {
  if (mocksEnabled()) {
    return mockSearch(searchRequest);
  }

  return request<SearchResponse>(
    '/api/search',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(searchRequest),
    },
    searchMessageForStatus,
  );
}

function itemMessageForStatus(status: number): string {
  if (status === 404) return 'This listing is no longer available.';
  return 'This listing could not be loaded. Please try again.';
}

/**
 * GET /api/item/{id} — an archive listing's details. Pass the attributes of the search that
 * found it to get the "why it matched" comparison.
 */
export async function getItem(id: string, searched?: Attributes): Promise<ItemDetails> {
  if (mocksEnabled()) {
    return mockGetItem(id, searched);
  }

  const params = new URLSearchParams();
  if (searched) {
    for (const name of ['category', 'color', 'fabric', 'fit'] as const) {
      params.set(name, searched[name]);
    }
  }
  const query = params.toString();
  return request<ItemDetails>(
    `/api/item/${encodeURIComponent(id)}${query ? `?${query}` : ''}`,
    { method: 'GET' },
    itemMessageForStatus,
  );
}
