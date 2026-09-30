"""Provenance collection and atomic JSON writing for claim benchmarks."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .claim_ids import ClaimId
from .schemas import (
    CLAIM_SUITE_VERSION,
    ArtifactRecord,
    BenchmarkManifest,
    RepositoryState,
)


DEFAULT_DISTRIBUTIONS = (
    "calm",
    "numpy",
    "scipy",
    "ase",
    "spglib",
    "pymatgen",
    "sqlalchemy",
    "pandas",
    "matplotlib",
)


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON value deterministically for hashing and persistence."""

    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: str | Path, value: Any) -> Path:
    """Write canonical JSON through a same-directory temporary file."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    temporary.write_bytes(canonical_json_bytes(value))
    temporary.replace(destination)
    return destination


def artifact_record(
    path: str | Path,
    *,
    relative_to: str | Path,
    media_type: str | None = None,
) -> ArtifactRecord:
    artifact_path = Path(path).resolve()
    root = Path(relative_to).resolve()
    return ArtifactRecord(
        path=artifact_path.relative_to(root).as_posix(),
        sha256=sha256_file(artifact_path),
        media_type=media_type,
    )


def _git_output(repository_root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def repository_state(repository_root: str | Path) -> RepositoryState:
    root = Path(repository_root).resolve()
    commit = _git_output(root, "rev-parse", "HEAD")
    status = _git_output(root, "status", "--porcelain", "--untracked-files=normal")
    dirty = None if status is None else bool(status)
    return RepositoryState(root=str(root), commit=commit or None, dirty=dirty)


def dependency_versions(
    distributions: Sequence[str] = DEFAULT_DISTRIBUTIONS,
) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for distribution in distributions:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return versions


def environment_snapshot() -> dict[str, Any]:
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "description": platform.platform(),
        },
        "dependencies": dependency_versions(),
    }


def build_manifest(
    *,
    repository_root: str | Path,
    output_root: str | Path,
    command: Sequence[str],
    selected_claims: Sequence[ClaimId],
    artifacts: Sequence[ArtifactRecord] = (),
    fixture_hashes: Mapping[str, str] | None = None,
    policy_settings: Mapping[str, Any] | None = None,
    seeds: Mapping[str, int] | None = None,
    suite_version: str = CLAIM_SUITE_VERSION,
) -> BenchmarkManifest:
    """Build a complete benchmark manifest without importing CALM or pymatgen."""

    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return BenchmarkManifest(
        created_at_utc=created_at,
        suite_version=suite_version,
        command=tuple(str(token) for token in command),
        output_root=str(Path(output_root).resolve()),
        repository=repository_state(repository_root),
        environment=environment_snapshot(),
        fixture_hashes=dict(fixture_hashes or {}),
        policy_settings=dict(policy_settings or {}),
        seeds=dict(seeds or {}),
        selected_claims=tuple(selected_claims),
        artifacts=tuple(artifacts),
    )
