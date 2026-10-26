# Contributing to dj-notification-api

Thanks for contributing. Bug reports, focused fixes, tests, and documentation
improvements are welcome. Open an issue for a substantial behavior or API
change before beginning a large implementation.

## Development setup

Use a compatible Python version (3.10–3.14) and install
[`uv`](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/lazarus-org/dj-notification-api.git
cd dj-notification-api
uv sync --locked --all-extras --python 3.13
```

The repository declares its dependencies in `pyproject.toml`. The generated `uv.lock` is version controlled; use `uv sync --locked` for
reproducible environments. Do not reintroduce Poetry or exported pip requirement
files as parallel sources of truth.

## Quality workflow

Run the relevant checks before submitting a pull request:

```bash
uv run ruff check django_notification
uv run black --check django_notification scripts
uv run ruff format --check django_notification/tests docs/conf.py
uv run pytest
uv run pre-commit run --all-files
```

Install both Git hook stages with `uv run pre-commit install`. Commitizen
checks the commit message at `commit-msg`; the other checks run before commit.
The local and CI hook files enforce the same checks, and the metadata check
rejects a missing hook or configuration drift between them.

Hooks include file checks, pyproject/tox formatting, pyupgrade, isort, Black,
docformatter, Python documentation formatting, RST validation, Bandit, Pylint,
the full pytest suite and Django migration lint. Tools run through the locked
uv environment. Black formats production code/scripts; Ruff formats tests and
the Sphinx configuration. Run `uv run python scripts/lint_migrations.py` for
migration lint without creating a separate host Django project.

The default test suite uses `pytest-django` and enforces 100% statement coverage
of package source through `pyproject.toml`. Existing test/migration exclusions
remain unchanged. Cover observable behavior, validation failures and recovery
paths; do not add exclusions to reach the threshold. For an individual
compatibility environment, use tox:

```bash
uv run tox -e py313-django61-drf318
```

Other supported environments are listed in `tox.ini` and the CI workflow.
Migration changes should be accompanied by a fresh-database migration test
and appropriate tests for upgrades from supported released schemas.

Changes to the outbox and delivery workers require extra attention to
transaction boundaries, concurrency, lease expiry, replay/idempotency, and
cross-database behavior. For permission or API changes, test both direct and
group audiences, unauthorized access, user-state isolation, and historical
GET compatibility.

## Coding practices

- Follow existing modules and Django conventions; use explicit dependencies
  and avoid hidden network effects at import time.
- Keep Channels, Redis, and provider libraries optional unless approved as
  a project-wide requirement.
- Use lifecycle services for notification state mutations; direct ORM writes
  do not automatically publish lifecycle events.
- Avoid collecting or logging message bodies, provider credentials, recipient
  contact details, and raw provider errors in delivery histories.
- Prefer bounded database operations and idempotent consumers for all
  at-least-once processing paths.
- Add documentation when changing a setting, endpoint, migration, or
  externally observable behavior.

## Pull requests

1. State the problem and the behavior change.
2. Reference the related issue, if any.
3. Describe tests performed, including Django/Python matrix entries.
4. Note migrations, breaking changes, and security consequences explicitly.
5. Do not publish directly to PyPI from a local development machine. Release
   controls are described in [the development guide](docs/development_toolchain.rst).

Use a focused conventional commit message, for example:

```text
fix(notifications): preserve group recipient visibility
```

Security vulnerabilities should be reported privately using
[SECURITY.md](SECURITY.md), not filed as public exploit reports.

## Contributor resources

- [Django documentation](https://docs.djangoproject.com/)
- [Django REST Framework documentation](https://www.django-rest-framework.org/)
- [uv documentation](https://docs.astral.sh/uv/)
- [Project documentation](https://dj-notification-api.readthedocs.io/en/latest/)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

## PostgreSQL validation

Run the full suite against a disposable PostgreSQL database using
`DJANGO_NOTIFICATION_TEST_DATABASE=postgresql` and the standard `PGHOST`,
`PGPORT`, `PGUSER`, `PGPASSWORD`, and `PGDATABASE` environment variables.
The database account must be allowed to create the prefixed test database.
The PostgreSQL job in CI provides a disposable PostgreSQL 17 service.
Read `VALIDATION_REPORT.md` and `RELEASE_READINESS.md` before preparing a release.
