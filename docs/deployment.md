# Deployment

Two supported paths: **Kubernetes (Helm)** is the production default; **Docker
Compose** is the quick-start / small-deploy option. Both run the same image;
only the orchestration differs.

## Image

Published to GitHub Container Registry via `.github/workflows/docker.yml`:

```
ghcr.io/catalysync/nagara:<tag>
```

Tags follow semver (`v0.1.0`) plus `main-<sha>` for every main commit and
`pr-<n>-<sha>` for PR builds. Multi-arch: `linux/amd64` + `linux/arm64`.

---

## Kubernetes (Helm)

Chart: `deploy/helm/nagara-core/`.

### Install

```bash
helm install nagara ./deploy/helm/nagara-core \
  --namespace nagara --create-namespace \
  --set image.tag=v0.1.0 \
  --set secrets.NAGARA_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))") \
  --set secrets.NAGARA_POSTGRES_PWD=$(openssl rand -base64 32) \
  --set env.NAGARA_POSTGRES_HOST=my-postgres.svc.cluster.local
```

### What the chart provisions

- `Deployment` — the app, non-root, readonly rootfs, resource limits
- `Service` — ClusterIP on port 8000
- `ConfigMap` — non-secret settings from `values.env.*`
- `Secret` — populated from `values.secrets.*` unless `existingSecret` is set
- `ServiceAccount`
- `HorizontalPodAutoscaler` — disabled by default; enable with `autoscaling.enabled=true`
- `Ingress` — disabled by default; enable with `ingress.enabled=true`

### Migrations

The chart runs `alembic upgrade head` as an **init container** before the
app container starts. Same image, different command. That means multiple
replicas can never race to migrate, and a failing migration blocks rollout
rather than booting a broken app.

Disable with `migrations.enabled=false` if you run migrations out-of-band.

### Probes

- **Liveness** — `/health/live`, cheap, no dependency checks.
- **Readiness** — `/health/ready`, `SELECT 1` against Postgres. Returns 503
  when the DB is unreachable so Kubernetes pulls the pod out of the Service
  endpoint list during outages without killing it.

### Secrets

The chart supports three modes:

1. **`existingSecret: "my-secret"`** — point at a Secret you manage out of
   band (via External Secrets Operator, sealed-secrets, Vault agent
   injector, …). **Recommended for production.**
2. **`secrets.NAGARA_SECRET_KEY=...`** — inline plaintext, rendered into a
   chart-owned Secret. Acceptable for dev / staging.
3. **Neither** — the Secret is rendered with empty values; `NAGARA_ENV=production`
   + empty `NAGARA_SECRET_KEY` will make the app refuse to start.

Required secrets:

| Key | Purpose |
|-----|---------|
| `NAGARA_SECRET_KEY` | Signs JWTs. Must be ≥32 chars in production. |
| `NAGARA_POSTGRES_PWD` | Database password. |

### Postgres

The chart does **not** ship Postgres — bring your own. Options:

- **Managed** (recommended for prod): RDS / Cloud SQL / Supabase / Neon / …
- **CloudNativePG operator** — run Postgres in-cluster with HA + backups.
- **Bitnami's `bitnami/postgresql` chart** — simplest in-cluster option for
  single-node dev clusters.

Set `env.NAGARA_POSTGRES_HOST`, `env.NAGARA_POSTGRES_PORT`, `env.NAGARA_POSTGRES_DB`,
`env.NAGARA_POSTGRES_USER`, and `secrets.NAGARA_POSTGRES_PWD` accordingly.

### TLS / ingress

The chart's Ingress is minimal. For HTTPS:

- [cert-manager](https://cert-manager.io/) + Let's Encrypt — standard path
- Cloud-provider ingress controller TLS — works out of the box on AWS ALB,
  GCP GCLB, etc.

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: nagara.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts: [nagara.example.com]
      secretName: nagara-tls
```

### Scaling

nagara core is **stateless** — no in-process caches or session state beyond
short-lived JWTs. Scale horizontally by increasing `replicaCount` or
enabling the HPA.

Postgres is the bottleneck; use read replicas + PgBouncer for significant
load. Connection pool tuning via `env.NAGARA_DATABASE_POOL_SIZE`.

---

## Docker Compose

For single-node deploys, demos, or self-hosters who don't want Kubernetes.

### Start

```bash
cp .env.example .env
# edit .env — at minimum set NAGARA_SECRET_KEY
docker compose --profile app up -d
```

The `app` profile starts: `postgres` → `redis` → `prestart` (runs
`alembic upgrade head`) → `app`. The `prestart` service mirrors the k8s
init-container pattern so migrations can't race.

### Dev vs prod stacks

- `docker-compose.yml` — production-shaped base
- `docker-compose.override.yml` — dev extras (source mount, `uvicorn --reload`).
  Compose auto-applies it on plain `docker compose up`.
- Explicitly for production: `docker compose -f docker-compose.yml up`

### Reverse proxy + TLS

Compose doesn't ship a reverse proxy. Use whatever you already know:

- **Caddy** — simplest auto-HTTPS; one-liner config for port 8000.
- **Traefik** — if you want labels-driven routing.
- **nginx + certbot** — classic.

Point the proxy at `http://<host>:8000` and terminate TLS there.

### Persistence

Postgres data lives in the `postgres_data` named volume. Back it up with
`pg_dump` on a schedule (cron job on the host is fine).

---

## CI/CD

The included workflow (`.github/workflows/docker.yml`) builds + pushes the
image to GHCR on every push to `main` and on tags. Multi-arch, cache-friendly.

For automated deploys:

- **GitOps** (Argo CD / Flux) — most operators do this. Helm chart lives
  in this repo; deployment repo watches it.
- **Helm upgrade from CI** — add a step to your pipeline: `helm upgrade
  nagara ./deploy/helm/nagara-core --install --reuse-values --set
  image.tag=$SHA`.

---

## Upgrades

```bash
helm upgrade nagara ./deploy/helm/nagara-core \
  --reuse-values --set image.tag=v0.2.0
```

The migration init container runs on every upgrade, applying any new
alembic revisions before the app starts. Breaking schema changes will fail
the init container — rollback with `helm rollback nagara`.

---

## Observability

- **Logs** — stdout JSON, collected by your log aggregator (Loki, Datadog,
  CloudWatch, …).
- **Metrics** — Prometheus ServiceMonitor template is in the chart but
  commented out; enable once you've wired up a metrics endpoint.
- **Traces** — OpenTelemetry hooks are a follow-up; nothing shipped yet.
