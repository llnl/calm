"""Ownership guardrails for exact prototype buildability checks."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from calm.project.application import buildability
from calm.public.collections.candidates import CandidateCollection
from calm.public.persistence.adapter import WorkspaceAdapter

ROOT = Path(__file__).resolve().parents[2]


def test_buildability_uses_current_typed_batch_repositories() -> None:
    source = inspect.getsource(buildability)
    assert "get_many_by_uid_full" in source
    assert "resolve_prototype" in source
    assert "get_by_uid_full" not in source
    assert "hasattr(" not in source
    assert "getattr(" not in source
    assert "except Exception" not in source
    assert "ensure_prototype_id" not in source
    assert "ensure_slab_id" not in source


def test_candidate_validation_has_one_batch_boundary() -> None:
    source = inspect.getsource(CandidateCollection.validate_buildable)
    assert source.count("check_prototypes_buildability") == 1
    assert "check_candidate_buildability" not in source
    assert "check_prototype_buildability" not in source
    assert "except Exception" not in source
    assert "hasattr(" not in source


def test_workspace_adapter_exposes_exact_scalar_and_batch_methods() -> None:
    scalar = inspect.getsource(WorkspaceAdapter.check_prototype_buildability)
    batch = inspect.getsource(WorkspaceAdapter.check_prototypes_buildability)
    combined = scalar + batch
    assert "self._ws.check_prototype_buildability(" in scalar
    assert "self._ws.check_prototypes_buildability(" in batch
    assert "getattr(" not in combined
    assert "NotImplementedError" not in combined


def test_sql_id_resolver_has_one_implementation_owner() -> None:
    resolver_source = (
        ROOT / "calm/project/infrastructure/db/id_resolver.py"
    ).read_text(encoding="utf-8")
    repos_root = ROOT / "calm/project/infrastructure/db/repos"
    repos_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(repos_root.glob("*.py"))
    )
    assert resolver_source.count("class SqlAlchemyIdResolver") == 1
    assert "class SqlAlchemyIdResolver" not in repos_source

    tree = ast.parse(
        (ROOT / "calm/project/infrastructure/db/uow.py").read_text(
            encoding="utf-8"
        )
    )
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "id_resolver"
    ]
    assert imports
