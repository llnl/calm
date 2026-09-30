"""Contracts for the ten sequential examples."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"
EXPECTED_SCRIPTS = (
    "01_optimize_materials.py",
    "02_generate_surfaces.py",
    "03_search_interfaces.py",
    "04_compare_interface_searches.py",
    "05_build_interfaces.py",
    "06_refine_interfaces.py",
    "07_relax_interfaces.py",
    "08_evaluate_interface_energetics.py",
    "09_build_interface_dataset.py",
    "10_run_interface_campaign.py",
)

RUN_NUMBERED_EXAMPLES = os.environ.get("CALM_RUN_NUMBERED_EXAMPLES") == "1"


def _scripts() -> list[Path]:
    return [EXAMPLES_DIR / name for name in EXPECTED_SCRIPTS]


def _stage_workflow(tmp_path: Path) -> Path:
    staged = tmp_path / "examples"
    staged.mkdir()
    for script in _scripts():
        shutil.copy2(script, staged / script.name)
    shutil.copytree(EXAMPLES_DIR / "Structures", staged / "Structures")
    return staged


def _run(
    script: Path,
    cwd: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    pythonpath = [str(REPO_ROOT)]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env.setdefault("MPLBACKEND", "Agg")
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=600,
        check=False,
    )


def test_example_inventory_is_exact() -> None:
    shipped = tuple(path.name for path in sorted(EXAMPLES_DIR.glob("[0-9][0-9]_*.py")))
    assert shipped == EXPECTED_SCRIPTS


def test_numbered_examples_share_project_and_output_paths() -> None:
    for script in _scripts():
        text = script.read_text(encoding="utf-8")
        assert 'EXAMPLES_DIR = Path(__file__).resolve().parent' in text
        assert 'PROJECT_DIR = EXAMPLES_DIR / "example_project.calm"' in text
        assert 'OUTPUT_DIR = EXAMPLES_DIR / "outputs"' in text
        assert "--out-dir" not in text
        assert ' / "outputs" / ' not in text


def test_examples_select_the_catalogued_li2o_100_oxygen_facing_surface() -> None:
    expected = 'termination_bottom="O",\n        termination_shift=1,'
    for name in (
        "02_generate_surfaces.py",
        "03_search_interfaces.py",
        "04_compare_interface_searches.py",
    ):
        text = (EXAMPLES_DIR / name).read_text(encoding="utf-8")
        assert expected in text, (
            f"{name} must select the Li2O(100) slab whose bottom face is O"
        )
        assert (
            'termination_bottom="O",\n        termination_shift=0,'
            not in text
        )


def test_interface_examples_use_collection_owned_construction_view() -> None:
    text = (EXAMPLES_DIR / "05_build_interfaces.py").read_text(encoding="utf-8")
    marker = 'OUTPUT_DIR / "05_built_interfaces.csv",'
    assert marker in text
    assert 'view="construction"' in text
    assert 'view="all"' not in text[text.index(marker) :]
    assert 'exclude=("calculator",)' not in text
    assert "include=" not in text


def test_material_characterization_example_uses_collection_owned_view() -> None:
    text = (EXAMPLES_DIR / "01_optimize_materials.py").read_text(encoding="utf-8")

    assert "MATERIAL_CHARACTERIZATION_COLUMNS" not in text
    assert 'view="characterization"' in text
    assert text.count('view="characterization"') == 2
    assert "include=" not in text[text.index('view="characterization"') :]


def test_interface_candidate_example_uses_collection_owned_summary_view() -> None:
    text = (EXAMPLES_DIR / "03_search_interfaces.py").read_text(encoding="utf-8")

    assert "CANDIDATE_SUMMARY_COLUMNS" not in text
    assert 'candidates.to_table(title="Candidates").display()' in text
    assert "candidates.write_table(all_csv)" in text
    assert "low_strain.write_table(low_csv)" in text
    assert "include=" not in text
    assert 'table="candidates"' not in text


def test_interface_search_example_uses_discrete_pareto_staircase() -> None:
    text = (EXAMPLES_DIR / "03_search_interfaces.py").read_text(encoding="utf-8")

    assert text.count('front_style="step"') == 1
    assert text.count("front_plot_style=None") == 1


def test_build_interface_example_uses_candidate_summary_view() -> None:
    text = (EXAMPLES_DIR / "05_build_interfaces.py").read_text(encoding="utf-8")

    assert "BUILD_CANDIDATE_COLUMNS" not in text
    assert "BUILD_TOP = 3" in text
    assert (
        'sel = candidates.select(pareto=True).select_top(BUILD_TOP, by="score")'
        in text
    )
    assert "sel.to_table(" in text
    assert 'title="Pareto candidates selected for construction"' in text
    assert "include=" not in text
    assert "top=BUILD_TOP" in text
    assert 'table="candidates"' not in text
    assert "max_width=" not in text



def test_numbered_examples_do_not_use_retired_table_selector() -> None:
    for path in sorted(EXAMPLES_DIR.glob("[0-9][0-9]_*.py")):
        assert "table=" not in path.read_text(encoding="utf-8"), path.name

def test_interface_search_comparison_uses_local_and_global_step_envelopes() -> None:
    text = (EXAMPLES_DIR / "04_compare_interface_searches.py").read_text(
        encoding="utf-8"
    )

    assert text.count('front_style="step"') == 4
    assert text.count("front_plot_style=None") == 4
    assert text.count('front_scope="both"') == 2
    assert 'front_scope="global"' not in text


def test_surface_characterization_example_uses_collection_owned_view() -> None:
    text = (EXAMPLES_DIR / "02_generate_surfaces.py").read_text(encoding="utf-8")

    assert "SURFACE_CHARACTERIZATION_COLUMNS" not in text
    assert text.count('view="characterization"') == 2
    characterization_calls = text[text.index('view="characterization"') :]
    assert "include=" not in characterization_calls
    assert "bulk_composition_compatible" not in text
    assert "excess_composition" not in text
    assert "vacuum_A" not in text


def test_interface_examples_export_composed_strain_diagnostics() -> None:
    example_05 = (EXAMPLES_DIR / "05_build_interfaces.py").read_text(
        encoding="utf-8"
    )
    example_07 = (EXAMPLES_DIR / "07_relax_interfaces.py").read_text(
        encoding="utf-8"
    )

    assert 'OUTPUT_DIR / "05_built_interface_strain.csv"' in example_05
    assert 'OUTPUT_DIR / "07_relaxed_interface_strain.csv"' in example_07
    assert example_05.count('view="strain"') == 1
    assert example_07.count('view="strain"') == 1


def test_followup_examples_use_result_owned_summary_views() -> None:
    example_06 = (EXAMPLES_DIR / "06_refine_interfaces.py").read_text(
        encoding="utf-8"
    )
    example_07 = (EXAMPLES_DIR / "07_relax_interfaces.py").read_text(
        encoding="utf-8"
    )
    example_08 = (EXAMPLES_DIR / "08_evaluate_interface_energetics.py").read_text(
        encoding="utf-8"
    )

    assert 'filename_prefix="06_"' in example_06
    assert 'view="all"' not in example_07
    assert 'view="all"' not in example_08
    assert "workflow.write_table(" in example_07
    assert "reference_workflow.write_table(" in example_08
    assert example_08.count("workflow.write_table(") == 3


@pytest.mark.real_backend
@pytest.mark.skipif(
    not RUN_NUMBERED_EXAMPLES,
    reason=(
        "The sequential numbered examples require a real MLIP backend. Set "
        "CALM_RUN_NUMBERED_EXAMPLES=1 to execute them."
    ),
)
def test_top_level_examples_run_sequentially(tmp_path: Path) -> None:
    staged = _stage_workflow(tmp_path)

    for name in EXPECTED_SCRIPTS:
        script = staged / name
        result = _run(script, tmp_path)
        assert result.returncode == 0, (
            f"example failed: {name}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    assert (staged / "example_project.calm").is_dir()
    assert (staged / "outputs").is_dir()
