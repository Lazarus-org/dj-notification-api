"""Offline consistency check for PEP 621 metadata and the tox compatibility matrix."""

from __future__ import annotations

import argparse
import configparser
import pathlib
import re
import sys

try:
    import tomllib
except ImportError:  # Python 3.10/3.11
    import tomli as tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED = {
    "py310-django52-drf318",
    "py311-django52-drf318",
    "py312-django52-drf318",
    "py312-django60-drf318",
    "py312-django61-drf318",
    "py313-django52-drf318",
    "py313-django60-drf318",
    "py313-django61-drf318",
    "py314-django52-drf318",
    "py314-django60-drf318",
    "py314-django61-drf318",
}


def check(tag: str | None = None) -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        data = tomllib.load(file)
    project = data["project"]
    assert project["name"] == "dj-notification-api"
    assert project["requires-python"] == ">=3.10"
    assert data["build-system"]["build-backend"] == "hatchling.build"
    assert (ROOT / "django_notification" / "__init__.py").is_file()
    assert "django-filter" in " ".join(project["dependencies"])
    assert "django" in " ".join(project["dependencies"]).lower()
    if tag:
        assert tag == f"v{project['version']}", f"tag {tag} != v{project['version']}"

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ROOT / "tox.ini")
    envs = set(parser["tox"]["env_list"].split())
    assert envs == EXPECTED, f"Unexpected tox environments: {envs ^ EXPECTED}"
    assert parser["testenv"]["runner"] == "uv-venv-runner", "Invalid tox-uv runner"
    assert (ROOT / "uv.lock").is_file(), "Generate the real dependency lock"
    hook_config = (ROOT / ".pre-commit-config.yaml").read_text()
    assert (
        hook_config == (ROOT / ".pre-commit-config-ci.yaml").read_text()
    ), "Local and CI pre-commit safeguards must remain identical"
    required_hooks = {
        "check-toml",
        "check-yaml",
        "trailing-whitespace",
        "end-of-file-fixer",
        "check-added-large-files",
        "check-case-conflict",
        "check-merge-conflict",
        "check-docstring-first",
        "pyproject-fmt",
        "tox-ini-fmt",
        "pyupgrade",
        "isort",
        "black",
        "commitizen",
        "bandit",
        "docformatter",
        "blacken-docs",
        "rstcheck",
        "pytest",
        "pylint",
        "pre-commit-django-migration-lint",
        "ruff",
        "ruff-format",
        "package-metadata",
    }
    configured_hooks = set(re.findall(r"^\s+- id: ([\w-]+)\s*$", hook_config, re.M))
    assert (
        required_hooks <= configured_hooks
    ), f"Missing pre-commit safeguards: {sorted(required_hooks - configured_hooks)}"
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    for env in EXPECTED:
        assert f"env: '{env}'" in ci, f"Missing CI environment: {env}"
    assert "poetry.lock" not in [p.name for p in ROOT.iterdir()]
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "uses: ./.github/workflows/ci.yml" in release
    assert "vars.PYPI_PUBLISH_ENABLED == 'true'" in release
    assert "environment: pypi" in release
    assert "needs: [verify-and-build, test-release]" in release
    print(
        f"Metadata OK: {project['name']} {project['version']} / {len(envs)} tox environments"
    )


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--tag")
    parsed = args.parse_args()
    try:
        check(parsed.tag)
    except (AssertionError, KeyError, OSError, ValueError) as error:
        print(f"Packaging check failed: {error}", file=sys.stderr)
        sys.exit(1)
