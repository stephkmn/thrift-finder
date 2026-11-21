import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// jsdom has no object URLs; the preview only needs a string back.
URL.createObjectURL = vi.fn(() => 'blob:test-preview');
URL.revokeObjectURL = vi.fn();

// jsdom doesn't implement scrolling; the board and details page only ask for it.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
