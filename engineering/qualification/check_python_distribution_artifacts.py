#!/usr/bin/env python3
"""Validate exact CALM wheel and source-distribution contents."""

from __future__ import annotations

import argparse
import base64
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tarfile
from typing import Any, Mapping
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = (
    REPO_ROOT
    / "engineering"
    / "architecture"
    / "current-python-distribution.json"
)
PYPROJECT = REPO_ROOT / "pyproject.toml"
_SCHEMA_VERSION = "calm.python_distribution.v2"
_RESULT_SCHEMA = "calm.python_distribution_artifacts.v2"
_CONTRACT_KEYS = frozenset({"schema_version", "license_policy", "sdist", "wheel"})
_LICENSE_KEYS = frozenset(
    {
        "copyright_holder",
        "copyright_year",
        "expression",
        "files",
        "status",
    }
)
_SDIST_KEYS = frozenset(
    {
        "egg_info_files",
        "generated_root_files",
        "manifest_directives",
        "profile",
        "root_directories",
        "source_root_files",
    }
)
_WHEEL_KEYS = frozenset(
    {
        "dist_info_files",
        "package_file_suffixes",
        "package_root",
        "profile",
    }
)
_LICENSE_FILES = ("LICENSE", "NOTICE")
_MANIFEST_DIRECTIVE_NAMES = frozenset(
    {"exclude", "global-exclude", "include", "prune", "recursive-exclude"}
)


