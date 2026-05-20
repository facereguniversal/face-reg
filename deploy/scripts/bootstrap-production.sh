#!/usr/bin/env bash
# Prepare deploy/.env.production and start the production Compose stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEPLOY_DIR}/.." && pwd)"
ENV_FILE="${DEPLOY_DIR}/.env.production"
EXAMPLE="${DEPLOY_DIR}/.env.production.example"

cd "${DEPLOY_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Creating ${ENV_FILE} from example..."
  cp "${EXAMPLE}" "${ENV_FILE}"
fi

# Generate SECRET_KEY if still a placeholder.
if grep -q '^SECRET_KEY=replace-with-openssl-rand-hex-32' "${ENV_FILE}" 2>/dev/null; then
  if command -v openssl >/dev/null 2>&1; then
    key="$(openssl rand -hex 32)"
    sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=${key}/" "${ENV_FILE}"
    rm -f "${ENV_FILE}.bak"
    echo "Generated SECRET_KEY"
  else
    echo "warn: install openssl to auto-generate SECRET_KEY" >&2
  fi
fi

echo ""
echo "Edit required secrets in ${ENV_FILE}:"
echo "  - POSTGRES_PASSWORD (and matching DATABASE_URL password)"
echo "  - CHECKIN_DEVICE_TOKENS"
echo "  - CORS_ORIGINS (https://your-domain)"
echo "  - GRAFANA_ADMIN_PASSWORD"
echo "  - DOMAIN (DNS must point here for public TLS)"
echo ""
echo "Hotel kiosk demo: set ENABLE_DEMO_UI=true and align CORS_ORIGINS with https://\${DOMAIN}"
echo "First admin (bootstrap disabled in prod): ./scripts/seed-admin.sh after stack is healthy"
echo ""

if ! "${SCRIPT_DIR}/validate-env.sh" "${ENV_FILE}"; then
  echo ""
  echo "Fix the variables above, then re-run: ${SCRIPT_DIR}/bootstrap-production.sh"
  exit 1
fi

compose=(docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file "${ENV_FILE}")

echo "Starting production stack from ${DEPLOY_DIR}..."
"${compose[@]}" up -d --build

echo ""
echo "Stack started. Useful checks:"
echo "  ${compose[*]} ps"
echo "  curl -kfsS \"https://\${DOMAIN:-localhost}/api/health\"   # -k for self-signed (tls internal)"
echo "  ssh -L 3000:127.0.0.1:3000 user@vm   # Grafana at http://127.0.0.1:3000"
echo ""
echo "Create first admin: ${SCRIPT_DIR}/seed-admin.sh"
