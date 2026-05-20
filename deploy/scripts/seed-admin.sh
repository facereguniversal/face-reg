#!/usr/bin/env bash
# Create the first admin user when BOOTSTRAP_ON_STARTUP=false (production default).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${DEPLOY_DIR}/.env.production"

ADMIN_NAME="${ADMIN_NAME:-Site Admin}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

if [[ -z "${ADMIN_PASSWORD}" ]]; then
  read -r -s -p "Admin password: " ADMIN_PASSWORD
  echo
fi

cd "${DEPLOY_DIR}"

docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file "${ENV_FILE}" exec -T api \
  python -c "
import asyncio
from api.bootstrap import _seed_user

async def main():
    await _seed_user({
        'name': '''${ADMIN_NAME}''',
        'email': '''${ADMIN_EMAIL}''',
        'password': '''${ADMIN_PASSWORD}''',
        'role': 'admin',
        'metadata': {'seeded': True},
    })

asyncio.run(main())
print('Admin ready:', '''${ADMIN_EMAIL}''')
"
