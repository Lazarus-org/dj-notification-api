Development, compatibility and releases
=======================================

Contributors use uv for reproducible development environments, tox for the
compatibility matrix, Ruff for lint and formatting, and pre-commit for shared
hooks. PEP 621 metadata and Hatchling produce standard pip-installable wheels.

.. list-table:: Declared compatibility
   :header-rows: 1

   * - Python
     - Django
     - Django REST Framework
   * - 3.10, 3.11
     - 5.2
     - 3.18
   * - 3.12, 3.13, 3.14
     - 5.2, 6.0, 6.1
     - 3.18

The current source no longer declares support for Python 3.9 or Django
4.2/5.0/5.1. Review the installed release's metadata before upgrading; this
change to minimum versions must be called out in the release notes.

The ``django-filter`` library is a required runtime dependency. Optional
installation extras are ``[channels]`` and ``[redis]``. Those extras enable
WebSocket dependencies but **do not** automatically register event adapters,
configure ASGI routing, or launch worker processes.

Local environment
-----------------

From the repository root::

    uv sync --locked --all-extras --python 3.13
    uv run ruff check django_notification
    uv run black --check django_notification scripts
    uv run ruff format --check django_notification/tests docs/conf.py
    uv run pre-commit install
    uv run pre-commit run --all-files
    uv run pytest

The hook configuration installs both pre-commit checks and Commitizen's
commit-message check. Local and CI configurations enforce the same hook set.
They include file checks, pyproject/tox formatters, pyupgrade, isort, Black,
docformatter, blacken-docs, rstcheck, Bandit, Pylint, pytest and migration lint.
Each restored tool runs from the project's locked uv environment.

Black formats production code/scripts, while Ruff formats tests and the Sphinx
configuration. This gives each file one formatter. Migration lint runs through
``uv run python scripts/lint_migrations.py`` using committed Django settings;
it does not depend on a local manage.py or ignored host project.

A representative tox environment is::

    uv run tox -e py313-django61-drf318

The declared matrix includes 11 Python/Django/DRF combinations. The
``tox.ini`` file and ``.github/workflows/ci.yml`` are the authoritative
configuration for individual environments.

The test suite enforces **100% statement coverage** of package source in every
matrix environment. Tests and migrations retain their existing coverage
exclusions; this is not a branch-coverage claim. Add behavioral regression
tests for new code, including validation and recovery paths. Provider failures
are simulated at adapter boundaries, while PostgreSQL tests verify actual
row locking and concurrent claims.

Inspect the exact measurement with::

    uv run coverage report --show-missing
    uv run coverage json -o coverage.json

Locking
-------

The generated ``uv.lock`` is committed alongside ``pyproject.toml``.
Use ``uv sync --locked`` for reproducible development installs and run
``uv lock`` when intentionally updating dependencies. Generate the lockfile
with uv rather than editing resolved records by hand. Framework combinations
in the tox matrix are resolved separately so branch-specific Django version
requirements remain effective.

Continuous integration
----------------------

CI runs the compatibility matrix alongside lint, formatting, type checking,
security scanning, documentation builds and packaging checks. PostgreSQL
tests exercise row locking and concurrent claims separately from SQLite.
Use the same commands locally when changing a related area.

Build the documentation with warnings treated as errors::

    uv run sphinx-build -W --keep-going -b html docs docs/_build/html

For documentation changes, check examples against the package API and keep
internal implementation/release notes outside the public Sphinx source tree.

Reproducing installed-package checks
-------------------------------------------

``scripts/verify_installation.py`` runs outside the source tree with a clean
wheel installation. It verifies optional-dependency absence, safe REST reads,
fresh migrations, two database aliases, and swapped users with and without
group support. Run it with ``--require-core-only``; add ``--user-model CustomUser``
or ``--user-model BareUser`` for the disposable host application.

For PostgreSQL, set ``DJANGO_NOTIFICATION_TEST_DATABASE=postgresql`` and the
standard ``PGHOST``, ``PGPORT``, ``PGUSER``, ``PGPASSWORD`` and ``PGDATABASE``
variables, then run the complete pytest suite. The account needs permission
to create a test database. SQLite deliberately skips real row-lock races.
