"""Executable closeout contracts for CALM's reviewed package organization."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "engineering" / "qualification" / "check_package_organization.py"
CONTRACT = ROOT / "engineering" / "architecture" / "current-package-ownership.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_reviewed_package_organization_is_consistent() -> None:
    completed = _run()
    assert completed.returncode == 0, completed.stderr
    assert "Package organization verified" in completed.stdout


def test_package_ownership_contract_has_one_reviewed_topology() -> None:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "calm.package_ownership.v2"
    assert payload["package_root_files"] == [
        "__init__.py",
        "_version.py",
        "api.py",
        "exceptions.py",
    ]
    assert set(payload["top_level_packages"]) == {
        "analysis",
        "bulk",
        "calculators",
        "interface",
        "keys",
        "math2d",
        "project",
        "public",
        "serialization",
        "slab",
        "structure",
        "symmetry",
        "viz",
    }
    assert "public" not in payload["top_level_packages"]["project"][
        "allowed_calm_import_roots"
    ]
    for package in (
        "analysis",
        "bulk",
        "calculators",
        "interface",
        "keys",
        "math2d",
        "serialization",
        "slab",
        "structure",
        "symmetry",
        "viz",
    ):
        allowed = payload["top_level_packages"][package][
            "allowed_calm_import_roots"
        ]
        assert "project" not in allowed
        assert "public" not in allowed

    retirement = payload["retirement"]
    assert set(retirement) == {
        "additional_prohibited_import_prefixes",
        "retired_attributes",
        "retired_files",
        "retired_modules",
        "retired_source_symbols",
        "retired_source_trees",
        "runtime_import_probes",
    }
    prohibited = set(retirement["retired_modules"]) | set(
        retirement["additional_prohibited_import_prefixes"]
    )
    assert set(retirement["runtime_import_probes"]) <= prohibited
    assert set(retirement["retired_modules"]).isdisjoint(
        retirement["additional_prohibited_import_prefixes"]
    )


def test_package_organization_projection_is_machine_readable() -> None:
    completed = _run("--show-current")
    assert completed.returncode == 0, completed.stderr
    projection = json.loads(completed.stdout)
    assert projection["schema_version"] == "calm.package_ownership.v2"
    assert projection["package_root_files"] == [
        "__init__.py",
        "_version.py",
        "api.py",
        "exceptions.py",
    ]
    assert len(projection["top_level_packages"]) == 13

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    retirement = contract["retirement"]
    prohibited = set(retirement["retired_modules"]) | set(
        retirement["additional_prohibited_import_prefixes"]
    )
    assert projection["retirement"] == {
        "additional_prohibited_import_prefix_count": len(
            retirement["additional_prohibited_import_prefixes"]
        ),
        "prohibited_import_prefix_count": len(prohibited),
        "retired_attribute_count": sum(
            len(values) for values in retirement["retired_attributes"].values()
        ),
        "retired_file_count": len(retirement["retired_files"]),
        "retired_module_count": len(retirement["retired_modules"]),
        "retired_source_symbol_count": sum(
            len(values)
            for values in retirement["retired_source_symbols"].values()
        ),
        "retired_source_tree_count": len(retirement["retired_source_trees"]),
        "runtime_import_probe_count": len(retirement["runtime_import_probes"]),
    }
