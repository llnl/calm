from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from calm.project.reproducibility import (
    DEFAULT_MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
)
from calm.public.errors import ProjectReproducibilityError
from calm.public.project import Project
from calm.public.records.reproducibility import (
    ProjectReproducibilityManifest,
    _build_reproducibility_manifest,
    _verify_reproducibility_manifest,
)


class _Collection:
    def __init__(self, rows):
        self._rows = list(rows)

    def records(self):
        return list(self._rows)




class _ConfigurationRepository:
    def get(self):
        return {
            "default_mlip": "demo-model",
            "default_calculator_uid_full": "calc:demo",
            "workflow_defaults": {
                "api_token": "do-not-persist-cleartext",
            },
        }


class _ConfigurationUnitOfWork:
    project_configuration = _ConfigurationRepository()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Workspace:
    _uow_factory = staticmethod(_ConfigurationUnitOfWork)


class _Project:
    def __init__(self, path: Path):
        self.path = path
        self._workspace = _Workspace()
        self._runs = [
            {
                "uid_full": "run:one",
                "id_short": "r_one",
                "run_type": "registry_search",
                "status": "done",
                "spec": {
                    "backend": {"name": "deterministic", "version": "1"},
                    "settings": {"seed": None},
                },
            },
            {
                "uid_full": "run:two",
                "id_short": "r_two",
                "run_type": "dataset",
                "status": "done",
                "spec": {"split": {"seed": 7}},
            },
        ]
        self._followups = [
            {
                "uid_full": "f:one",
                "id_short": "f_one",
                "kind": "registry_search",
                "payload": {
                    "actual_seed": 412,
                    "backend_identity": {"name": "deterministic", "version": "1"},
                },
            }
        ]

    def runs(self, **_kwargs):
        return _Collection(self._runs)

    def followups(self, **_kwargs):
        return _Collection(self._followups)


def _seed_project(root: Path) -> _Project:
    root.mkdir(parents=True)
    connection = sqlite3.connect(root / "calm.sqlite")
    connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
    connection.execute("INSERT INTO sample(value) VALUES ('one')")
    connection.commit()
    connection.close()
    # A stale file from the retired reporting subsystem is ignored by current
    # reproducibility snapshots.
    (root / "calm-public-records.json").write_text(
        json.dumps({"schema_version": 6}), encoding="utf-8"
    )
    artifact = root / "out" / "tables" / "result.csv"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("x,y\n1,2\n", encoding="utf-8")
    return _Project(root)


def test_manifest_records_versions_git_files_backends_seeds_environment_and_hardware(
    tmp_path: Path,
) -> None:
    project = _seed_project(tmp_path / "study.calm")

    manifest = _build_reproducibility_manifest(project)
    payload = manifest.to_dict()

    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert len(manifest.snapshot_id) == 64
    assert payload["software"]["calm_version"]
    assert "source_control" in payload["software"]
    assert payload["environment"]["python"]["version"]
    assert isinstance(payload["environment"]["packages"], dict)
    assert payload["hardware"]["cpu_count"] is None or payload["hardware"]["cpu_count"] > 0

    files = {row["path"]: row for row in payload["files"]}
    assert files["calm.sqlite"]["role"] == "database_snapshot"
    assert (
        files["calm.sqlite"]["snapshot_policy"]
        == "sqlite_logical_content_v1"
    )
    assert "calm-public-records.json" not in files
    assert files["out/tables/result.csv"]["role"] == "artifact"
    assert all(len(row["sha256"]) == 64 for row in files.values())

    assert payload["run_summary"]["by_type"] == {
        "dataset": 1,
        "registry_search": 1,
    }
    assert payload["seeds"]["counts"] == {
        "derived": 1,
        "explicit": 1,
        "unspecified": 1,
    }
    assert manifest.backends
    rendered = json.dumps(payload["backends"], sort_keys=True)
    configuration = json.dumps(payload["configuration"], sort_keys=True)
    assert "do-not-persist-cleartext" not in rendered
    assert "do-not-persist-cleartext" not in configuration
    assert "<redacted>" not in rendered
    assert "<redacted>" in configuration


