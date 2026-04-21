# nagara frontend

Next.js 15 + Tailwind v4 + [mizu](https://github.com/catalysync/mizu) design
system. Matches the configuration conventions used in `apps/tweakmizu` so it
should feel native to anyone who worked on mizu.

## Prerequisites

- Node.js 22+
- pnpm 9+
- The nagara backend running somewhere reachable (defaults to
  `http://127.0.0.1:8000`; override with `NAGARA_API_URL`)
- Mizu's `@aspect/*` packages must resolve. They aren't on a public registry
  yet. For local development clone `catalysync/mizu` as a sibling directory
  and link the packages — see **Linking mizu locally** below.

## Scripts

```bash
pnpm dev               # next dev --turbopack
pnpm build             # next build --turbopack
pnpm lint              # next lint
pnpm typecheck         # tsc --noEmit
pnpm test              # vitest
pnpm generate:client   # regenerate src/client/ from the backend's /openapi.json
```

Shortcuts from the repo root invoke these via pnpm filters:

```bash
pnpm dev               # same as `pnpm --filter frontend dev`
pnpm typecheck
pnpm test
```

## API requests

`next.config.ts` rewrites `/api/*` to the backend's root so the browser
always hits same-origin. Set `NAGARA_API_URL` at build/start time to point
at a non-default host.

Generated client code lives in `src/client/` (gitignored). Run
`pnpm generate:client` after any backend schema change; the backend must be
running for the OpenAPI spec to be fetchable.

## Linking mizu locally

Until `@aspect/*` packages are published, either:

1. Clone mizu as a sibling of `nagara` and swap the `workspace:^` specifiers
   in `package.json` to `"file:../../mizu/packages/<name>"` locally. Don't
   commit the rewrite.
2. Or, publish mizu to GitHub Packages / npm and replace `workspace:^` with
   a version range.
