"""Repository contracts for portable MkDocs hosting."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MKDOCS = ROOT / "mkdocs.yml"
GITLAB_CI = ROOT / ".gitlab-ci.yml"
GITHUB_PAGES = ROOT / ".github" / "workflows" / "docs-pages.yml"
DOCS = ROOT / "docs"


def test_mkdocs_urls_are_host_configurable() -> None:
    text = MKDOCS.read_text(encoding="utf-8")
    required = (
        "site_url: !ENV CALM_SITE_URL",
        "repo_url: !ENV CALM_REPO_URL",
        "repo_name: !ENV CALM_REPO_NAME",
        "edit_uri: !ENV CALM_EDIT_URI",
    )
    missing = [entry for entry in required if entry not in text]
    assert missing == [], f"Missing host-configurable MkDocs settings: {missing}"
    assert "czgitlab.llnl.gov" not in text


def test_active_documentation_has_no_repository_host_lock_in() -> None:
    offenders: list[str] = []
    for path in DOCS.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "czgitlab.llnl.gov" in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], f"Host-locked active documentation: {offenders}"


def test_github_pages_workflow_builds_and_deploys_strict_site() -> None:
    text = GITHUB_PAGES.read_text(encoding="utf-8")
    required = (
        "github.ref_name == github.event.repository.default_branch",
        "actions/configure-pages@v5",
        "steps.pages.outputs.base_url",
        "python -m pip install -e \".[docs]\"",
        "python -m mkdocs build --strict",
        "actions/upload-pages-artifact@v4",
        "actions/deploy-pages@v4",
        "pages: write",
        "id-token: write",
        "path: site",
    )
    missing = [entry for entry in required if entry not in text]
    assert missing == [], f"Incomplete GitHub Pages workflow: {missing}"

    for variable in (
        "CALM_SITE_URL",
        "CALM_REPO_URL",
        "CALM_REPO_NAME",
        "CALM_EDIT_URI",
    ):
        assert f"{variable}:" in text


def test_gitlab_pages_job_supplies_host_metadata_and_public_directory() -> None:
    text = GITLAB_CI.read_text(encoding="utf-8")
    pages_job = re.search(r"(?ms)^pages:\n(?P<body>.*?)(?=^[^ #\n][^\n]*:\n|\Z)", text)
    assert pages_job is not None
    body = pages_job.group("body")

    assert "pages: true" in body
    assert 'test -n "${CI_PAGES_URL:-}"' in body
    assert "CI_PAGES_URL" in body
    assert "$CALM_CI_PYTHON -m mkdocs build --strict --site-dir public" in body
    assert "- public" in body
    assert 'if: \'$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH\'' in body

    for variable in ("CALM_REPO_URL", "CALM_REPO_NAME", "CALM_EDIT_URI"):
        assert f"{variable}:" in text
