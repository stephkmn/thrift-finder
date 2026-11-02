import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // FastAPI (Member C) runs on its default port during development.
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    // Tests opt into mocks per case; keep fake latency at zero unless a test needs it.
    env: { VITE_MOCK_DELAY_MS: '0' },
  },
});
