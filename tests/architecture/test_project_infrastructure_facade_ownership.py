from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _class(path: Path, name: str) -> ast.ClassDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _repository_source(*names: str) -> str:
    root = ROOT / "calm" / "project" / "infrastructure" / "db" / "repos"
    selected = names or tuple(
        path.name
        for path in sorted(root.glob("*.py"))
        if path.name not in {"__init__.py", "_common.py"}
    )
    return "\n".join(
        (root / name).read_text(encoding="utf-8") for name in selected
    )


def test_retired_runner_store_and_workspace_persistence_modules_stay_absent() -> None:
    retired_trees = (
        ROOT / "calm" / "project" / "runner",
        ROOT / "calm" / "project" / "runner_payloads",
        ROOT / "calm" / "project" / "stores",
    )
    retired_files = [
        path
        for tree in retired_trees
        for path in tree.rglob("*.py")
    ]
    workspace_persistence = (
        ROOT / "calm" / "project" / "runtime" / "workspace_persistence.py"
    )
    assert retired_files == []
    assert not workspace_persistence.exists()


def test_retired_project_ux_namespaces_have_no_runtime_source() -> None:
    ux = ROOT / "calm" / "project" / "ux"
    assert list(ux.rglob("*.py")) == []


def test_workspace_slab_queries_do_not_repair_or_allocate_identifiers() -> None:
    workspace = (
        ROOT / "calm" / "project" / "runtime" / "workspace.py"
    ).read_text(encoding="utf-8")
    helpers = (
        ROOT / "calm" / "project" / "runtime" / "helpers.py"
    ).read_text(encoding="utf-8")

    assert "attach_bulk_id_short_to_slab" not in workspace
    assert "attach_bulk_id_short_to_slab" not in helpers

    tree = ast.parse(workspace)
    workspace_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Workspace"
    )
    list_slabs = next(
        node
        for node in workspace_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "list_slabs"
    )
    source = ast.unparse(list_slabs)
    assert "ensure_short_id" not in source
    assert "except Exception" not in source


def test_slab_writer_owns_tilt_metadata_and_repository_only_projects_it() -> None:
    writer = (
        ROOT / "calm" / "project" / "application" / "slabs.py"
    ).read_text(encoding="utf-8")
    repository = _repository_source("slabs.py")

    assert 'if "calm:tilt" not in slab_atoms.info:' in writer
    assert 'slab_atoms.info["calm:tilt"]' in writer
    assert "compute_slab_tilt_metadata" in writer
    assert "compute_slab_tilt_metadata" not in repository
    assert "dict_to_atoms" not in repository
    assert "extract_canonical_tilt_metadata" in repository


def test_edge_payloads_are_strict_and_payload_aware() -> None:
    helpers = (
        ROOT
        / "calm"
        / "project"
        / "infrastructure"
        / "db"
        / "payload_helpers.py"
    ).read_text(encoding="utf-8")
    repositories = _repository_source("lineage.py")

    workspace = (
        ROOT / "calm" / "project" / "runtime" / "workspace.py"
    ).read_text(encoding="utf-8")
    edge_method = workspace.split(
        "    def add_provenance_edge(",
        maxsplit=1,
    )[1].split("\n    def ", maxsplit=1)[0]

    assert "from calm.serialization.json import canonical_json" in helpers
    assert "canonical = canonical_json(payload)" in helpers
    assert "except Exception" not in helpers
    assert "payload=payload or {}" not in edge_method
    assert "payload=payload" in edge_method
    assert '"payload_hash": expected_hash' in repositories
    assert "Current edge rows require canonical payload_json" in repositories
    assert "payload_hash does not match payload_json" in repositories


