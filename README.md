# Face Recognition Web Service

A **universal face-recognition web service** providing production-grade REST APIs for face enrollment, identification, and verification. Built with a **microservices architecture** using **FastAPI**, **InsightFace/ArcFace embeddings**, **FAISS** vector indexing, and **PostgreSQL** for metadata storage.

> **Status**: MVP-ready with Docker Compose and Kubernetes deployment options. Production-grade security, audit logging, and scalability.

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Face Enrollment** | Register 4–6 images per user with quality validation |
| **Face Identification** | 1:N search against all registered faces |
| **Face Verification** | 1:1 match verification against a specific user |
| **JWT Authentication** | OAuth2-compatible token-based auth with refresh tokens |
| **Role-Based Access Control** | Admin and user roles with endpoint-level permissions |
| **Audit Logging** | Compliance-grade append-only logs with IP tracking |
| **Multi-Deployment** | Docker Compose (dev), Kubernetes (prod), local dev mode |
| **Scalable ML Pipeline** | Async processing with quality checks and degraded-mode fallback |
| **RESTful API** | OpenAPI/Swagger documentation auto-generated |

---

## 📊 Project Structure Breakdown

```
face-reg/
├── api/                          # FastAPI Application
│   ├── main.py                   # Entry point, middleware setup
│   ├── requirements.txt           # Python dependencies
│   ├── auth/
│   │   └── jwt_handler.py         # JWT token generation & validation
│   ├── models/
│   │   ├── db_models.py           # SQLAlchemy ORM models
│   │   └── schemas.py             # Pydantic request/response schemas
│   ├── routes/
│   │   ├── auth.py                # POST /api/auth/login, /refresh
│   │   ├── users.py               # CRUD for user management
│   │   ├── faces.py               # Face enrollment & validation
│   │   └── identify.py            # Identification & verification endpoints
│   └── services/
│       ├── database.py            # SQLAlchemy session & ORM utilities
│       ├── dependencies.py        # FastAPI dependency injection
│       ├── audit_service.py       # Audit log recording
│       ├── user_service.py        # User business logic
│       └── face_service.py        # Face enrollment, ID, verify logic
│
├── model_server/                 # ML Inference Service (separate container)
│   ├── detect.py                 # Face detection (MTCNN/RetinaFace)
│   ├── embed.py                  # Embedding extraction (ArcFace)
│   └── requirements.txt           # ML dependencies (torch, insightface, etc.)
│
├── ingestion/                    # Data ingestion & preprocessing
│   ├── pipeline/
│   │   └── preprocessor.py       # Image quality checks, normalization
│   ├── capture_ui/               # Web UI for face capture
│   │   ├── index.html
│   │   ├── app.js
│   │   └── style.css
│   └── checkin_ui/               # Web UI for check-in/verification
│       ├── index.html
│       ├── app.js
│       └── style.css
│
├── deploy/                       # Deployment configurations
│   ├── docker-compose.yml        # Local/dev deployment (all services)
│   ├── Dockerfile.api            # API service container image
│   ├── Dockerfile.model          # Model server container image
│   └── k8s/                      # Kubernetes manifests (production)
│       ├── namespace.yaml        # Isolated k8s namespace
│       ├── secrets.yaml          # DB credentials, JWT secret
│       ├── config.yaml           # ConfigMap for env variables
│       ├── db.yaml               # PostgreSQL StatefulSet
│       ├── api.yaml              # API Deployment & Service
│       ├── model-server.yaml     # Model server Deployment
│       └── volumes.yaml          # PersistentVolume claims
│
├── db/                           # Database setup
│   ├── schema.sql                # PostgreSQL schema (users, faces, audit)
│   └── migrations/               # Database migration scripts
│
├── ci/
│   └── workflows/
│       └── ci.yml                # GitHub Actions CI pipeline
│
├── docs/                         # Documentation
│   ├── architecture.md           # System design & component diagrams
│   ├── api_reference.md          # API endpoint documentation
│   └── contrib_guidelines.md     # Contributing guidelines
│
├── tests/                        # Test suite
│   ├── api_tests.py              # FastAPI endpoint tests
│   ├── audit_tests.py            # Audit logging tests
│   ├── model_tests.py            # ML service tests
│   └── conftest.py               # Pytest fixtures & setup
│
├── GUIDELINE.md                  # Product requirements & philosophy
├── implementation_plan.md        # Feature roadmap
├── LICENSE                       # MIT License
└── README.md                     # This file
```

---

## 🏗️ Architecture Overview

### High-Level Flow

