# Changelog

All notable changes are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- FastAPI factory (`create_app`) with lifespan registry (`@on_startup` /
  `@on_shutdown`) and Kubernetes-ready health probes (`/health/live`,
  `/health/ready`).
- Typed exception envelope (`NagaraError`, `BadRequest`, `Unauthorized`,
  `Forbidden`, `NotFound`, `Conflict`, `Gone`, `ValidationFailed`,
  `InternalServerError`, `TaskError`) with auto `error_code` snake-case.
- Custom `APIRoute` mixing auto-commit of the first `AsyncSession` arg and
  OpenAPI inclusion gated by `APITag.public` / `APITag.internal`.
- Stable, kebab-case OpenAPI `operation_id` generator for typed-client codegen.
- Cross-cutting middleware: request-id, content-size limit, request-cancel
  (499 on disconnect), multipart-boundary validation, security headers,
  forwarded-prefix, query-list flattening.
- `kit/` package: `utils`, `schemas`, `pagination`, `sorting`, `repository`,
  `pubsub`, `sse`, `paths`, `redis`, `compression`.
- Layered settings (env > .env > TOML > defaults) with `temporary_settings`
  contextvar override and `verify_settings` production preflight.
- Redis-backed `slowapi` rate limiting with typed 429 envelope and
  multiplier-aware `Retry-After`.
- Sentry integration with `before_send` filter for typed errors.
- structlog dev/prod renderer split with stdlib `dictConfig` integration.
- Postgres minimum-version preflight check at startup.
- `py.typed` marker; public surface re-exported from `nagara`.
