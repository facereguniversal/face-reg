# Production deployment (Docker Compose)

This guide covers running face-reg on a single VM with Docker Compose, TLS via Caddy, and Prometheus/Grafana observability.

## Prerequisites

- Docker Engine 24+ with Compose v2
- DNS pointing `DOMAIN` to the VM (for real TLS, replace `tls internal` in `deploy/Caddyfile` with your ACME/email block)
- Firewall: allow `443` (and `80` for redirects); restrict Grafana (`127.0.0.1:3000`) to VPN or SSH tunnel

## Quick deploy

```bash
cd deploy
cp .env.production.example .env.production
# Edit secrets: SECRET_KEY, POSTGRES password in DATABASE_URL, CHECKIN_DEVICE_TOKENS, CORS_ORIGINS, GRAFANA_ADMIN_PASSWORD

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build
```

HTTPS is served by Caddy on port 443 (reverse proxy to the API). The API container is not published directly in the production profile.

## Required environment variables

See `deploy/.env.production.example` for the full list. Production startup **fails fast** if:

- `SECRET_KEY` is missing or still the default placeholder
- `BOOTSTRAP_ON_STARTUP=true`
- `CORS_ORIGINS` contains `*` or is empty

## Operations

### Health checks

- `GET /api/health` returns **200** when database and model server are healthy, **503** when degraded (Compose marks the API unhealthy).
- Model server: `GET http://model_server:8001/health` (internal).

### Metrics

- API: `http://api:8000/metrics` (scrape from Prometheus only; do not expose publicly)
- Model server: `http://model_server:8001/metrics`
- Grafana: `http://127.0.0.1:3000` on the host (default admin password from `GRAFANA_ADMIN_PASSWORD`)

### Backups

1. **PostgreSQL:** `docker compose exec db pg_dump -U faceuser facedb > backup.sql`
2. **FAISS index:** snapshot the `model_data` volume (contains `faiss.index` and `faiss_id_map.json`)

### Rotating secrets

1. Update `.env.production`
2. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
3. Re-issue kiosk device tokens in `CHECKIN_DEVICE_TOKENS` and redeploy kiosk clients

### Logs

Production services use the `json-file` driver with rotation (`max-size` 10m, `max-file` 5). API request logs are JSON lines on stdout with `X-Request-ID`.

## Security notes

- Demo UIs (`/demo/*`) are disabled when `ENABLE_DEMO_UI=false`
- OpenAPI (`/docs`) is disabled when `ENVIRONMENT=production`
- `/api/faces/validate` requires JWT authentication
- User enroll/get routes enforce self-or-admin authorization
- Rate limits: login 10/min, check-in and validate 30/min
- WebSocket admin feed still passes token via query string (single-replica deployment); prefer header auth in future hardening

## Development vs production

| Concern | Dev (`docker-compose.yml`) | Prod (+ `docker-compose.prod.yml`) |
|--------|----------------------------|-------------------------------------|
| API port | 8000 published | Only via Caddy 443 |
| Bootstrap | Enabled | Disabled |
| Demo UI | Enabled | Disabled |
| TLS | None | Caddy |
| Observability | Optional | Prometheus + Grafana |