```
┌──────────────────────────────────────────┐
│     Client (Web UI / Mobile SDK)         │
└────────────────┬─────────────────────────┘
                 │ HTTPS REST
                 ↓
         ┌──────────────────┐
         │  API Gateway     │
         │  (FastAPI)       │
         └────┬────┬────┬───┘
              │    │    │
    ┌─────────┘    │    └──────────┐
    ↓              ↓               ↓
┌────────┐  ┌───────────┐  ┌────────────┐
│  Auth  │  │ Enrollment│  │Identify &  │
│Service │  │ Service   │  │ Verify     │
└────┬───┘  └─────┬─────┘  └────┬───────┘
     │            │             │
     └────────────┼─────────────┘
                  ↓
         ┌────────────────────┐
         │   ML Layer         │
         │ (Model Server)     │
         │ - Detection        │
         │ - Alignment        │
         │ - Embedding        │
         └────────┬───────────┘
                  ↓
    ┌─────────────────────────────┐
    │   Data Storage              │
    ├─────────────────────────────┤
    │ • PostgreSQL (Users/Audit)  │
    │ • FAISS Index (Embeddings)  │
    │ • File/S3 Storage (Images)  │
    └─────────────────────────────┘
```

### Component Responsibilities

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API Gateway** | FastAPI | Central entry point, validation, routing |
| **Auth Service** | PyJWT | Token generation, user authentication |
| **User Service** | SQLAlchemy | User CRUD operations |
| **Face Service** | Python, requests | Enrollment, ID, verification logic |
| **Model Server** | InsightFace, FAISS | Face detection & embedding extraction |
| **Database** | PostgreSQL | Users, audit logs, metadata |
| **Vector Index** | FAISS | Fast approximate nearest neighbor search |

### Data Flow: Face Enrollment

```
1. User uploads 4-6 face images
        ↓
2. Preprocessing: quality validation, normalization (preprocessor.py)
        ↓
3. Face Detection: find faces in images (MTCNN)
        ↓
4. Embedding Extraction: convert faces to 512-d vectors (ArcFace)
        ↓
5. FAISS Indexing: add embeddings to searchable index
        ↓
6. Audit Log: record enrollment action
        ↓
7. Success response to client
```

---

## 🚀 Deployment Guide

### Quick Start: Docker Compose (Local Development)

**Prerequisites:**
- Docker & Docker Compose installed
- 2+ GB RAM available
- Port 8000, 8001, 5432 available

**Steps:**

```bash
cd deploy
docker-compose up --build
```

**Services available:**
- API: `http://localhost:8000` (Swagger UI: `/docs`)
- Model Server: `http://localhost:8001`
- PostgreSQL: `localhost:5432` (user: `faceuser`, pass: `facepass`, db: `facedb`)

**Verify deployment:**

```bash
# Check API health
curl http://localhost:8000/health

# View Swagger documentation
open http://localhost:8000/docs

# Test login endpoint
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

**Stop services:**

```bash
docker-compose down          # Stop containers
docker-compose down -v       # Stop and remove volumes (reset DB)
```

---

### Production: Kubernetes Deployment

**Prerequisites:**
- Kubernetes cluster (v1.24+)
- `kubectl` configured
- Persistent storage provisioner (local-path or cloud provider)

**Steps:**

1. **Create namespace & secrets:**

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml         # Edit with your values first!
kubectl apply -f k8s/config.yaml
```

2. **Deploy infrastructure:**

```bash
kubectl apply -f k8s/volumes.yaml
kubectl apply -f k8s/db.yaml              # Wait for PostgreSQL to be ready
sleep 30
kubectl apply -f k8s/db-schema.yaml       # Initialize schema
```

3. **Deploy services:**

```bash
kubectl apply -f k8s/model-server.yaml
kubectl apply -f k8s/api.yaml
```

4. **Verify deployment:**

```bash
kubectl get pods -n face-reg               # Check pod status
kubectl get svc -n face-reg                # Check services
kubectl logs -n face-reg deployment/api -f # Tail API logs
```

5. **Access the API:**

```bash
# Port-forward for local testing
kubectl port-forward -n face-reg svc/api 8000:8000

# Or configure ingress (production)
# See k8s/ingress.yaml for example
```

6. **Destroy deployment:**

```bash
kubectl delete namespace face-reg
```

---

### Local Development: Without Docker

**Prerequisites:**
- Python 3.11+
- PostgreSQL 14+
- PyTorch + CUDA (optional, for GPU acceleration)

