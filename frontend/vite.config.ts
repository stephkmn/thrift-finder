import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { searchForWorkspaceRoot } from 'vite';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';
import { parse } from 'yaml';

// The attribute vocabulary is owned by Member A (ML) in the backend; the UI reads it at build time.
const VOCABULARY_FILE = fileURLToPath(
  new URL('../backend/app/ml/attributes.yaml', import.meta.url),
);

const YAML_FILE = /\.ya?ml$/i;
// Imports that ask Vite for something other than the parsed module (?raw text, ?url, ...).
const LEAVE_TO_VITE = /(?:^|&)(?:raw|url|inline|worker|sharedworker)(?:[=&]|$)/;

/**
 * Turns `*.yaml` / `*.yml` imports into JSON modules. Runs for dev, build, and Vitest alike.
 * Ids can carry a query (e.g. a dev-server `?v=` hash), so match on the path part only.
 */
function yamlAsJson(): Plugin {
  return {
    name: 'yaml-as-json',
    transform(code, id) {
      const queryStart = id.indexOf('?');
      const path = queryStart === -1 ? id : id.slice(0, queryStart);
      const query = queryStart === -1 ? '' : id.slice(queryStart + 1);
      if (!YAML_FILE.test(path) || LEAVE_TO_VITE.test(query)) return null;
      return { code: `export default ${JSON.stringify(parse(code))};`, map: null };
    },
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), yamlAsJson()],
  server: {
    fs: {
      // Keep the default workspace root and open up only the one backend file the UI needs.
      allow: [searchForWorkspaceRoot(process.cwd()), VOCABULARY_FILE],
    },
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
