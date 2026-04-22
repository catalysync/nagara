import { defineConfig } from '@hey-api/openapi-ts';

// Regenerate the TypeScript client from a dumped OpenAPI spec.
//
//   from repo root:  ./scripts/generate-client.sh
//   or inside frontend:  pnpm generate:client   (after the spec is dumped)
//
// The script calls `app.openapi()` in-process and writes `frontend/openapi.json`,
// so no backend has to be running for client regeneration.
export default defineConfig({
  input: './openapi.json',
  output: {
    path: 'src/client',
    format: 'prettier',
    lint: 'eslint',
  },
  plugins: [
    '@hey-api/client-fetch',
    { name: '@hey-api/sdk', asClass: true },
    '@hey-api/schemas',
    '@hey-api/typescript',
  ],
});
