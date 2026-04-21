import { defineConfig } from '@hey-api/openapi-ts';

// Regenerate the TypeScript client from the running backend's OpenAPI spec.
//   1. start the backend:      just dev
//   2. generate:               pnpm -C frontend generate:client
// Output lives in src/client/ (gitignored) so it regenerates cleanly.
export default defineConfig({
  input: process.env.NAGARA_API_URL
    ? `${process.env.NAGARA_API_URL}/openapi.json`
    : 'http://127.0.0.1:8000/openapi.json',
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
