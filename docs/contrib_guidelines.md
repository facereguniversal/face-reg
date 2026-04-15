# Contributing Guidelines

## Code Style

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/). Use `black` for formatting and `flake8` for linting.
- **Commit messages**: Use [Conventional Commits](https://www.conventionalcommits.org/) format, e.g.:
  - `feat: add batch identification endpoint`
  - `fix: handle empty image uploads gracefully`
  - `docs: update API reference for /verify endpoint`
- **Branch naming**: `feature/<name>`, `fix/<name>`, `chore/<name>`

## Pull Request Process

1. Fork and create a feature branch from `main`.
2. Write or update tests for your changes.
3. Run `black .` and `flake8 .` before pushing.
4. Submit a PR with a clear description of the change and why it's needed.
5. PRs require at least 1 approving review before merge.
6. CI must pass (tests, linting, Docker build).

## Dev Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt
pre-commit install
```

## Testing

```bash
pytest tests/ -v
```

## Architecture Decisions

See [architecture.md](architecture.md) for system design rationale.
