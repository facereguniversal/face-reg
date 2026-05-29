.PHONY: help local-up-compose local-down-compose local-up-k8s local-down-k8s local-seed local-demo-flow

help:
	@echo "========================================================================="
	@echo "            FACE-REG DUAL-TARGET DEVOPS CONTROL DASHBOARD"
	@echo "========================================================================="
	@echo " DOCKER COMPOSE TARGETS:"
	@echo "   make local-up-compose    - Bootstraps Compose production-replica stack"
	@echo "   make local-down-compose  - Cleans up all Compose resources & volumes"
	@echo ""
	@echo " KUBERNETES (KIND) TARGETS:"
	@echo "   make local-up-k8s        - Provisions Kind cluster, builds/loads local"
	@echo "                              containers, deploys K8s manifests & metrics"
	@echo "   make local-down-k8s      - Destroys local Kind cluster"
	@echo ""
	@echo " DEMO & SEEDING UTILITIES:"
	@echo "   make local-seed          - Runs interactive biometric enrollment script"
	@echo "   make local-demo-flow     - Runs end-to-end enrollment and check-in demo"
	@echo "========================================================================="

# ---------------------------------------------------------------------------
# Docker Compose Orchestration
# ---------------------------------------------------------------------------
local-up-compose:
	@echo "✨ Validating demo environment variables..."
	@./deploy/scripts/validate-env.sh ./deploy/.env.demo
	@echo "🚀 Launching Docker Compose production-replica stack..."
	docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --env-file deploy/.env.demo up -d --build
	@echo "⏳ Waiting for API health gateway to stabilize..."
	@until curl -s http://localhost:8000/api/health | grep -q "ok"; do sleep 1; done
	@echo "🔒 Seeding database admin account..."
	docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --env-file deploy/.env.demo exec -T api python -m api.seed_admin
	@echo "✅ Docker Compose Stack is fully active!"
	@echo "👉 API Endpoint: http://localhost:8000"
	@echo "👉 Grafana:      http://localhost:3000 (admin/admin)"

local-down-compose:
	@echo "🧹 Tearing down Docker Compose Stack..."
	docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.prod.yml --env-file deploy/.env.demo down -v

# ---------------------------------------------------------------------------
# Local Kubernetes (Kind) Orchestration
# ---------------------------------------------------------------------------
local-up-k8s:
	@echo "✨ Bootstrapping local Kubernetes cluster via Kind..."
	@if ! kind get clusters | grep -q "face-reg-cluster"; then \
		kind create cluster --name face-reg-cluster --config deploy/k8s/kind-config.yaml; \
	else \
		echo "Kind cluster already exists."; \
	fi
	@echo "🐳 Building local container images..."
	docker build -t face-reg-api:latest -f deploy/Dockerfile.api .
	docker build -t face-reg-model:latest -f deploy/Dockerfile.model .
	@echo "📦 Loading images into Kind nodes..."
	kind load docker-image face-reg-api:latest --name face-reg-cluster
	kind load docker-image face-reg-model:latest --name face-reg-cluster
	@echo "🕸️ Deploying core Kubernetes manifests..."
	kubectl apply -f deploy/k8s/namespace.yaml
	kubectl apply -f deploy/k8s/volumes.yaml
	kubectl apply -f deploy/k8s/secrets.yaml
	kubectl apply -f deploy/k8s/config.yaml
	kubectl apply -f deploy/k8s/db.yaml
	kubectl apply -f deploy/k8s/redis.yaml
	kubectl apply -f deploy/k8s/model-server.yaml
	kubectl apply -f deploy/k8s/api.yaml
	kubectl apply -f deploy/k8s/ingress.yaml
	kubectl apply -f deploy/k8s/monitoring.yaml
	@echo "⏳ Waiting for API Deployment rollout..."
	kubectl rollout status deployment/api -n face-reg --timeout=120s
	@echo "⏳ Waiting for API health gateway to stabilize..."
	@until curl -s http://localhost:8000/api/health | grep -q "ok"; do sleep 1; done
	@echo "🔒 Seeding database admin account..."
	kubectl exec -i deploy/api -n face-reg -- python -m api.seed_admin
	@echo "✅ Kubernetes local cluster is fully active!"
	@echo "👉 API Endpoint: http://localhost:8000"
	@echo "👉 Grafana:      http://localhost:3000 (admin/admin)"

local-down-k8s:
	@echo "🧹 Deleting local Kind cluster..."
	kind delete cluster --name face-reg-cluster

# ---------------------------------------------------------------------------
# Seeding and Telemetry Utilities
# ---------------------------------------------------------------------------
local-seed:
	@echo "🌱 Running custom seeding CLI..."
	@.venv/bin/python deploy/scripts/demo-cli.py

local-demo-flow:
	@echo "🎬 Executing live biometric enrollment & check-in flow..."
	@.venv/bin/python deploy/scripts/demo-cli.py
