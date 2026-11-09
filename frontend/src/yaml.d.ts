/** `*.yaml` / `*.yml` imports are parsed at build time by the yaml-as-json plugin in vite.config.ts. */
declare module '*.yaml' {
  const data: unknown;
  export default data;
}

declare module '*.yml' {
  const data: unknown;
  export default data;
}
