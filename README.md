# Face Recognition Web Service

A **universal face-recognition web service** providing REST APIs for face registration, recognition, and management. Built with a microservices architecture using **FastAPI**, **InsightFace/ArcFace embeddings**, **FAISS** vector indexing, and **PostgreSQL** for metadata storage.

## Features

- Face enrollment (register 4–6 images per user)
  - *Note: Only embeddings are stored; raw images are not persisted.*
- Face identification (1:N search against all registered faces)
- Face verification (1:1 match against a specific user)
- JWT authentication & role-based access control
- Audit logging for compliance (Source IP tracked)
- Docker Compose-based deployment
- Kubernetes manifests for production
- Degraded-mode support for missing ML dependencies

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

## Configuration

All configuration is done via environment variables:

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

## License

See [LICENSE](LICENSE).