def _string_list(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> list[str]:
    value = payload.get(name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        errors.append(f"{name} must be a list of nonempty strings")
        return []
    if value != sorted(value):
        errors.append(f"{name} must be sorted")
    if len(value) != len(set(value)):
        errors.append(f"{name} must not contain duplicates")
    return list(value)


def _token_rows(
    payload: Mapping[str, Any],
    name: str,
    errors: list[str],
) -> list[tuple[str, ...]]:
    value = payload.get(name)
    if not isinstance(value, list):
        errors.append(f"{name} must be a list")
        return []
    rows: list[tuple[str, ...]] = []
    for index, row in enumerate(value):
        if not isinstance(row, list) or len(row) < 2 or any(
            not isinstance(item, str) or not item for item in row
        ):
            errors.append(
                f"{name}[{index}] must contain at least two nonempty strings"
            )
            continue
        token_row = tuple(row)
        if token_row[0] not in _MANIFEST_DIRECTIVE_NAMES:
            errors.append(
                f"{name}[{index}] uses unsupported directive {token_row[0]!r}"
            )
        rows.append(token_row)
    if rows != sorted(rows):
        errors.append(f"{name} must be sorted")
    if len(rows) != len(set(rows)):
        errors.append(f"{name} must not contain duplicates")
    return rows


def _validate_manifest(
    path: Path,
    *,
    expected: list[tuple[str, ...]],
    errors: list[str],
) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"could not read MANIFEST.in: {exc}")
        return
    observed: list[tuple[str, ...]] = []
    for line_number, raw_line in enumerate(lines, start=1):
        try:
            parts = shlex.split(raw_line, comments=True, posix=True)
        except ValueError as exc:
            errors.append(f"MANIFEST.in line {line_number} is invalid: {exc}")
            continue
        if not parts:
            continue
        row = tuple(parts)
        if row[0] not in _MANIFEST_DIRECTIVE_NAMES:
            errors.append(
                f"MANIFEST.in uses unsupported directive {row[0]!r} "
                f"on line {line_number}"
            )
            continue
        if len(row) < 2:
            errors.append(
                f"MANIFEST.in directive {row[0]!r} on line {line_number} "
                "requires at least one argument"
            )
            continue
        if row in observed:
            errors.append(f"MANIFEST.in repeats directive {row!r}")
        observed.append(row)
    if observed != expected:
        errors.append(
            "MANIFEST.in directives must exactly match the distribution "
            f"contract: expected {expected}, observed {observed}"
        )


def _mapping(
    payload: Mapping[str, Any],
    name: str,
    expected_keys: frozenset[str],
    errors: list[str],
) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        errors.append(f"{name} must be a JSON object")
        return {}
    observed = set(value)
    if observed != expected_keys:
        errors.append(
            f"{name} keys must be exactly {sorted(expected_keys)}, "
            f"observed {sorted(observed)}"
        )
    return value


def _load_contract(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"could not read distribution contract: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("distribution contract must be a JSON object")
        return {}
    observed = set(payload)
    if observed != _CONTRACT_KEYS:
        errors.append(
            "distribution contract keys must be exactly "
            f"{sorted(_CONTRACT_KEYS)}, observed {sorted(observed)}"
        )
    if payload.get("schema_version") != _SCHEMA_VERSION:
        errors.append(
            f"distribution contract schema must be {_SCHEMA_VERSION!r}"
        )

    license_policy = _mapping(
        payload, "license_policy", _LICENSE_KEYS, errors
    )
    expected_license = {
        "copyright_holder": "Lawrence Livermore National Security, LLC",
        "copyright_year": 2026,
        "expression": "MIT",
        "status": "approved",
    }
    for name, expected in expected_license.items():
        if license_policy.get(name) != expected:
            errors.append(f"license_policy.{name} must be {expected!r}")
    license_files = license_policy.get("files")
    if not isinstance(license_files, dict):
        errors.append("license_policy.files must be a JSON object")
        license_files = {}
    if list(license_files) != list(_LICENSE_FILES):
        errors.append(
            f"license_policy.files must be exactly {list(_LICENSE_FILES)}"
        )
    for name, digest in license_files.items():
        if not isinstance(digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", digest
        ) is None:
            errors.append(
                f"license_policy.files[{name!r}] must be lowercase SHA-256"
            )

    sdist = _mapping(payload, "sdist", _SDIST_KEYS, errors)
    if sdist.get("profile") != "minimal_installation_source":
        errors.append("sdist.profile must be 'minimal_installation_source'")
    for name in (
        "egg_info_files",
        "generated_root_files",
        "root_directories",
        "source_root_files",
    ):
        _string_list(sdist, name, errors)

    wheel = _mapping(payload, "wheel", _WHEEL_KEYS, errors)
    if wheel.get("profile") != "installable_package_only":
        errors.append("wheel.profile must be 'installable_package_only'")
    if wheel.get("package_root") != "calm":
        errors.append("wheel.package_root must be 'calm'")
    for name in ("dist_info_files", "package_file_suffixes"):
        _string_list(wheel, name, errors)
    return payload


def _load_project(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"could not read pyproject.toml: {exc}")
        return {}
    project = payload.get("project")
    if not isinstance(project, dict):
        errors.append("pyproject.toml must define [project]")
        return {}
    for field in ("name", "version", "requires-python"):
        if not isinstance(project.get(field), str) or not project[field]:
            errors.append(f"project.{field} must be a nonempty string")
    return payload


def _normalized_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).strip("_")


def _safe_archive_name(name: str) -> bool:
    if not name or "\\" in name or "\x00" in name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _tracked_package_files(
    repo_root: Path,
    package_root: str,
    suffixes: set[str],
    errors: list[str],
) -> set[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", package_root],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        errors.append(f"could not enumerate tracked package files: {detail}")
        return set()
    result: set[str] = set()
    unsupported: list[str] = []
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        path = repo_root / relative
        if not path.is_file():
            continue
        if path.suffix not in suffixes:
            unsupported.append(relative)
            continue
        result.add(relative)
    if unsupported:
        errors.append(
            "tracked package files fall outside package_file_suffixes: "
            + ", ".join(sorted(unsupported))
        )
    if not result:
        errors.append("tracked package source set is empty")
    return result


def _metadata(
    content: bytes,
    *,
    label: str,
    project: Mapping[str, Any],
    license_policy: Mapping[str, Any],
    errors: list[str],
) -> Any:
    message = BytesParser(policy=policy.default).parsebytes(content)
    expected = {
        "Name": project.get("name"),
        "Version": project.get("version"),
    }
    for header, value in expected.items():
        if message.get(header) != value:
            errors.append(
                f"{label} {header} must be {value!r}, "
                f"observed {message.get(header)!r}"
            )
    expected_python = {
        item.strip()
        for item in str(project.get("requires-python", "")).split(",")
        if item.strip()
    }
    observed_python = {
        item.strip()
        for item in str(message.get("Requires-Python", "")).split(",")
        if item.strip()
    }
    if observed_python != expected_python:
        errors.append(
            f"{label} Requires-Python must be equivalent to "
            f"{project.get('requires-python')!r}, observed "
            f"{message.get('Requires-Python')!r}"
        )
    if message.get_all("License"):
        errors.append(f"{label} must omit the deprecated License header")
    expected_expression = license_policy.get("expression")
    observed_expressions = message.get_all("License-Expression", [])
    if observed_expressions != [expected_expression]:
        errors.append(
            f"{label} License-Expression must be exactly "
            f"{expected_expression!r}, observed {observed_expressions!r}"
        )
    expected_files = list(license_policy.get("files", {}))
    observed_files = message.get_all("License-File", [])
    if observed_files != expected_files:
        errors.append(
            f"{label} License-File headers must be exactly "
            f"{expected_files!r}, observed {observed_files!r}"
        )
    license_classifiers = [
        value
        for value in message.get_all("Classifier", [])
        if value.startswith("License ::")
    ]
    if license_classifiers:
        errors.append(
            f"{label} must omit license classifiers when using License-Expression"
        )
    return message


def _record_rows(content: bytes, errors: list[str]) -> dict[str, tuple[str, str]]:
    try:
        rows = list(csv.reader(io.StringIO(content.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        errors.append(f"wheel RECORD is invalid: {exc}")
        return {}
    result: dict[str, tuple[str, str]] = {}
    for row in rows:
        if len(row) != 3:
            errors.append(f"wheel RECORD row must have three fields: {row!r}")
            continue
        path, digest, size = row
        if path in result:
            errors.append(f"wheel RECORD contains duplicate path {path!r}")
            continue
        result[path] = (digest, size)
    return result


def _urlsafe_sha256(content: bytes) -> str:
    digest = hashlib.sha256(content).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _validate_wheel(
    path: Path,
    *,
    project: Mapping[str, Any],
    contract: Mapping[str, Any],
    source_license_files: Mapping[str, bytes],
    tracked_package_files: set[str],
    errors: list[str],
) -> dict[str, Any]:
    name = str(project.get("name", ""))
    version = str(project.get("version", ""))
    normalized_name = _normalized_distribution_name(name)
    expected_filename = f"{normalized_name}-{version}-py3-none-any.whl"
    if path.name != expected_filename:
        errors.append(
            f"wheel filename must be {expected_filename!r}, observed {path.name!r}"
        )
    dist_info = f"{normalized_name}-{version}.dist-info"
    wheel_policy = contract.get("wheel", {})
    dist_info_files = set(wheel_policy.get("dist_info_files", ()))
    expected_files = tracked_package_files | {
        f"{dist_info}/{filename}" for filename in dist_info_files
    }

    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("wheel contains duplicate archive member names")
            unsafe = sorted(name for name in names if not _safe_archive_name(name))
            if unsafe:
                errors.append("wheel contains unsafe member paths: " + ", ".join(unsafe))
            directories = sorted(name for name in names if name.endswith("/"))
            if directories:
                errors.append(
                    "wheel must not contain explicit directory entries: "
                    + ", ".join(directories)
                )
            observed_files = {name for name in names if not name.endswith("/")}
            missing = sorted(expected_files - observed_files)
            unexpected = sorted(observed_files - expected_files)
            if missing:
                errors.append("wheel is missing required files: " + ", ".join(missing))
            if unexpected:
                errors.append("wheel contains unexpected files: " + ", ".join(unexpected))

            metadata_path = f"{dist_info}/METADATA"
            wheel_path = f"{dist_info}/WHEEL"
            top_level_path = f"{dist_info}/top_level.txt"
            record_path = f"{dist_info}/RECORD"
            content = {
                name: archive.read(name)
                for name in observed_files
                if name in expected_files
            }
            if metadata_path in content:
                _metadata(
                    content[metadata_path],
                    label="wheel METADATA",
                    project=project,
                    license_policy=contract.get("license_policy", {}),
                    errors=errors,
                )
            for filename, expected_content in source_license_files.items():
                member = f"{dist_info}/licenses/{filename}"
                if member in content and content[member] != expected_content:
                    errors.append(
                        f"wheel license bytes differ from repository: {filename}"
                    )
            if top_level_path in content and content[top_level_path] != b"calm\n":
                errors.append("wheel top_level.txt must contain exactly 'calm\\n'")
            if wheel_path in content:
                wheel_message = BytesParser(policy=policy.default).parsebytes(
                    content[wheel_path]
                )
                if wheel_message.get("Root-Is-Purelib") != "true":
                    errors.append("wheel must declare Root-Is-Purelib: true")
                if wheel_message.get_all("Tag", []) != ["py3-none-any"]:
                    errors.append("wheel must declare exactly Tag: py3-none-any")
            if record_path in content:
                rows = _record_rows(content[record_path], errors)
                if set(rows) != observed_files:
                    errors.append("wheel RECORD paths must exactly match wheel members")
                for member in sorted(observed_files):
                    if member not in rows:
                        continue
                    digest, size = rows[member]
                    if member == record_path:
                        if digest or size:
                            errors.append("wheel RECORD self-entry must omit hash and size")
                        continue
                    payload = archive.read(member)
                    expected_digest = f"sha256={_urlsafe_sha256(payload)}"
                    if digest != expected_digest:
                        errors.append(f"wheel RECORD hash mismatch for {member}")
                    if size != str(len(payload)):
                        errors.append(f"wheel RECORD size mismatch for {member}")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        errors.append(f"could not inspect wheel {path}: {exc}")
        return {"filename": path.name, "file_count": 0}
    return {"filename": path.name, "file_count": len(expected_files)}


def _tar_file_bytes(archive: tarfile.TarFile, member: tarfile.TarInfo) -> bytes:
    handle = archive.extractfile(member)
    if handle is None:
        raise OSError(f"could not read tar member {member.name}")
    return handle.read()


def _validate_sdist(
    path: Path,
    *,
    repo_root: Path,
    project: Mapping[str, Any],
    contract: Mapping[str, Any],
    tracked_package_files: set[str],
    errors: list[str],
) -> dict[str, Any]:
    name = str(project.get("name", ""))
    version = str(project.get("version", ""))
    expected_root = f"{name.replace('_', '-')}-{version}"
    expected_filename = f"{expected_root}.tar.gz"
    if path.name != expected_filename:
        errors.append(
            f"sdist filename must be {expected_filename!r}, observed {path.name!r}"
        )
    sdist_policy = contract.get("sdist", {})
    source_root_files = set(sdist_policy.get("source_root_files", ()))
    generated_root_files = set(sdist_policy.get("generated_root_files", ()))
    root_directories = set(sdist_policy.get("root_directories", ()))
    egg_info_files = set(sdist_policy.get("egg_info_files", ()))
    expected_root_entries = source_root_files | generated_root_files | root_directories

    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            names = [member.name.rstrip("/") for member in members]
            if len(names) != len(set(names)):
                errors.append("sdist contains duplicate archive member names")
            unsafe = sorted(
                member.name
                for member in members
                if not _safe_archive_name(member.name.rstrip("/"))
            )
            if unsafe:
                errors.append("sdist contains unsafe member paths: " + ", ".join(unsafe))
            special = sorted(
                member.name
                for member in members
                if not (member.isfile() or member.isdir())
            )
            if special:
                errors.append(
                    "sdist must contain only regular files and directories: "
                    + ", ".join(special)
                )

            relative_members: dict[str, tarfile.TarInfo] = {}
            top_levels: set[str] = set()
            for member in members:
                parts = PurePosixPath(member.name.rstrip("/")).parts
                if not parts:
                    continue
                top_levels.add(parts[0])
                if parts[0] != expected_root or len(parts) == 1:
                    continue
                relative = PurePosixPath(*parts[1:]).as_posix()
                relative_members[relative] = member
            if top_levels != {expected_root}:
                errors.append(
                    f"sdist must contain one top-level directory {expected_root!r}, "
                    f"observed {sorted(top_levels)}"
                )

            observed_root_entries = {
                PurePosixPath(relative).parts[0]
                for relative in relative_members
                if PurePosixPath(relative).parts
            }
            if observed_root_entries != expected_root_entries:
                missing = sorted(expected_root_entries - observed_root_entries)
                unexpected = sorted(observed_root_entries - expected_root_entries)
                if missing:
                    errors.append("sdist is missing root entries: " + ", ".join(missing))
                if unexpected:
                    errors.append(
                        "sdist contains unexpected root entries: "
                        + ", ".join(unexpected)
                    )

            observed_package_files = {
                relative
                for relative, member in relative_members.items()
                if member.isfile() and relative.startswith("calm/")
            }
            if observed_package_files != tracked_package_files:
                missing = sorted(tracked_package_files - observed_package_files)
                unexpected = sorted(observed_package_files - tracked_package_files)
                if missing:
                    errors.append(
                        "sdist is missing tracked package files: " + ", ".join(missing)
                    )
                if unexpected:
                    errors.append(
                        "sdist contains unexpected package files: "
                        + ", ".join(unexpected)
                    )

            observed_egg_info_files = {
                relative.split("/", 1)[1]
                for relative, member in relative_members.items()
                if member.isfile() and relative.startswith("calm.egg-info/")
            }
            if observed_egg_info_files != egg_info_files:
                errors.append(
                    "sdist calm.egg-info files must be exactly "
                    f"{sorted(egg_info_files)}, observed "
                    f"{sorted(observed_egg_info_files)}"
                )

            for relative in sorted(source_root_files | tracked_package_files):
                member = relative_members.get(relative)
                source = repo_root / relative
                if member is None or not member.isfile() or not source.is_file():
                    continue
                if _tar_file_bytes(archive, member) != source.read_bytes():
                    errors.append(f"sdist source bytes differ from repository: {relative}")

            pkg_info = relative_members.get("PKG-INFO")
            egg_pkg_info = relative_members.get("calm.egg-info/PKG-INFO")
            if pkg_info is not None and pkg_info.isfile():
                root_metadata = _tar_file_bytes(archive, pkg_info)
                _metadata(
                    root_metadata,
                    label="sdist PKG-INFO",
                    project=project,
                    license_policy=contract.get("license_policy", {}),
                    errors=errors,
                )
                if egg_pkg_info is not None and egg_pkg_info.isfile():
                    if _tar_file_bytes(archive, egg_pkg_info) != root_metadata:
                        errors.append(
                            "sdist root and calm.egg-info PKG-INFO must match"
                        )

            top_level = relative_members.get("calm.egg-info/top_level.txt")
            if top_level is not None and top_level.isfile():
                if _tar_file_bytes(archive, top_level) != b"calm\n":
                    errors.append(
                        "sdist calm.egg-info/top_level.txt must contain exactly "
                        "'calm\\n'"
                    )

            sources = relative_members.get("calm.egg-info/SOURCES.txt")
            if sources is not None and sources.isfile():
                try:
                    source_lines = {
                        line
                        for line in _tar_file_bytes(archive, sources)
                        .decode("utf-8")
                        .splitlines()
                        if line
                    }
                except UnicodeDecodeError as exc:
                    errors.append(f"sdist SOURCES.txt is invalid UTF-8: {exc}")
                else:
                    expected_sources = (
                        source_root_files
                        | tracked_package_files
                        | {
                            f"calm.egg-info/{filename}"
                            for filename in egg_info_files
                        }
                    )
                    if source_lines != expected_sources:
                        errors.append(
                            "sdist SOURCES.txt must exactly describe source and "
                            "egg-info members"
                        )
    except (OSError, tarfile.TarError, KeyError) as exc:
        errors.append(f"could not inspect sdist {path}: {exc}")
        return {"filename": path.name, "file_count": 0}
    file_count = sum(
        1 for member in relative_members.values() if member.isfile()
    )
    return {"filename": path.name, "file_count": file_count}


def _discover_artifacts(
    dist_dir: Path,
    *,
    wheel: Path | None,
    sdist: Path | None,
    errors: list[str],
) -> tuple[Path | None, Path | None]:
    if wheel is not None or sdist is not None:
        if wheel is None or sdist is None:
            errors.append("--wheel and --sdist must be supplied together")
        return wheel, sdist
    if not dist_dir.is_dir():
        errors.append(f"distribution directory does not exist: {dist_dir}")
        return None, None
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1:
        errors.append(
            f"distribution directory must contain exactly one wheel, found {len(wheels)}"
        )
    if len(sdists) != 1:
        errors.append(
            f"distribution directory must contain exactly one sdist, found {len(sdists)}"
        )
    return (
        wheels[0] if len(wheels) == 1 else None,
        sdists[0] if len(sdists) == 1 else None,
    )


def validate(
    *,
    repo_root: Path = REPO_ROOT,
    contract_path: Path | None = None,
    pyproject_path: Path | None = None,
    dist_dir: Path | None = None,
    wheel_path: Path | None = None,
    sdist_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    contract_path = (
        contract_path.resolve()
        if contract_path is not None
        else repo_root
        / "engineering"
        / "architecture"
        / "current-python-distribution.json"
    )
    pyproject_path = (
        pyproject_path.resolve()
        if pyproject_path is not None
        else repo_root / "pyproject.toml"
    )
    dist_dir = dist_dir.resolve() if dist_dir is not None else repo_root / "dist"
    errors: list[str] = []
    contract = _load_contract(contract_path, errors)
    pyproject = _load_project(pyproject_path, errors)
    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    license_policy = (
        contract.get("license_policy", {}) if isinstance(contract, dict) else {}
    )
    expected_expression = license_policy.get("expression")
    if project.get("license") != expected_expression:
        errors.append(
            "project.license must match the distribution license expression"
        )
    expected_license_files = list(license_policy.get("files", {}))
    if project.get("license-files") != expected_license_files:
        errors.append(
            "project.license-files must match the distribution license files"
        )
    source_license_files: dict[str, bytes] = {}
    for filename, expected_digest in license_policy.get("files", {}).items():
        path = repo_root / filename
        if not path.is_file():
            errors.append(f"required repository license file is missing: {filename}")
            continue
        content = path.read_bytes()
        observed_digest = hashlib.sha256(content).hexdigest()
        if observed_digest != expected_digest:
            errors.append(
                f"repository license digest mismatch for {filename}: "
                f"expected {expected_digest}, observed {observed_digest}"
            )
        source_license_files[filename] = content
    sdist_policy = contract.get("sdist", {}) if isinstance(contract, dict) else {}
    expected_manifest = (
        _token_rows(sdist_policy, "manifest_directives", errors)
        if isinstance(sdist_policy, dict)
        else []
    )
    _validate_manifest(
        repo_root / "MANIFEST.in",
        expected=expected_manifest,
        errors=errors,
    )
    wheel_policy = contract.get("wheel", {}) if isinstance(contract, dict) else {}
    package_root = str(wheel_policy.get("package_root", "calm"))
    suffixes = set(wheel_policy.get("package_file_suffixes", ()))
    tracked = _tracked_package_files(
        repo_root, package_root, suffixes, errors
    )
    wheel_path, sdist_path = _discover_artifacts(
        dist_dir,
        wheel=wheel_path.resolve() if wheel_path is not None else None,
        sdist=sdist_path.resolve() if sdist_path is not None else None,
        errors=errors,
    )

    wheel_result: dict[str, Any] | None = None
    sdist_result: dict[str, Any] | None = None
    if wheel_path is not None and wheel_path.is_file():
        wheel_result = _validate_wheel(
            wheel_path,
            project=project,
            contract=contract,
            source_license_files=source_license_files,
            tracked_package_files=tracked,
            errors=errors,
        )
    elif wheel_path is not None:
        errors.append(f"wheel does not exist: {wheel_path}")
    if sdist_path is not None and sdist_path.is_file():
        sdist_result = _validate_sdist(
            sdist_path,
            repo_root=repo_root,
            project=project,
            contract=contract,
            tracked_package_files=tracked,
            errors=errors,
        )
    elif sdist_path is not None:
        errors.append(f"sdist does not exist: {sdist_path}")

    return {
        "schema": _RESULT_SCHEMA,
        "contract_schema": contract.get("schema_version") if contract else None,
        "license_status": (
            contract.get("license_policy", {}).get("status")
            if contract
            else None
        ),
        "license_expression": (
            contract.get("license_policy", {}).get("expression")
            if contract
            else None
        ),
        "sdist": sdist_result,
        "sdist_profile": (
            contract.get("sdist", {}).get("profile") if contract else None
        ),
        "tracked_package_file_count": len(tracked),
        "wheel": wheel_result,
        "wheel_profile": (
            contract.get("wheel", {}).get("profile") if contract else None
        ),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--sdist", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = validate(
        dist_dir=args.dist_dir,
        wheel_path=args.wheel,
        sdist_path=args.sdist,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["errors"]:
        for error in result["errors"]:
            print(f"Python distribution artifact error: {error}", file=sys.stderr)
        return 1
    print(
        "CALM wheel and source distribution match the exact artifact contract."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
