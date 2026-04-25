# Security policy

## Reporting a vulnerability

**Please do not open a public issue.** Instead use GitHub's
[private vulnerability reporting](https://github.com/catalysync/nagara/security/advisories/new)
to disclose the issue privately.

If you cannot use GitHub for any reason, email `security@catalysync.dev`.
We aim to acknowledge reports within 48 hours and to ship a fix or
public advisory within 14 days for confirmed issues.

## Supported versions

nagara is pre-1.0. Only the latest `main` branch is supported. Once we
ship 1.0 we'll publish a versioned support window here.

## Hardening defaults

Out of the box nagara:

- Enforces typed-exception envelopes so internal stack traces never reach clients
- Stamps every request with a UUID and propagates it into structured logs and Sentry events
- Rejects oversized request bodies via `ContentSizeLimitMiddleware`
- Rejects unsafe path segments via `kit.paths.safe_join` / `ValidatedFileName`
- Defaults `CORS_ALLOW_CREDENTIALS=False` and refuses to start with `*` + credentials
- Issues short-lived JWT access tokens + longer-lived refresh tokens (Argon2id-hashed passwords)
- Uses Sentry's `before_send` filter to drop typed-error events from production noise

If you find a default that's weaker than this list claims, that's a security issue —
please report it.
