"""Contracts for the canonical greenfield tutorial programs."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
TUTORIAL_ROOT = ROOT / "examples" / "tutorials"
EXPECTED_ROOT = TUTORIAL_ROOT / "expected"
SCRIPTS = {
    "first-interface": TUTORIAL_ROOT / "first_interface.py",
    "compare-candidates": TUTORIAL_ROOT / "compare_candidates.py",
    "refine-relax-evaluate": TUTORIAL_ROOT / "refine_relax_evaluate.py",
}
RUN_CALCULATOR_TUTORIAL = (
    os.environ.get("CALM_RUN_CALCULATOR_TUTORIAL") == "1"
)


def _expectation(name: str) -> dict[str, object]:
    return json.loads(
        (EXPECTED_ROOT / f"{name}.json").read_text(encoding="utf-8")
    )


def _run(script: Path, work_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(ROOT), env.get("PYTHONPATH")))
    )
    env.setdefault("MPLBACKEND", "Agg")
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--work-dir",
            str(work_dir),
            "--reset",
        ],
        cwd=work_dir.parent,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        check=False,
    )


def _require_science_environment() -> None:
    for module in ("ase", "spglib", "scipy", "sqlalchemy"):
        if importlib.util.find_spec(module) is None:
            pytest.skip(f"greenfield tutorial execution requires {module}")


def _assert_summary(name: str, work_dir: Path) -> dict[str, object]:
    summary_path = work_dir / "outputs" / "run-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected = _expectation(name)
    assert summary["schema_version"] == "calm.tutorial_run.v1"
    assert summary["tutorial"] == name
    assert summary["structures"] == expected["structures"]
    assert summary["calculator_required"] is expected["calculator_required"]
    artifacts = set(summary["artifacts"])
    assert set(expected["required_artifacts"]).issubset(artifacts)
    required_stage = expected.get("required_interface_stage")
    if required_stage is not None:
        assert summary["interface_stage"] == required_stage
    return summary


def test_greenfield_tutorial_inventory_and_expectations_are_exact() -> None:
    scripts = {
        path.name
        for path in TUTORIAL_ROOT.glob("*.py")
        if not path.name.startswith("_")
    }
    assert scripts == {
        "first_interface.py",
        "compare_candidates.py",
        "refine_relax_evaluate.py",
    }
    fixtures = {path.stem for path in EXPECTED_ROOT.glob("*.json")}
    assert fixtures == set(SCRIPTS)
    for name in SCRIPTS:
        expected = _expectation(name)
        assert expected["schema_version"] == "calm.tutorial_expectation.v1"
        assert expected["tutorial"] == name


def test_tutorial_sources_use_only_the_top_level_calm_api() -> None:
    for name, path in SCRIPTS.items():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        imports = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        for node in imports:
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("calm."), (name, node.module)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("calm."), (name, alias.name)
        assert "from calm import" in text
        assert "tutorial_structure" in text
        assert "examples/Structures" not in text
        assert "EXAMPLES_DIR" not in text
        assert "Material.from_file" not in text


def test_first_interface_reads_identity_from_the_saved_project_record() -> None:
    text = SCRIPTS["first-interface"].read_text(encoding="utf-8")
    assert 'saved_interface = project.interface(f"{INTERFACE_PREFIX}_0000")' in text
    assert '"interface": saved_interface.label' in text
    assert '"interface_stage": saved_interface.stage' in text
    assert "interface = interfaces.get(" not in text


def test_each_tutorial_is_independently_runnable_by_contract() -> None:
    first = SCRIPTS["first-interface"].read_text(encoding="utf-8")
    compare = SCRIPTS["compare-candidates"].read_text(encoding="utf-8")
    advanced = SCRIPTS["refine-relax-evaluate"].read_text(encoding="utf-8")

    for text in (first, compare, advanced):
        assert 'parser.add_argument(\n        "--work-dir"' in text
        assert 'parser.add_argument("--reset"' in text or '"--reset",' in text
        assert "prepare_directory(work_dir, reset=reset)" in text
        assert "write_run_summary(" in text
    assert "does not depend on the first" in compare
    assert 'Potential(family="ase", model="EMT")' in advanced
    assert "workflow mechanics and reference bookkeeping" in advanced


def test_first_interface_tutorial_executes_without_calculator(tmp_path: Path) -> None:
    _require_science_environment()
    work_dir = tmp_path / "first"
    result = _run(SCRIPTS["first-interface"], work_dir)
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    summary = _assert_summary("first-interface", work_dir)
    assert summary["interface_stage"] == "built"
    assert int(summary["candidate_count"]) >= 1


def test_compare_candidates_tutorial_executes_independently(tmp_path: Path) -> None:
    _require_science_environment()
    work_dir = tmp_path / "compare"
    result = _run(SCRIPTS["compare-candidates"], work_dir)
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    summary = _assert_summary("compare-candidates", work_dir)
    assert int(summary["candidate_count"]) >= int(summary["pareto_count"]) >= 1
    assert int(summary["shortlist_count"]) >= 1


@pytest.mark.real_backend
@pytest.mark.skipif(
    not RUN_CALCULATOR_TUTORIAL,
    reason=(
        "The ASE EMT tutorial is opt-in. Set "
        "CALM_RUN_CALCULATOR_TUTORIAL=1 to execute it."
    ),
)
def test_refine_relax_evaluate_tutorial_executes(tmp_path: Path) -> None:
    _require_science_environment()
    work_dir = tmp_path / "advanced"
    result = _run(SCRIPTS["refine-relax-evaluate"], work_dir)
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    summary = _assert_summary("refine-relax-evaluate", work_dir)
    assert summary["calculator"] == "ase:EMT"
    assert summary["reference_convention"] == (
        "work_of_adhesion_relaxed_surfaces"
    )
    assert summary["refinement_ok"] is True
    assert int(summary["relaxation_results"]) >= 1
    assert int(summary["raw_energy_results"]) >= 1
    assert int(summary["thermodynamic_results"]) >= 1


def test_canonical_tutorial_work_directories_live_under_examples() -> None:
    support = (TUTORIAL_ROOT / "_support.py").read_text(encoding="utf-8")
    assert 'WORK_ROOT = EXAMPLES_ROOT / "work"' in support
    expected_defaults = {
        "first-interface": 'default_work_dir("first-interface")',
        "compare-candidates": 'default_work_dir("compare-candidates")',
        "refine-relax-evaluate": 'default_work_dir("refine-relax-evaluate")',
    }
    for name, marker in expected_defaults.items():
        assert marker in SCRIPTS[name].read_text(encoding="utf-8")

    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "docs" / "learn").glob("*.md")
    )
    public_text += (ROOT / "README.md").read_text(encoding="utf-8")
    public_text += (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    for name in expected_defaults:
        assert f"--work-dir examples/work/{name}" in public_text
    assert "--work-dir calm-first-interface" not in public_text
    assert "--work-dir calm-compare-candidates" not in public_text
    assert "--work-dir calm-refine-relax-evaluate" not in public_text
    assert "work/" in (ROOT / "examples" / ".gitignore").read_text(encoding="utf-8")
