# Kubernetes Deployment Manifests

This directory holds Kubernetes manifests and/or Helm charts for
production deployment.

## Planned Resources

- `api-deployment.yaml` – API service pods + HPA
- `model-server-deployment.yaml` – ML inference pods (GPU node pool)
- `postgres-statefulset.yaml` – Database (or use managed RDS/Cloud SQL)
- `ingress.yaml` – Ingress controller with TLS
- `configmap.yaml` – Environment configuration
- `secrets.yaml` – Sensitive credentials (encrypted via SealedSecrets/SOPS)
