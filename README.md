# Face Recognition Web Service

A demo-ready face recognition stack built with FastAPI, InsightFace/ArcFace, FAISS, and PostgreSQL.

> Status: Docker Compose is the supported deployment path for the current demo. The Kubernetes manifests are still draft assets and are not treated as a supported deployment target yet.

## What Works

- `POST /api/users/{id}/faces` enrolls 4 to 6 images per user.
- `POST /api/identify` performs 1:N search against enrolled templates.
- `POST /api/verify` performs 1:1 verification against a target user.
- `POST /api/faces/validate` checks image quality and rejects non-embeddable inputs.
- `/demo/capture/` and `/demo/checkin/` serve the browser demos from the API host.
- Docker Compose seeds a demo admin account on startup so login works without manual DB edits.

## Project Layout

```text
face-reg/
├── .github/workflows/       # CI
├── api/                     # FastAPI app, auth, services, bootstrap
├── db/                      # Schema and migration notes
├── deploy/                  # Dockerfiles, Compose, draft k8s manifests
├── docs/                    # API and architecture docs
├── ingestion/               # Browser demos and preprocessing helpers
├── model_server/            # InsightFace + FAISS service
├── tests/                   # Pytest suite
└── README.md
```

## Quick Start

Prerequisites:

- Docker Engine with Compose
- Port `8000` available on the host

Run the stack:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

The Compose setup publishes only the API port. PostgreSQL and the model server stay internal to the Compose network.

Available URLs:

- API root: `http://localhost:8000/`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`
- Capture demo: `http://localhost:8000/demo/capture/`
- Check-in demo: `http://localhost:8000/demo/checkin/`

Seeded demo admin:

- Email: `admin@example.com`
- Password: `adminpass`

Smoke-test login:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"adminpass"}'
```

Stop and clean up:

```bash
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml down -v
```

## Demo Bootstrap

Startup seeding is controlled through environment variables:

```bash
BOOTSTRAP_ON_STARTUP=true
BOOTSTRAP_ADMIN_NAME="Demo Admin"
BOOTSTRAP_ADMIN_EMAIL="admin@example.com"
BOOTSTRAP_ADMIN_PASSWORD="adminpass"
# Optional:
# BOOTSTRAP_USERS_FILE=/app/seeds/demo-users.json
```

Optional seed file format:

```json
{
  "users": [
    {
      "name": "Front Desk Demo",
      "email": "frontdesk@example.com",
      "password": "change-me",
      "role": "admin",
      "metadata": { "seeded": true }
    },
    {
      "name": "Guest Demo",
      "email": "guest@example.com",
      "role": "user",
      "metadata": { "group": "demo" }
    }
  ]
}
```

The demo UIs read the API host from `window.location.origin`, so they work from a remote browser against a single VM without editing frontend code.

## API Summary

Authentication:

- `POST /api/auth/login`
- `POST /api/auth/refresh`

Users:

- `POST /api/users`
- `GET /api/users/{user_id}`
- `DELETE /api/users/{user_id}`

Faces:

- `POST /api/users/{user_id}/faces`
- `POST /api/faces/validate`
- `GET /api/faces/{template_id}`
- `DELETE /api/faces/{template_id}`

Recognition:

- `POST /api/identify`
- `POST /api/identify/batch`
- `POST /api/verify`

Utility:

- `GET /api/health`

See [docs/api_reference.md](docs/api_reference.md) for request and response examples.

## Local Development

Prerequisites:

- Python 3.11+
- PostgreSQL 14+

Setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
pip install -r model_server/requirements.txt
```

Initialize the database:

```bash
createdb facedb
psql facedb < db/schema.sql
```

Required environment variables:

```bash
export DATABASE_URL="postgresql+asyncpg://faceuser:facepass@localhost:5432/facedb"
export SECRET_KEY="your-secret-key-here"
export MODEL_SERVER_URL="http://localhost:8001"
```

Run the services from the repo root:

```bash
uvicorn model_server.embed:app --host 0.0.0.0 --port 8001 --reload
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testing

Run the full suite:

```bash
pytest -v
```

Checks used in CI:

```bash
black --check api model_server tests
flake8 api model_server tests --max-line-length 120
docker build -f deploy/Dockerfile.api -t face-api:ci .
docker build -f deploy/Dockerfile.model -t face-model:ci .
```

## Limitations

- The demo stack is optimized for a single host and CPU inference.
- The Kubernetes manifests under `deploy/k8s/` are draft references, not a verified deployment path.
- Real biometric demo data should stay outside Git and be mounted or copied in only for rehearsal/demo use.

## Documentation

- [Architecture](docs/architecture.md)
- [API Reference](docs/api_reference.md)
- [Contributing Guidelines](docs/contrib_guidelines.md)
- [Implementation Plan](implementation_plan.md)
