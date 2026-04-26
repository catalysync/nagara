# nagara frontend

Next.js 15 + Tailwind v4 + a shared component library. Configuration
conventions (tsconfig, postcss, vitest, eslint) follow the common
monorepo-with-design-system pattern.

## Prerequisites

- Node.js 22+
- pnpm 9+
- The nagara backend running somewhere reachable (defaults to
  `http://127.0.0.1:8000`; override with `NAGARA_API_URL`)
- The shared `@aspect/*` packages must resolve — see
  **Linking the component library** below.

## Scripts

```bash
pnpm dev               # next dev --turbopack
pnpm build             # next build --turbopack
pnpm lint              # next lint
pnpm typecheck         # tsc --noEmit
pnpm test              # vitest
pnpm generate:client   # regenerate src/client/ from frontend/openapi.json
```

Shortcuts from the repo root invoke these via pnpm filters:

```bash
pnpm dev               # same as `pnpm --filter frontend dev`
pnpm typecheck
pnpm test
```

To regenerate the API client without spinning up the backend, run
`./scripts/generate-client.sh` from the repo root — it dumps the OpenAPI
spec in-process and feeds it into this package's generator.

## API requests

`next.config.ts` rewrites `/api/*` to the backend's root so the browser
always hits same-origin. Set `NAGARA_API_URL` at build/start time to point
at a non-default host.

Generated client code lives in `src/client/` (gitignored). Run
`pnpm generate:client` after any backend schema change.

## Linking the component library

The `@aspect/*` packages (design tokens, CSS, React components) are
workspace dependencies. Until they're published to a registry, resolve
them locally:

1. Clone the component-library repo as a sibling directory.
2. Swap the `workspace:^` specifiers in `package.json` to
   `"file:../../<repo-name>/packages/<name>"` for local dev (don't commit
   the rewrite).
3. Or, publish the packages and replace `workspace:^` with a version range.
