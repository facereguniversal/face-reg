# Production deployment (Docker Compose)

Single-VM production stack: API + model server + PostgreSQL, TLS via Caddy, Prometheus + Grafana.

## 5-minute deploy (fresh Ubuntu VM)

```bash
# 1. Install Docker (https://docs.docker.com/engine/install/ubuntu/)
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin git

# 2. Clone and configure
git clone <your-repo-url> face-reg && cd face-reg/deploy
cp .env.production.example .env.production
${EDITOR:-nano} .env.production   # set DOMAIN, passwords, CORS_ORIGINS, CHECKIN_DEVICE_TOKENS

# 3. Validate and start
chmod +x scripts/*.sh
./scripts/bootstrap-production.sh

# 4. First admin (bootstrap is off in production)
./scripts/seed-admin.sh
```

One-liner after editing `.env.production`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## Prerequisites

- Docker Engine 24+ with Compose v2 (`docker compose`)
- Copy `deploy/.env.production.example` → `deploy/.env.production` (never commit the latter)
- **Firewall (minimum):** allow inbound `443` (and `80` for ACME redirects). Grafana is `127.0.0.1:3000` only — use SSH tunnel (`ssh -L 3000:127.0.0.1:3000 user@vm`) or VPN; do not expose 3000 publicly.

## Required environment variables

See `deploy/.env.production.example`. Run `./scripts/validate-env.sh` before deploy.

Production API startup **fails fast** when:

- `SECRET_KEY` is missing or still a placeholder/default
- `BOOTSTRAP_ON_STARTUP=true`
- `CORS_ORIGINS` contains `*` or is empty

Compose also requires `POSTGRES_PASSWORD`, `DATABASE_URL`, `CHECKIN_DEVICE_TOKENS`, and `GRAFANA_ADMIN_PASSWORD` to be set (see prod compose file).

## TLS: self-signed vs public domain

| Mode | `DOMAIN` | `deploy/Caddyfile` |
|------|----------|-------------------|
| Lab / IP demo | `localhost` or hostname | Keep `tls internal` (browser warning; use `curl -k`) |
| Public HTTPS | `faces.example.com` with DNS → VM | **Remove** the `tls internal` line; Caddy obtains Let's Encrypt certs (ports 80+443 open) |

`DOMAIN` is passed to the Caddy container and used as the site address.

## Hotel / kiosk demo UIs

Browser demos (`/demo/capture/`, `/demo/checkin/`, `/demo/admin/`) are **disabled** when `ENABLE_DEMO_UI=false` (default).

For an on-VM hotel demo served through Caddy on the same domain:

1. Set `ENABLE_DEMO_UI=true` in `.env.production`
2. Set `CORS_ORIGINS=https://<your-domain>` (must match browser origin)
3. Redeploy; open `https://<domain>/demo/checkin/?deviceId=...&deviceToken=...`

Alternatively host `ingestion/*_ui/` as static files on another origin and point them at `https://<domain>/api`.

## Operations

### Health checks

- `GET /api/health` returns **200** when database and model server are healthy, **503** when degraded.
- Compose/Docker healthchecks treat **503 as unhealthy** (expected for orchestration).
- Model server (internal): `GET http://model_server:8001/health`

### Metrics

- API: `http://api:8000/metrics` (Prometheus only; not public)
- Model server: `http://model_server:8001/metrics`
- Grafana: `http://127.0.0.1:3000` on the host (`GRAFANA_ADMIN_PASSWORD`)

### Backups

1. **PostgreSQL:** `docker compose exec db pg_dump -U faceuser facedb > backup.sql`
2. **FAISS index:** snapshot the `model_data` volume

### Rotating secrets

1. Update `.env.production`
2. `./scripts/validate-env.sh`
3. `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d`

### Logs

Production services use `json-file` logging with rotation (`max-size` 10m, `max-file` 5).

## Security notes

- `BOOTSTRAP_ON_STARTUP=false` in production compose override
- Demo UIs off by default (`ENABLE_DEMO_UI=false`)
- OpenAPI (`/docs`) disabled when `ENVIRONMENT=production`
- Example env file uses placeholders only — no real passwords
- Rate limits: login 10/min; check-in and validate 30/min

## Development vs production

| Concern | Dev (`docker-compose.yml`) | Prod (+ `docker-compose.prod.yml`) |
|--------|----------------------------|-------------------------------------|
| API port | 8000 published | Only via Caddy 443 |
| Bootstrap | Enabled | Disabled — use `scripts/seed-admin.sh` |
| Demo UI | Enabled | Off by default (`ENABLE_DEMO_UI`) |
| TLS | None | Caddy |
| Observability | Optional | Prometheus + Grafana |
