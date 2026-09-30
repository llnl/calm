"""Standard-library helpers for project reproducibility snapshots.

The public typed facade lives in :mod:`calm.public.records.reproducibility`.  This
module deliberately avoids SQLAlchemy and optional scientific dependencies so
manifest generation remains available in dependency-light environments.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from importlib import metadata
from math import isfinite
from pathlib import Path
from typing import Any, Callable

MANIFEST_SCHEMA_VERSION = "calm.reproducibility.v2"
DEFAULT_MANIFEST_FILENAME = "calm-reproducibility-manifest.json"

_RELEVANT_ENVIRONMENT_VARIABLES = (
    "CONDA_DEFAULT_ENV",
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "PYTHONHASHSEED",
    "ROCR_VISIBLE_DEVICES",
    "VIRTUAL_ENV",
)

_SECRET_FRAGMENTS = (
    "access_key",
    "api_key",
    "credential",
    "password",
    "secret",
    "token",
)

_BACKEND_KEYS = {
    "backend",
    "backend_identity",
    "calculator",
    "calculator_spec",
    "calculator_specs",
    "mlip",
    "potential",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def jsonable(value: Any, *, _path: str = "$") -> Any:
    """Return one deterministic exact JSON-compatible projection.

    Reproducibility identities must not depend on ``repr`` or on a fallback
    selected after an explicit conversion hook failed. Unsupported values and
    broken ``to_dict()`` implementations therefore raise with their path.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"Reproducibility value at {_path} must be finite.")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return jsonable(value.value, _path=_path)

    try:
        import numpy as np  # type: ignore
    except ImportError:  # pragma: no cover - NumPy is a CALM dependency
        np = None  # type: ignore[assignment]
    if np is not None:
        if isinstance(value, np.generic):
            return jsonable(value.item(), _path=_path)
        if isinstance(value, np.ndarray):
            return jsonable(value.tolist(), _path=_path)

    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value), _path=_path)
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            if not isinstance(key, str):
                raise TypeError(
                    f"Reproducibility mapping key at {_path} must be a string."
                )
            normalized[key] = jsonable(item, _path=f"{_path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            jsonable(item, _path=f"{_path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, (set, frozenset)):
        normalized = [jsonable(item, _path=f"{_path}[]") for item in value]
        return sorted(normalized, key=canonical_json)

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if converted is value:
            raise TypeError(
                f"{type(value).__name__}.to_dict() returned the original object "
                f"at {_path}."
            )
        return jsonable(converted, _path=_path)

    raise TypeError(
        "Reproducibility values must have an exact JSON representation; "
        f"unsupported {type(value).__name__} at {_path}."
    )


def canonical_json(value: Any) -> str:
    return json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return digest.hexdigest(), size


def _ignored_project_file(relative: Path) -> bool:
    parts = relative.parts
    if not parts:
        return True
    if any(part in {".git", "__pycache__", ".pytest_cache"} for part in parts):
        return True
    name = relative.name
    if name == DEFAULT_MANIFEST_FILENAME or name.endswith(".reproducibility.json"):
        return True
    # Retired automatic reporting artifact. Old files are intentionally inert
    # and excluded so deleting them cannot change a current project snapshot.
    if name == "calm-public-records.json":
        return True
    if name in {"calm.sqlite-wal", "calm.sqlite-shm", "calm.sqlite-journal"}:
        return True
    if name.endswith((".tmp", ".swp", "~")):
        return True
    return False


def project_file_inventory(
    root: Path,
    *,
    database_snapshot_hasher: Callable[[Path], tuple[str, int]],
    database_snapshot_policy: str,
    exclude_paths: Iterable[Path] = (),
) -> list[dict[str, Any]]:
    """Hash stable project files and a deterministic logical SQLite snapshot."""

    excluded = {Path(path).expanduser().resolve() for path in exclude_paths}
    rows: list[dict[str, Any]] = []
    database = root / "calm.sqlite"
    if database.exists():
        digest, size = database_snapshot_hasher(database)
        rows.append(
            {
                "path": "calm.sqlite",
                "role": "database_snapshot",
                "sha256": digest,
                "size_bytes": size,
                "snapshot_policy": str(database_snapshot_policy),
            }
        )

    for path in sorted(root.rglob("*")):
        if (
            path == database
            or path.resolve() in excluded
            or path.is_symlink()
            or not path.is_file()
        ):
            continue
        relative = path.relative_to(root)
        if _ignored_project_file(relative):
            continue
        digest, size = hash_file(path)
        role = "project_file"
        if relative.parts and relative.parts[0] in {"out", "CALM_results"}:
            role = "artifact"
        rows.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "sha256": digest,
                "size_bytes": size,
            }
        )
    return rows


