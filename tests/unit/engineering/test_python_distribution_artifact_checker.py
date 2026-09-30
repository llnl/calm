"""Dependency-light mutation tests for Python distribution artifacts."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile

from engineering.qualification import check_python_distribution_artifacts as checker


ROOT = Path(__file__).resolve().parents[3]
CONTRACT = (
    ROOT / "engineering" / "architecture" / "current-python-distribution.json"
)
_METADATA = (
    "Metadata-Version: 2.4\n"
    "Name: calm\n"
    "Version: 0.1.0b1\n"
    "Summary: test artifact\n"
    "Requires-Python: <3.13,>=3.10\n"
    "License-Expression: MIT\n"
    "License-File: LICENSE\n"
    "License-File: NOTICE\n"
    "\n"
    "test artifact\n"
).encode()
_WHEEL = (
    "Wheel-Version: 1.0\n"
    "Generator: test\n"
    "Root-Is-Purelib: true\n"
    "Tag: py3-none-any\n"
    "\n"
).encode()


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "calm").mkdir(parents=True)
    (root / "engineering" / "architecture").mkdir(parents=True)
    (root / "calm" / "__init__.py").write_text(
        '__version__ = "0.1.0b1"\n', encoding="utf-8"
    )
    (root / "README.md").write_text("# CALM\n", encoding="utf-8")
    for filename in ("LICENSE", "NOTICE"):
        shutil.copy2(ROOT / filename, root / filename)
    (root / "MANIFEST.in").write_text(
        "include LICENSE\n"
        "include NOTICE\n"
        "include README.md\n"
        "prune tests\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["setuptools>=77", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        "[project]\n"
        'name = "calm"\n'
        'version = "0.1.0b1"\n'
        'requires-python = ">=3.10,<3.13"\n'
        'license = "MIT"\n'
        'license-files = ["LICENSE", "NOTICE"]\n\n'
        "[tool.setuptools]\n"
        "include-package-data = false\n",
        encoding="utf-8",
    )
    contract = root / "engineering" / "architecture" / CONTRACT.name
    contract.write_text(CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "add",
            "MANIFEST.in",
            "LICENSE",
            "NOTICE",
            "README.md",
            "pyproject.toml",
            "calm",
            "engineering/architecture",
        ],
        check=True,
    )
    return root, contract


def _record(members: dict[str, bytes], record_path: str) -> bytes:
    rows: list[list[str]] = []
    for name, content in sorted(members.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest())
        encoded = digest.rstrip(b"=").decode("ascii")
        rows.append([name, f"sha256={encoded}", str(len(content))])
    rows.append([record_path, "", ""])
    stream = io.StringIO(newline="")
    csv.writer(stream, lineterminator="\n").writerows(rows)
    return stream.getvalue().encode()


def _wheel(
    root: Path,
    *,
    metadata: bytes = _METADATA,
    extras: dict[str, bytes] | None = None,
    omit_package: bool = False,
) -> Path:
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    path = dist / "calm-0.1.0b1-py3-none-any.whl"
    dist_info = "calm-0.1.0b1.dist-info"
    members = {
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": _WHEEL,
        f"{dist_info}/licenses/LICENSE": (root / "LICENSE").read_bytes(),
        f"{dist_info}/licenses/NOTICE": (root / "NOTICE").read_bytes(),
        f"{dist_info}/top_level.txt": b"calm\n",
    }
    if not omit_package:
        members["calm/__init__.py"] = (root / "calm" / "__init__.py").read_bytes()
    members.update(extras or {})
    record_path = f"{dist_info}/RECORD"
    members[record_path] = _record(members, record_path)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return path


def _sdist(
    root: Path,
    *,
    metadata: bytes = _METADATA,
    extras: dict[str, bytes] | None = None,
    package_content: bytes | None = None,
) -> Path:
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    path = dist / "calm-0.1.0b1.tar.gz"
    prefix = "calm-0.1.0b1"
    package = (
        (root / "calm" / "__init__.py").read_bytes()
        if package_content is None
        else package_content
    )
    egg_info_files = {
        "PKG-INFO": metadata,
        "dependency_links.txt": b"",
        "not-zip-safe": b"",
        "requires.txt": b"",
        "top_level.txt": b"calm\n",
    }
    source_lines = {
        "MANIFEST.in",
        "LICENSE",
        "NOTICE",
        "README.md",
        "pyproject.toml",
        "calm/__init__.py",
        *{f"calm.egg-info/{name}" for name in (*egg_info_files, "SOURCES.txt")},
    }
    egg_info_files["SOURCES.txt"] = (
        "\n".join(sorted(source_lines)) + "\n"
    ).encode()
    files = {
        "MANIFEST.in": (root / "MANIFEST.in").read_bytes(),
        "LICENSE": (root / "LICENSE").read_bytes(),
        "NOTICE": (root / "NOTICE").read_bytes(),
        "PKG-INFO": metadata,
        "README.md": (root / "README.md").read_bytes(),
        "calm/__init__.py": package,
        "pyproject.toml": (root / "pyproject.toml").read_bytes(),
        "setup.cfg": b"[egg_info]\ntag_build =\ntag_date = 0\n",
        **{
            f"calm.egg-info/{name}": content
            for name, content in egg_info_files.items()
        },
    }
    files.update(extras or {})
    with tarfile.open(path, mode="w:gz") as archive:
        for relative, content in sorted(files.items()):
            info = tarfile.TarInfo(f"{prefix}/{relative}")
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    return path


def _validate(root: Path, contract: Path, wheel: Path, sdist: Path) -> dict:
    return checker.validate(
        repo_root=root,
        contract_path=contract,
        pyproject_path=root / "pyproject.toml",
        wheel_path=wheel,
        sdist_path=sdist,
    )


def test_exact_minimal_artifacts_are_accepted(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    result = _validate(root, contract, _wheel(root), _sdist(root))

    assert result["errors"] == []
    assert result["tracked_package_file_count"] == 1
    assert result["wheel"]["file_count"] == 7
    assert result["sdist_profile"] == "minimal_installation_source"


def test_manifest_drift_is_rejected_before_artifact_admission(
    tmp_path: Path,
) -> None:
    root, contract = _repository(tmp_path)
    (root / "MANIFEST.in").write_text("include README.md\n", encoding="utf-8")
    result = _validate(root, contract, _wheel(root), _sdist(root))

    assert any(
        error.startswith(
            "MANIFEST.in directives must exactly match the distribution contract"
        )
        for error in result["errors"]
    )


def test_wheel_rejects_repository_only_content(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    wheel = _wheel(root, extras={"tests/test_leak.py": b""})
    result = _validate(root, contract, wheel, _sdist(root))

    assert any(
        error == "wheel contains unexpected files: tests/test_leak.py"
        for error in result["errors"]
    )


def test_sdist_rejects_repository_snapshot_content(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    sdist = _sdist(root, extras={"docs/index.md": b"# leaked\n"})
    result = _validate(root, contract, _wheel(root), sdist)

    assert any(
        error == "sdist contains unexpected root entries: docs"
        for error in result["errors"]
    )


def test_artifacts_reject_license_expression_drift(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    metadata = _METADATA.replace(
        b"License-Expression: MIT\n",
        b"License-Expression: Apache-2.0\n",
    )
    result = _validate(
        root,
        contract,
        _wheel(root, metadata=metadata),
        _sdist(root, metadata=metadata),
    )

    assert any(
        "wheel METADATA License-Expression must be exactly 'MIT'" in error
        for error in result["errors"]
    )
    assert any(
        "sdist PKG-INFO License-Expression must be exactly 'MIT'" in error
        for error in result["errors"]
    )


def test_wheel_rejects_license_bytes_not_from_the_repository(
    tmp_path: Path,
) -> None:
    root, contract = _repository(tmp_path)
    wheel = _wheel(
        root,
        extras={"calm-0.1.0b1.dist-info/licenses/LICENSE": b"tampered\n"},
    )

    result = _validate(root, contract, wheel, _sdist(root))

    assert "wheel license bytes differ from repository: LICENSE" in result["errors"]


def test_sdist_rejects_package_bytes_not_from_the_repository(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    result = _validate(
        root,
        contract,
        _wheel(root),
        _sdist(root, package_content=b"tampered = True\n"),
    )

    assert "sdist source bytes differ from repository: calm/__init__.py" in result["errors"]


def test_wheel_rejects_missing_tracked_package_source(tmp_path: Path) -> None:
    root, contract = _repository(tmp_path)
    result = _validate(
        root,
        contract,
        _wheel(root, omit_package=True),
        _sdist(root),
    )

    assert "wheel is missing required files: calm/__init__.py" in result["errors"]
