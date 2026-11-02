interface ImportMetaEnv {
  /** "true" routes API calls to the in-browser mocks in src/api/mocks. */
  readonly VITE_USE_MOCKS?: string;
  /** Fake latency for mock responses, in milliseconds. Defaults to 600. */
  readonly VITE_MOCK_DELAY_MS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