**Setup:**

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# or venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r api/requirements.txt
pip install -r model_server/requirements.txt

# 3. Set up PostgreSQL
createdb facedb
psql facedb < db/schema.sql

# 4. Set environment variables
export DATABASE_URL="postgresql://localhost/facedb"
export SECRET_KEY="your-secret-key-here"
export MODEL_SERVER_URL="http://localhost:8001"

# 5. Start model server (Terminal 1)
cd model_server
python -m uvicorn embed:app --host 0.0.0.0 --port 8001

# 6. Start API (Terminal 2)
cd api
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ⚙️ Configuration

All configuration is managed via **environment variables**:

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://localhost/facedb` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT signing key | *(required)* | `your-super-secret-key-min-32-chars` |
| `MODEL_SERVER_URL` | Model inference service URL | `http://localhost:8001` | `http://model-server:8001` |
| `STORAGE_BACKEND` | Image storage type | `local` | `s3` for AWS S3 |
| `FAISS_INDEX_PATH` | Path to FAISS index file | `./data/faiss.index` | `/var/lib/face-reg/faiss.index` |
| `CORS_ORIGINS` | Allowed CORS origins | `["http://localhost:3000"]` | JSON array as string |
| `JWT_EXPIRY_MINUTES` | Token expiration time | `30` | `60` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG` or `WARNING` |
| `BATCH_SIZE` | Enrollment batch size | `32` | `16` or `64` |
| `SIMILARITY_THRESHOLD` | Face match threshold (0-1) | `0.6` | `0.5` or `0.7` |

**Environment file example (`.env`):**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://faceuser:facepass@db:5432/facedb

# Security
SECRET_KEY=your-32-character-minimum-secret-key-1234567890ab

# Services
MODEL_SERVER_URL=http://model_server:8001

# Storage
STORAGE_BACKEND=local
FAISS_INDEX_PATH=/data/faiss.index

# API
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
JWT_EXPIRY_MINUTES=60
LOG_LEVEL=INFO
```

---

## 📡 API Quick Reference

### Authentication

```bash
# Login (get token)
POST /api/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800
}

# Use token in subsequent requests
Authorization: Bearer {access_token}
```

### User Management

```bash
# Create user
POST /api/users
Authorization: Bearer {token}

{
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe"
}

# List users
GET /api/users
Authorization: Bearer {token}

# Get user by ID
GET /api/users/{user_id}
Authorization: Bearer {token}

# Update user
PUT /api/users/{user_id}
Authorization: Bearer {token}

# Delete user
DELETE /api/users/{user_id}
Authorization: Bearer {token}
```

### Face Operations

```bash
# Enroll faces (4-6 images per user)
POST /api/users/{user_id}/faces
Authorization: Bearer {token}
Content-Type: multipart/form-data

[Form fields: image1, image2, image3, image4, image5, image6]

# Validate face quality (before enrollment)
POST /api/faces/validate
Authorization: Bearer {token}
Content-Type: multipart/form-data

[Form field: image]

Response:
{
  "quality_score": 0.92,
  "is_valid": true,
  "message": "Face quality is excellent"
}

# Identify face (1:N search)
POST /api/identify
Authorization: Bearer {token}
Content-Type: multipart/form-data

[Form field: image]

Response:
{
  "matches": [
    {
      "user_id": "uuid-1",
      "username": "john_doe",
      "similarity": 0.95
    },
    {
      "user_id": "uuid-2",
      "username": "jane_doe",
      "similarity": 0.88
    }
  ]
}

# Verify face (1:1 match)
POST /api/verify
Authorization: Bearer {token}
Content-Type: application/json

{
  "user_id": "uuid-1",
  "image": "base64-encoded-image"
}

Response:
{
  "user_id": "uuid-1",
  "is_match": true,
  "similarity": 0.94,
  "confidence": "high"
}
```

### Audit Logs

```bash
# Get audit logs (admin only)
GET /api/audit/logs?limit=100&user_id={user_id}
Authorization: Bearer {admin_token}

Response:
{
  "logs": [
    {
      "id": "log-uuid",
      "user_id": "user-uuid",
      "action": "FACE_ENROLL",
      "details": "Enrolled 6 face images",
      "source_ip": "192.168.1.100",
      "timestamp": "2024-01-15T10:30:45Z"
    }
  ]
}
```

**Full API docs:** See [docs/api_reference.md](docs/api_reference.md) or visit `/docs` endpoint.

