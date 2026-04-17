# Face Recognition Web Service

A **universal face-recognition web service** providing REST APIs for face registration, recognition, and management. Built with a microservices architecture using **FastAPI**, **InsightFace/ArcFace embeddings**, **FAISS** vector indexing, and **PostgreSQL** for metadata storage.

## MVP Features

- ✅ Face enrollment (register 4–6 images per user)
  - *Note: Only embeddings are stored in this MVP phase; raw images are not persisted.*
- ✅ Face identification (1:N search against all registered faces)
- ✅ Face verification (1:1 match against a specific user)
- ✅ JWT authentication & role-based access control
- ✅ Audit logging for compliance (Source IP tracked)
- ✅ Docker Compose-based local development
- 🔲 Kubernetes manifests for production (Planned)
- ✅ Degraded-mode support for missing ML dependencies

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

## Full Guide: Running Face-Reg

This project supports two running strategies: **Docker Compose** (recommended for simplicity) and **Local Native Execution** (recommended for active development).

### Prerequisites
- Python 3.10+
- Docker & Docker Compose
- *Wait, you don't actually need an external face-auth camera—your laptop webcam works fine!*

### Method 1: The One-Click Docker Compose Build (Recommended)

The easiest way to stand up the entire architecture (Postgres DB, API, Model Server).

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd face-reg
   cp .env.example .env
   # Ensure you provide a secure SECRET_KEY in the .env file!
   ```

2. **Boot the stack**
   ```bash
   cd deploy
   docker-compose up --build
   ```
   This command provisions:
   - `api`: FastAPI reverse-gateway on `http://localhost:8000`
   - `model_server`: The InsightFace vector extractor on `http://localhost:8001`
   - `db`: PostgreSQL metadata storage on port `5432`

3. **Verify Health**
   Navigate to [http://localhost:8000/api/health](http://localhost:8000/api/health). You should see all services reporting "ok":
   ```json
   {
       "status": "ok",
       "database": "ok",
       "model_server": "ok",
       "model_mode": "fallback"
   }
   ```

### Method 2: Local Native Execution (For Development)

If you are directly developing scripts and don't want to wait for Docker to rebuild every time, run the services natively.

1. **Start the database locally**
   You can either run Postgres manually or just spawn the DB container:
   ```bash
   cd deploy
   docker-compose up db -d
   ```
   *Note: Our MVP doesn't use Alembic migrations yet. The database schema in `db/schema.sql` automatically runs when the `postgres` container initializes for the first time.*

2. **Run the Model Server**
   Open a new terminal session.
   ```bash
   cd model_server
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # InsightFace runs natively here. If missing, it uses OpenCV fallbacks!
   python embed.py
   ```
   The model server now routes FAISS connections on port 8001.

3. **Run the API Backend**
   Open a third terminal session.
   ```bash
   cd api
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # IMPORTANT: The script must be run from the repository root!
   cd ..
   PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Accessing the Web Services

With the application running (via Method 1 or Method 2), you can interact directly with:

- **Swagger UI Console**: `http://localhost:8000/docs`
- **ReDoc Schema View**: `http://localhost:8000/redoc`

#### The Face Capture UI (Enrollment Demo)

To showcase the actual browser capture process without building heavy frontends:
1. Open up the Vanilla JS capture UI locally:
   - Open `/ingestion/capture_ui/index.html` in your browser (no server needed, just `file:///.../index.html`).
2. Pass an authorized user parameter to the URL to simulate an active session:
   - `index.html?userId=00000000-0000-0000-0000-000000000000&token=your-jwt-token`
3. Hit **Capture** to take 4 to 6 photos, validate quality against the local backend endpoint, and **Complete Enrollment**.

### Automated Tests

We use `aiosqlite` connected to an in-memory test DB, meaning tests run quickly without relying on external databases.

```bash
pip install -r api/requirements.txt
PYTHONPATH=. pytest tests/ -v
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
