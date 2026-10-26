Contributing
============

For local installation instructions, style conventions, pull-request guidance
and supported development commands, see the repository's
`CONTRIBUTING.md <https://github.com/lazarus-org/dj-notification-api/blob/main/CONTRIBUTING.md>`_.

The authoritative tooling configuration lives in ``pyproject.toml`` and
``tox.ini``. In a local source checkout, the typical commands are::

    uv sync --locked --all-extras --python 3.13
    uv run ruff check django_notification
    uv run black --check django_notification scripts
    uv run ruff format --check django_notification/tests docs/conf.py
    uv run pytest
    uv run pre-commit run --all-files

The full supported framework matrix and release workflow are documented in
:doc:`development_toolchain`. Please report vulnerabilities privately through
the repository's ``SECURITY.md`` rather than a public issue.