def installed_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    try:
        distributions = metadata.distributions()
    except Exception:
        return packages
    for distribution in distributions:
        try:
            name = distribution.metadata.get("Name")
            if not name:
                continue
            packages[str(name).lower()] = str(distribution.version)
        except Exception:
            continue
    return dict(sorted(packages.items()))


def environment_snapshot() -> dict[str, Any]:
    return {
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "executable": sys.executable,
            "prefix": sys.prefix,
        },
        "packages": installed_packages(),
        "variables": {
            key: os.environ[key]
            for key in _RELEVANT_ENVIRONMENT_VARIABLES
            if key in os.environ
        },
    }


def hardware_snapshot() -> dict[str, Any]:
    memory_bytes: int | None = None
    try:
        memory_bytes = int(os.sysconf("SC_PAGE_SIZE")) * int(
            os.sysconf("SC_PHYS_PAGES")
        )
    except Exception:
        pass
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "memory_bytes": memory_bytes,
    }


def _git(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *command],
        cwd=str(cwd),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def source_control_snapshot(source_path: Path) -> dict[str, Any]:
    """Record the Git state containing the imported CALM source, if available."""

    try:
        root = Path(_git(["rev-parse", "--show-toplevel"], cwd=source_path)).resolve()
        commit = _git(["rev-parse", "HEAD"], cwd=root)
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
        describe = _git(["describe", "--always", "--dirty", "--tags"], cwd=root)
        status = _git(["status", "--porcelain=v1", "--untracked-files=all"], cwd=root)
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=str(root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        untracked: list[dict[str, Any]] = []
        for line in status.splitlines():
            if not line.startswith("?? "):
                continue
            relative = line[3:]
            path = root / relative
            row: dict[str, Any] = {"path": relative}
            if path.is_file() and not path.is_symlink():
                digest, size = hash_file(path)
                row.update({"sha256": digest, "size_bytes": size})
            untracked.append(row)
        return {
            "available": True,
            "root": str(root),
            "commit": commit,
            "branch": branch,
            "describe": describe,
            "dirty": bool(status),
            "tracked_diff_sha256": sha256_bytes(diff),
            "untracked_files": untracked,
        }
    except Exception as exc:
        return {
            "available": False,
            "root": None,
            "commit": None,
            "branch": None,
            "describe": None,
            "dirty": None,
            "tracked_diff_sha256": None,
            "untracked_files": [],
            "reason": str(exc),
        }


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if any(fragment in normalized for fragment in _SECRET_FRAGMENTS):
                out[str(key)] = "<redacted>"
            else:
                out[str(key)] = redact_sensitive(item)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item) for item in value]
    return jsonable(value)


