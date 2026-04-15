# Database Migrations

This directory holds Alembic migration scripts for evolving the PostgreSQL schema.

## Setup

```bash
cd face-reg
alembic init db/migrations
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

See [Alembic docs](https://alembic.sqlalchemy.org/) for details.
