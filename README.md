# Face Recognition Web Service

A production-grade, highly available face recognition and enrollment stack built with **FastAPI**, **InsightFace/ArcFace**, **PostgreSQL (pgvector)**, and **Redis**.

> [!NOTE]
> This service has been fully upgraded for mass production scaling (10,000+ daily users). The architecture is completely stateless: ML inference is separated from indexing, database similarity search is handled natively via `pgvector`, rate-limiting is synchronized across replicas via Redis, and deployments are orchestrated via Highly Available Kubernetes.

---

## Features

- **1:N Face Identification**: Match a probe face against all enrolled templates in under 50ms using optimized PostgreSQL `pgvector` indexing.
- **1:1 Face Verification**: Verify a probe face against a specific user's template to validate identity.
- **Biometric Enrollment**: Upload 3 to 5 images per user to generate and store a high-quality averaged 512-d ArcFace embedding.
- **Distributed Rate Limiting**: Redis-backed rate-limiting ensures consistent, synchronized traffic controls across multiple API gateways and service replicas.
- **Stateless ML Pipeline**: The Model Server acts purely as a stateless embedding generator, allowing seamless horizontal scaling under high concurrent workloads.
- **Live Admin Dashboard & Web Demos**: Real-time websocket-powered hotel kiosk check-in tracking, user capture, and admin interfaces.
- **Production-Grade Monitoring**: Fully integrated Prometheus scraping endpoints and Grafana dashboards tracking system resource utilization and API throughput.
- **Enterprise-Ready Infrastructure**: Kubernetes configurations with Horizontal Pod Autoscalers (HPAs), Pod Anti-Affinity rules, NGINX Ingress Controller, and cert-manager automated TLS.
- **GitHub Actions CI/CD**: Automated linting, unit testing (`pytest`), Docker builds, and zero-downtime rolling updates to your Kubernetes cluster.

---

## System Architecture

```mermaid
graph TD
    Client["Clients / Kiosks"]
    
    subgraph K8S["Kubernetes Cluster (High Availability)"]
        Ingress["NGINX Ingress Controller (cert-manager TLS)"]
        
        subgraph API_GATEWAY["API Layer (FastAPI Replicas)"]
            API_1["api-pod-1"]
            API_2["api-pod-2"]
        end
        
        subgraph INFERENCE["ML Layer (Stateless ArcFace Replicas)"]
            ML_1["model-server-pod-1"]
            ML_2["model-server-pod-2"]
        end
        
        subgraph CACHE["Cache Layer"]
            Redis["Redis (Distributed Rate-Limit Storage)"]
        end
        
        subgraph DB["Storage Layer"]
            Postgres["PostgreSQL + pgvector (MetaDB & Vector Search)"]
            Storage["Shared Persistent Volume (Face Images)"]
        end
    end
    
    Client -->|HTTPS (TLS)| Ingress
    Ingress --> API_1 & API_2
    API_1 & API_2 -->|Distributed Limiting| Redis
    API_1 & API_2 -->|Stateless Embeddings| ML_1 & ML_2
    API_1 & API_2 -->|JSON Metadata & pgvector ANN Search| Postgres
    API_1 & API_2 -->|Image Writes| Storage
```

---

## Project Layout

```text
face-reg/
├── .github/workflows/       # GitHub Actions CI/CD Pipeline
├── api/                     # FastAPI App (JWT Auth, slowapi rate-limiting, services, db, seeds)
├── db/                      # Alembic migrations & Database Schema SQL (pgvector integration)
├── deploy/                  # Dockerfiles, docker-compose configs, and High-Availability Kubernetes manifests
│   ├── docker-compose.yml       # Local Dev Compose Stack
│   ├── docker-compose.prod.yml  # Local Production-Simulated Stack
│   └── k8s/                     # HA K8s manifests (Deployments, Services, HPAs, Redis, NGINX Ingress, TLS)
├── docs/                    # Architectural guidelines, API specs, and deploy runbooks
├── ingestion/               # Kiosk browser demos (Capture, Check-In, Admin Dashboard)
├── model_server/            # Stateless ArcFace/InsightFace embedding generation service
└── tests/                   # Pytest automation suite
```

---

## Configuration

The system is configured via environment variables.

| Variable | Description | Default | Environment |
|----------|-------------|---------|-------------|
| `PORT` | FastAPI server port | `8000` | Local / Container |
| `DATABASE_URL` | PostgreSQL connection string | *Required* | All |
| `REDIS_URL` | Redis distributed caching/rate-limit string | *Required in Prod* | All |
| `MODEL_SERVER_URL` | Endpoint to stateless embedding service | `http://localhost:8001` | All |
| `SECRET_KEY` | HS256 JWT cryptographic signing key | *Required in Prod* | All |
| `ENVIRONMENT` | Deployment environment mode (`development`/`production`) | `development` | All |
| `CORS_ORIGINS` | Allowed origins (no wildcards in production) | `http://localhost:3000` | All |
| `CHECKIN_DEVICE_TOKENS` | Device identification and auth tokens | *Required in Prod* | All |
| `ENABLE_DEMO_UI` | Serve hotel kiosk web interfaces from the API | `true` in dev, `false` in prod | All |

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 14+ with the `pgvector` extension installed
- Redis Server (local or containerized)

### 2. Local Environment Setup
Clone the repository and build the virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
pip install -r model_server/requirements.txt
```

### 3. Database Initialization
Ensure your database has the `pgvector` extension enabled, then apply the base schema:
```bash
createdb facedb
psql facedb -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql facedb < db/schema.sql
```

### 4. Running the Services
In separate terminal sessions, start the stateless embedding generator and the FastAPI API gateway:
```bash
# Start Model Inference Server (Port 8001)
uvicorn model_server.embed:app --host 0.0.0.0 --port 8001 --reload

# Start API Gateway (Port 8000)
export DATABASE_URL="postgresql+asyncpg://faceuser:facepass@localhost:5432/facedb"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="dev-secret-key-change-me"
export CHECKIN_DEVICE_TOKENS="demo-kiosk:demo-token"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Running with Docker Compose (Local Staging)

For a complete local simulation of the production architecture using containerized PostgreSQL, Redis, and multi-replica API gateways:

```bash
# Start the full stack
docker compose -f deploy/docker-compose.yml up --build

# Verify all services are running and healthy
curl http://localhost:8000/api/health
```

---

## Production Deployment (Kubernetes HA)

Our primary production target is Kubernetes (EKS, GKE, or custom clusters) utilizing the high-availability configuration located in `deploy/k8s/`.

For step-by-step production setup, custom configuration parameters, Prometheus metric targets, and disaster recovery procedures, see the comprehensive **[docs/production.md](docs/production.md)** guide.

---

## Documentation

- **[Architecture Specifications](docs/architecture.md)** — Detailed microservices design, Mermaid flows, and scalability patterns.
- **[API Reference](docs/api_reference.md)** — Endpoints, request schemas, authentication parameters, and response payloads.
- **[Production Deploy Runbook](docs/production.md)** — HA Kubernetes deployment, TLS, monitoring, and backups.
- **[Contribution Guidelines](docs/contrib_guidelines.md)** — Code style enforcement, test guidelines, and pull request procedures.

---

## License

MIT
