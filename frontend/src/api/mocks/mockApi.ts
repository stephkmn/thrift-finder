import { ApiError } from '../errors';
import type { ExtractResponse } from '../types';
import fixture from './extract.json';

/** Submitting exactly this text makes the mock fail, so the error UI can be demoed. */
export const MOCK_ERROR_TRIGGER = '__error__';

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
    throw new ApiError(500, 'Something went wrong while analyzing your item. Please try again.');
  }
  const response = structuredClone(fixture) as ExtractResponse;
  return { ...response, query_id: mockQueryId() };
}