def _walk(value: Any, *, path: str) -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, Mapping):
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            yield child, key_text, item
            yield from _walk(item, path=child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            yield from _walk(item, path=child)


def collect_backend_identities(
    sources: Iterable[tuple[str, Any]],
) -> list[dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}

    def add(source: str, value: Any) -> None:
        normalized = jsonable(value)
        fingerprint = sha256_value(normalized)
        row = identities.setdefault(
            fingerprint,
            {
                "fingerprint": fingerprint,
                "identity": redact_sensitive(normalized),
                "sources": [],
            },
        )
        if source not in row["sources"]:
            row["sources"].append(source)

    for source_name, payload in sources:
        for path, key, value in _walk(payload, path=source_name):
            key_normalized = key.lower()
            if key_normalized not in _BACKEND_KEYS:
                continue
            if key_normalized == "calculator_specs" and isinstance(value, Mapping):
                for target, spec in value.items():
                    add(f"{path}.{target}", spec)
            else:
                add(path, value)
    for row in identities.values():
        row["sources"].sort()
    return sorted(identities.values(), key=lambda row: row["fingerprint"])


def collect_seed_policy(sources: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for source_name, payload in sources:
        for path, key, value in _walk(payload, path=source_name):
            key_normalized = key.lower()
            if not (
                key_normalized == "seed"
                or key_normalized == "seed_policy"
                or key_normalized.endswith("_seed")
            ):
                continue
            if key_normalized == "seed_policy":
                policy = str(value) if value not in (None, "") else "unspecified"
            elif value is None:
                policy = "unspecified"
            elif "actual_seed" in key_normalized or "derived_seed" in key_normalized:
                policy = "derived"
            else:
                policy = "explicit"
            observations.append(
                {
                    "source": path,
                    "field": key,
                    "policy": policy,
                    "value": jsonable(value),
                }
            )
    observations.sort(key=lambda row: (row["source"], row["field"]))
    counts = Counter(row["policy"] for row in observations)
    return {
        "statement": (
            "CALM records every observed explicit, derived, and unspecified seed field. "
            "A missing observation does not prove that an external backend was deterministic."
        ),
        "counts": dict(sorted(counts.items())),
        "observations": observations,
    }


def run_inventory(
    runs: Iterable[Any],
) -> tuple[list[dict[str, Any]], list[tuple[str, Any]]]:
    rows: list[dict[str, Any]] = []
    sources: list[tuple[str, Any]] = []
    for run in runs:
        row = jsonable(run)
        if not isinstance(row, Mapping):
            continue
        uid = str(row.get("uid_full") or "")
        short = str(row.get("id_short") or "")
        run_type = str(row.get("run_type") or "")
        spec = row.get("spec") or {}
        rows.append(
            {
                "uid_full": uid,
                "id_short": short,
                "run_type": run_type,
                "status": str(row.get("status") or ""),
                "spec_sha256": sha256_value(spec),
            }
        )
        sources.append((f"run:{short or uid}:{run_type}.spec", spec))
    rows.sort(key=lambda row: (row["run_type"], row["id_short"], row["uid_full"]))
    return rows, sources


def followup_sources(followups: Iterable[Any]) -> list[tuple[str, Any]]:
    sources: list[tuple[str, Any]] = []
    for item in followups:
        row = jsonable(item)
        if not isinstance(row, Mapping):
            continue
        uid = str(row.get("uid_full") or "")
        short = str(row.get("id_short") or "")
        kind = str(row.get("kind") or "")
        payload = row.get("payload") or {}
        sources.append((f"followup:{short or uid}:{kind}.payload", payload))
    return sources


def snapshot_id(payload: Mapping[str, Any]) -> str:
    stable = dict(jsonable(payload))
    stable.pop("generated_at_utc", None)
    project = dict(stable.get("project") or {})
    project.pop("path", None)
    stable["project"] = project
    stable.pop("snapshot_id", None)
    return sha256_value(stable)


def write_json_atomic(
    path: Path, payload: Mapping[str, Any], *, overwrite: bool
) -> None:
    path = path.expanduser().resolve()
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Reproducibility manifest already exists: {path}. Pass overwrite=True to replace it."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            jsonable(payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    fd, raw_tmp = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(fd)
    tmp = Path(raw_tmp)
    try:
        tmp.write_text(encoded, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