def test_manifest_round_trip_and_verification_detects_project_file_changes(
    tmp_path: Path,
) -> None:
    project = _seed_project(tmp_path / "study.calm")
    destination = project.path / DEFAULT_MANIFEST_FILENAME

    recorded = _build_reproducibility_manifest(project)
    recorded.write(destination)
    loaded = ProjectReproducibilityManifest.read(destination)

    assert loaded.snapshot_id == recorded.snapshot_id
    clean = _verify_reproducibility_manifest(project, destination)
    assert clean.ok
    assert clean.errors == ()

    (project.path / "out" / "tables" / "result.csv").write_text(
        "x,y\n9,9\n", encoding="utf-8"
    )
    changed = _verify_reproducibility_manifest(project, destination)
    assert not changed.ok
    assert {issue.code for issue in changed.errors} == {"file_changed"}
    with pytest.raises(ProjectReproducibilityError, match="Project file changed"):
        changed.raise_for_errors()


def test_manifest_survives_sqlite_physical_rewrite_without_logical_change(
    tmp_path: Path,
) -> None:
    project = _seed_project(tmp_path / "study.calm")
    destination = project.path / DEFAULT_MANIFEST_FILENAME

    _build_reproducibility_manifest(project).write(destination)

    connection = sqlite3.connect(project.path / "calm.sqlite")
    try:
        connection.execute("REINDEX")
        connection.execute("VACUUM")
        connection.commit()
    finally:
        connection.close()

    report = _verify_reproducibility_manifest(project, destination)
    assert report.ok
    assert report.errors == ()


def test_manifest_write_is_atomic_and_requires_explicit_overwrite(tmp_path: Path) -> None:
    project = _seed_project(tmp_path / "study.calm")
    manifest = _build_reproducibility_manifest(project)
    destination = project.path / DEFAULT_MANIFEST_FILENAME

    manifest.write(destination)
    with pytest.raises(FileExistsError, match="overwrite=True"):
        manifest.write(destination)
    manifest.write(destination, overwrite=True)
    assert not list(destination.parent.glob(f".{destination.name}.*.tmp"))


def test_manifest_reader_rejects_tampered_snapshot_id(tmp_path: Path) -> None:
    project = _seed_project(tmp_path / "study.calm")
    destination = project.path / DEFAULT_MANIFEST_FILENAME
    _build_reproducibility_manifest(project).write(destination)
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["snapshot_id"] = "0" * 64
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProjectReproducibilityError, match="invalid snapshot_id"):
        ProjectReproducibilityManifest.read(destination)


def test_project_exposes_reproducibility_manifest_methods() -> None:
    assert hasattr(Project, "reproducibility_manifest")
    assert hasattr(Project, "write_reproducibility_manifest")
    assert hasattr(Project, "verify_reproducibility_manifest")


def test_project_writer_and_verifier_use_default_project_manifest_path(tmp_path: Path) -> None:
    project = _seed_project(tmp_path / "study.calm")

    manifest = Project.write_reproducibility_manifest(project, overwrite=True)
    destination = project.path / DEFAULT_MANIFEST_FILENAME

    assert destination.is_file()
    assert ProjectReproducibilityManifest.read(destination).snapshot_id == manifest.snapshot_id
    report = Project.verify_reproducibility_manifest(project)
    assert report.ok


def test_reproducibility_json_projection_propagates_broken_explicit_adapter() -> None:
    from calm.project.reproducibility import jsonable

    class BrokenRecord:
        def to_dict(self):
            raise RuntimeError("record conversion failed")

    with pytest.raises(RuntimeError, match="record conversion failed"):
        jsonable(BrokenRecord())


def test_reproducibility_json_projection_rejects_opaque_objects() -> None:
    from calm.project.reproducibility import jsonable

    with pytest.raises(TypeError, match="unsupported object"):
        jsonable(object())
