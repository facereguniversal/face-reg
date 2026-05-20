#!/usr/bin/env bash
# Validate deploy/.env.production before production compose up.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${DEPLOY_DIR}/.env.production}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "error: ${ENV_FILE} not found (copy .env.production.example first)" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${ENV_FILE}"
set +a

errors=0
warn() { echo "warn: $*" >&2; }
fail() { echo "error: $*" >&2; errors=$((errors + 1)); }

placeholder() {
  local value="$1"
  [[ "${value}" == replace-* ]] || [[ "${value}" == *replace-with* ]] || [[ "${value}" == CHANGE_ME* ]]
}

require_nonempty() {
  local name="$1"
  local value="${!name:-}"
  if [[ -z "${value}" ]]; then
    fail "${name} is required"
  elif placeholder "${value}"; then
    fail "${name} still uses a placeholder value"
  fi
}

require_nonempty SECRET_KEY
require_nonempty POSTGRES_PASSWORD
require_nonempty DATABASE_URL
require_nonempty CHECKIN_DEVICE_TOKENS
require_nonempty CORS_ORIGINS
require_nonempty GRAFANA_ADMIN_PASSWORD
require_nonempty DOMAIN

if [[ "${SECRET_KEY}" == "CHANGE_ME_IN_PRODUCTION" ]] || [[ "${SECRET_KEY}" == "local-dev-secret-change-in-prod" ]]; then
  fail "SECRET_KEY must not use a default/dev value"
fi

if [[ "${BOOTSTRAP_ON_STARTUP:-false}" == "true" ]]; then
  fail "BOOTSTRAP_ON_STARTUP must be false in production"
fi

if [[ "${CORS_ORIGINS}" == *"*"* ]]; then
  fail "CORS_ORIGINS must not contain wildcards in production"
fi

if [[ "${DATABASE_URL}" != *"${POSTGRES_PASSWORD}"* ]]; then
  fail "DATABASE_URL password must match POSTGRES_PASSWORD"
fi

if [[ "${ENABLE_DEMO_UI:-false}" == "true" ]]; then
  if [[ "${CORS_ORIGINS}" != https://* ]]; then
    warn "ENABLE_DEMO_UI=true: ensure CORS_ORIGINS includes your https://DOMAIN"
  fi
fi

if [[ "${errors}" -gt 0 ]]; then
  echo "${errors} validation error(s)" >&2
  exit 1
fi

echo "ok: ${ENV_FILE} looks ready for production compose"
