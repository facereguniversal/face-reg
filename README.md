# Face Recognition Web Service

A **universal face-recognition web service** providing REST APIs for face registration, recognition, and management. Built with a microservices architecture using **FastAPI**, **InsightFace/ArcFace embeddings**, **FAISS** vector indexing, and **PostgreSQL** for metadata storage.

## Features

- ✅ Face enrollment (register 4–6 images per user)
- ✅ Face identification (1:N search against all registered faces)
- ✅ Face verification (1:1 match against a specific user)
- ✅ JWT authentication & role-based access control
- ✅ Audit logging for compliance (GDPR-aware)
- ✅ Docker Compose-based local development
- ✅ Kubernetes manifests for production

## Architecture

```
Client (Web UI / SDKs)
        ↓
  API Gateway (FastAPI)
     ↙        ↘
Auth Service  Ingestion / Identify Services
                    ↓
         ML Pipeline (MTCNN → ArcFace)
                    ↓
       FAISS Index + PostgreSQL + File Store
```

See [docs/architecture.md](docs/architecture.md) for diagrams and full details.

## Repository Structure

```
face-reg/
├── api/                  # FastAPI backend service
│   ├── main.py           # App entrypoint
│   ├── requirements.txt
│   ├── routes/           # Route handlers
│   ├── models/           # Pydantic schemas & DB models
│   ├── services/         # Business logic
│   └── auth/             # JWT helpers
├── model_server/         # ML inference service
│   ├── detect.py         # Face detection & alignment
│   ├── embed.py          # Embedding extraction (ArcFace)
│   └── requirements.txt
├── ingestion/
│   ├── capture_ui/       # Web UI for face capture
│   └── pipeline/         # Preprocessing scripts
├── db/
│   ├── schema.sql        # PostgreSQL schema
│   └── migrations/       # Alembic migration scripts
├── tests/                # Unit & integration tests
├── deploy/
│   ├── docker-compose.yml
│   └── k8s/              # Kubernetes manifests
├── ci/
│   └── workflows/        # GitHub Actions CI/CD
└── docs/                 # Architecture & API docs
```

## Quick Start

### Requirements

- Python 3.10+
- Docker & Docker Compose
- (Optional) NVIDIA GPU with CUDA 11+ for faster inference

### 1. Clone and configure

```bash
git clone <repo-url>
cd face-reg
cp .env.example .env
# Edit .env with your DB credentials and secret keys
```

### 2. Run with Docker Compose

```bash
cd deploy
docker-compose up --build
```

This starts:
- `api` – FastAPI server on `http://localhost:8000`
- `db` – PostgreSQL on port `5432`
- `model_server` – ML inference server on `http://localhost:8001`

### 3. Access the API

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/api/health`

### 4. Run tests

```bash
cd tests
pip install -r ../api/requirements.txt
pytest -v
```

## Configuration

All configuration is done via environment variables (see `.env.example`):

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `SECRET_KEY` | JWT signing secret | *required* |
| `MODEL_SERVER_URL` | URL of model inference service | `http://model_server:8001` |
| `STORAGE_BACKEND` | `local` or `s3` | `local` |
| `FAISS_INDEX_PATH` | Path to FAISS index file | `./data/faiss.index` |

## API Reference

See [docs/api_reference.md](docs/api_reference.md) for full endpoint documentation.

Key endpoints:
- `POST /api/auth/login` — Obtain JWT token
- `POST /api/users` — Create a new user
- `POST /api/users/{id}/faces` — Enroll face images
- `POST /api/identify` — Identify a face
- `POST /api/verify` — Verify a face against a user

## Contributing

See [docs/contrib_guidelines.md](docs/contrib_guidelines.md) for coding standards and PR policies.

## License

See [LICENSE](LICENSE).
