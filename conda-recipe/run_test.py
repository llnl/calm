"""Installed-package checks executed automatically by conda-build.

The script intentionally avoids ``__future__`` imports because conda-build
may compose generated import checks into its temporary copy before execution.
"""

from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from typing import Any, Mapping


EXPECTED_NAME = "calm"
EXPECTED_BUILD_NUMBER = 0
EXPECTED_SUBDIR = "noarch"
EXPECTED_DEPENDENCIES = {"numpy", "python", "sqlalchemy"}
_DEPENDENCY_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_DIST_INFO_RE = re.compile(r"^calm-[^/]+\.dist-info/")


def _dependency_name(specification: str) -> str:
    match = _DEPENDENCY_RE.match(specification)
    if match is None:
        raise AssertionError(f"invalid conda dependency: {specification!r}")
    return match.group(1).lower().replace("_", "-")


def _site_packages_tail(relative: str) -> str | None:
    parts = PurePosixPath(relative.replace("\\", "/")).parts
    for marker in ("site-packages", "dist-packages"):
        if marker in parts:
            index = parts.index(marker) + 1
            if index < len(parts):
                return PurePosixPath(*parts[index:]).as_posix()
    return None


def _record_projection(record: Mapping[str, Any]) -> dict[str, object]:
    assert record.get("name") == EXPECTED_NAME, record.get("name")
    package_version = record.get("version")
    assert isinstance(package_version, str) and package_version, package_version
    assert (
        record.get("build_number") == EXPECTED_BUILD_NUMBER
    ), record.get("build_number")
    assert record.get("subdir") == EXPECTED_SUBDIR, record.get("subdir")

    dependencies = record.get("depends")
    assert isinstance(dependencies, list) and all(
        isinstance(item, str) for item in dependencies
    ), dependencies
    dependency_names = {_dependency_name(item) for item in dependencies}
    assert dependency_names == EXPECTED_DEPENDENCIES, sorted(dependency_names)

    files = record.get("files")
    assert isinstance(files, list) and all(isinstance(item, str) for item in files)
    installed = sorted(
        tail
        for item in files
        if (tail := _site_packages_tail(item)) is not None
    )
    assert "calm/__init__.py" in installed, installed[:20]
    foreign = [
        item
        for item in installed
        if not item.startswith("calm/") and _DIST_INFO_RE.match(item) is None
    ]
    assert foreign == [], foreign
    non_python_package_files = [
        item
        for item in installed
        if item.startswith("calm/")
        and not item.endswith(".py")
        and not (
            "__pycache__" in PurePosixPath(item).parts
            and item.endswith(".pyc")
        )
    ]
    assert non_python_package_files == [], non_python_package_files
    forbidden = [
        item
        for item in installed
        if item.startswith(("tests/", "docs/", "examples/", "engineering/"))
    ]
    assert forbidden == [], forbidden
    return {
        "dependency_names": sorted(dependency_names),
        "installed_site_package_files": installed,
        "package_version": package_version,
    }


def _load_conda_record(prefix: Path) -> Mapping[str, Any]:
    records: list[Mapping[str, Any]] = []
    for path in sorted((prefix / "conda-meta").glob(f"{EXPECTED_NAME}-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("name") == EXPECTED_NAME:
            records.append(payload)
    assert len(records) == 1, f"expected one CALM conda record, observed {len(records)}"
    return records[0]


def main() -> None:
    prefix_text = os.environ.get("PREFIX") or os.environ.get("CONDA_PREFIX")
    assert prefix_text, "conda test environment did not define PREFIX"
    prefix = Path(prefix_text).resolve()

    record = _load_conda_record(prefix)
    projection = _record_projection(record)
    package_version = projection["package_version"]

    import calm

    assert calm.__version__ == package_version, calm.__version__
    assert metadata.version(EXPECTED_NAME) == package_version
    module_path = Path(calm.__file__).resolve()
    try:
        module_path.relative_to(prefix)
    except ValueError as exc:
        raise AssertionError(
            f"CALM imported outside the conda test prefix: {module_path}"
        ) from exc
    assert callable(calm.open_project)

    with TemporaryDirectory(prefix="calm-conda-smoke-") as temporary:
        project = calm.open_project(
            Path(temporary) / "package_test.calm",
            summarize=False,
        )
        assert project.path is not None


if __name__ == "__main__":
    main()
