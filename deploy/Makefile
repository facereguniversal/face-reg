.PHONY: validate-env config-prod up-prod bootstrap

ENV_FILE ?= .env.production

validate-env:
	./scripts/validate-env.sh $(ENV_FILE)

config-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file $(ENV_FILE) config

bootstrap:
	./scripts/bootstrap-production.sh

up-prod: validate-env
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file $(ENV_FILE) up -d --build
