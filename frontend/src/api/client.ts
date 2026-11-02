import { ApiError } from './errors';
import { mockExtract } from './mocks/mockApi';
import type { ExtractResponse } from './types';

export { ApiError } from './errors';

export interface ExtractInput {
  image?: File;
  text?: string;
}

// Read at call time (not module load) so tests can flip the flag with vi.stubEnv.
function mocksEnabled(): boolean {
  return import.meta.env.VITE_USE_MOCKS === 'true';
}

function messageForStatus(status: number): string {
  if (status === 413) return 'That photo is too large for the server. Try a smaller image.';
  if (status === 415 || status === 422)
    return "The server couldn't read that photo. Try a JPG or PNG.";
  if (status === 429) return 'Too many requests right now. Wait a moment and try again.';
  return 'Something went wrong while analyzing your item. Please try again.';
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

  let response: Response;
  try {
    response = await fetch('/api/extract', { method: 'POST', body });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check that the backend is running.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, messageForStatus(response.status));
  }
  return (await response.json()) as ExtractResponse;
}