---

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/api_tests.py -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html
```

### Key Test Suites

- `api_tests.py` — FastAPI endpoint tests
- `audit_tests.py` — Audit logging functionality
- `model_tests.py` — ML service tests

---

## 🛠️ Development Workflow

### 1. Local Setup

```bash
cd face-reg
python -m venv venv
source venv/bin/activate
pip install -r api/requirements.txt
```

### 2. Run Services

```bash
# Terminal 1: PostgreSQL
docker run --rm -p 5432:5432 \
  -e POSTGRES_USER=faceuser \
  -e POSTGRES_PASSWORD=facepass \
  -e POSTGRES_DB=facedb \
  postgres:16-alpine

# Terminal 2: Model Server
cd model_server
uvicorn embed:app --reload --port 8001

# Terminal 3: API
cd api
uvicorn main:app --reload --port 8000
```

### 3. Make Changes

- Edit source files
- Tests run automatically with `--reload`
- API auto-refreshes at `http://localhost:8000/docs`

### 4. Create PR

```bash
git checkout -b feature/my-feature
git commit -am "Add feature"
git push origin feature/my-feature
```

See [docs/contrib_guidelines.md](docs/contrib_guidelines.md) for full contribution guidelines.

---

## 📋 Requirements

### System

- **CPU**: 2+ cores recommended
- **RAM**: 4 GB minimum (8 GB for comfortable development)
- **Disk**: 10 GB minimum (for models + data)
- **GPU**: Optional (NVIDIA CUDA 11.8+ for acceleration)

### Software

**Runtime:**
- Docker 20.10+
- Docker Compose 2.0+
- OR Python 3.11+

**Development:**
- Python 3.11+
- PostgreSQL 14+
- Git 2.30+

**Optional:**
- Kubernetes 1.24+ (for K8s deployment)
- NVIDIA Docker Runtime (for GPU support)

---

## 🐛 Troubleshooting

### Docker Compose Issues

**Issue**: `Cannot connect to database`
```bash
# Solution: Wait for DB to be healthy
docker-compose logs db
docker-compose restart api
```

**Issue**: `Model server connection refused`
```bash
# Solution: Ensure model server is running
docker-compose logs model_server
docker-compose restart model_server
```

**Issue**: Port already in use
```bash
# Solution: Change ports in docker-compose.yml or use different host port
docker-compose down
lsof -i :8000   # Find what's using port 8000
```

### Kubernetes Issues

**Issue**: `Pods stuck in Pending`
```bash
kubectl describe pod -n face-reg <pod-name>
kubectl get pvc -n face-reg   # Check volume claims
```

**Issue**: `ImagePullBackOff`
```bash
# Solution: Check image registry and credentials
kubectl get events -n face-reg
docker pull your-registry/api:latest
```

### API Issues

**Issue**: `401 Unauthorized`
```bash
# Solution: Ensure token is set correctly
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/users
```

**Issue**: `Face detection failed`
```bash
# Solution: Check model server logs
docker-compose logs model_server
# Ensure model files are present
ls -la /path/to/models/
```

---

## 📚 Documentation

- **[Architecture](docs/architecture.md)** — System design, component diagrams, data flow
- **[API Reference](docs/api_reference.md)** — Complete endpoint documentation
- **[Contributing Guidelines](docs/contrib_guidelines.md)** — Development standards and workflow
- **[Implementation Plan](implementation_plan.md)** — Feature roadmap and development phases

---

## 🔒 Security

- **Authentication**: JWT-based OAuth2 flow with refresh tokens
- **Authorization**: Role-based access control (RBAC)
- **Encryption**: HTTPS/TLS in transit, encrypted passwords at rest
- **Audit Logging**: Append-only audit trail with IP tracking
- **Input Validation**: Pydantic schemas + rate limiting
- **Secrets Management**: Environment variables for sensitive data

**Important**: In production, use:
- Strong `SECRET_KEY` (minimum 32 characters, cryptographically random)
- Managed PostgreSQL (e.g., AWS RDS, Azure Database)
- HTTPS with valid SSL certificate
- Network isolation (VPC, firewalls)

See [GUIDELINE.md](GUIDELINE.md) for security compliance details.

---

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

We welcome contributions! Please read [docs/contrib_guidelines.md](docs/contrib_guidelines.md) for:
- Code style standards
- Testing requirements
- Commit message conventions
- Pull request process

---

## 📞 Support

For issues, questions, or suggestions:
1. Check [Troubleshooting](#-troubleshooting) section
2. Review [Documentation](docs/)
3. Open an issue on GitHub
4. Check existing issues for similar problems

---

**Last Updated**: April 2026 | **Version**: 1.0.0-MVP