def test_sql_repositories_and_ids_cannot_reconnect_outside_the_uow() -> None:
    db_root = ROOT / "calm" / "project" / "infrastructure" / "db"
    repositories = _repository_source()
    resolver = (db_root / "id_resolver.py").read_text(encoding="utf-8")
    uow = (db_root / "uow.py").read_text(encoding="utf-8")

    assert "class _ConnProxy" not in uow
    assert "raw SQL strings" not in uow
    assert "sa_text" not in uow

    for retired in (
        "_safe_execute",
        "repositories sometimes outlive",
        "repositories may outlive",
        "engine.connect()",
        "engine.begin()",
    ):
        assert retired not in repositories
        assert retired not in resolver

    for path in db_root.rglob("*.py"):
        if path.name == "uow.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "engine.connect(" not in source
        assert "engine.begin(" not in source


def test_project_ports_expose_only_current_persistence_capabilities() -> None:
    ids = (ROOT / "calm" / "project" / "ports" / "ids.py").read_text(
        encoding="utf-8"
    )
    repositories = (
        ROOT / "calm" / "project" / "ports" / "repos.py"
    ).read_text(encoding="utf-8")

    for retired in (
        "def resolve_bulk(",
        "def resolve_artifact(",
        "def resolve_job(",
        "def ensure_job_id(",
        "def ensure_campaign_id(",
        "def ensure_campaign_run_id(",
    ):
        assert retired not in ids

    assert "def update_parent_links(" not in repositories
    artifact_port = repositories.split(
        "class ArtifactRepository", maxsplit=1
    )[1].split("\n\nclass EdgeRepository", maxsplit=1)[0]
    assert "def get_by_uid_full(" in artifact_port



def test_artifact_store_port_matches_the_only_current_implementation() -> None:
    port_path = ROOT / "calm" / "project" / "ports" / "artifacts.py"
    store_path = (
        ROOT
        / "calm"
        / "project"
        / "infrastructure"
        / "artifacts"
        / "fs_store.py"
    )
    port = _class(port_path, "ArtifactStore")
    store = _class(store_path, "FSArtifactStore")

    port_methods = {
        node.name
        for node in port.body
        if isinstance(node, ast.FunctionDef)
    }
    store_methods = {
        node.name
        for node in store.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    assert port_methods == {"ensure_run_layout", "put_bytes", "uri_for"}
    assert store_methods == port_methods

    store_source = store_path.read_text(encoding="utf-8")
    assert "def allocate(" not in store_source
    assert "def resolve(" not in store_source
    assert ".as_uri()" in store_source


def test_workspace_accepts_only_current_workspace_local_artifact_uris() -> None:
    workspace = (
        ROOT / "calm" / "project" / "runtime" / "workspace.py"
    ).read_text(encoding="utf-8")
    resolver = (
        ROOT / "calm" / "project" / "runtime" / "artifact_uri.py"
    ).read_text(encoding="utf-8")

    assert "self._artifact_store" not in workspace
    assert "path.relative_to(self._out_dir)" in workspace
    assert "legacy relative paths" not in workspace
    assert 'parsed.scheme != "file"' in resolver
    assert "if parsed.netloc:" in resolver
    assert "parsed.query or parsed.fragment" in resolver


def test_repository_short_id_lookups_stay_owned_by_the_id_resolver() -> None:
    sources = [
        (ROOT / "calm/project/ports/repos.py").read_text(encoding="utf-8"),
        _repository_source(),
        (ROOT / "calm/project/runtime/workspace.py").read_text(encoding="utf-8"),
    ]
    for source in sources:
        assert "get_by_id_short" not in source


def test_calculator_rows_require_the_current_canonical_specification() -> None:
    repositories = _repository_source("calculators.py")
    resolution = (
        ROOT
        / "calm"
        / "project"
        / "application"
        / "followups"
        / "calculator_resolution.py"
    ).read_text(encoding="utf-8")

    assert "_calculator_options_from_storage" not in repositories
    assert "CalculatorSpec.from_json(spec_json).to_dict()" in repositories
    assert "CalculatorSpec.from_dict(calc_record.spec)" in resolution
