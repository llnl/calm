"""Construct one calculator-free LiF/Li2O coherent interface.

Run from any working directory:

    python examples/tutorials/first_interface.py \
        --work-dir examples/work/first-interface --reset
"""

from __future__ import annotations

import argparse
from pathlib import Path

# --8<-- [start:first-interface-imports]
from calm import (
    BuildSettings,
    Material,
    SearchSettings,
    open_project,
    tutorial_structure,
)
# --8<-- [end:first-interface-imports]

from _support import (
    default_work_dir,
    expectation,
    prepare_directory,
    write_run_summary,
)

SEARCH_NAME = "lif-li2o-100"
INTERFACE_PREFIX = "first-interface"


def run(work_dir: Path, *, reset: bool = False) -> dict[str, object]:
    root = prepare_directory(work_dir, reset=reset)
    project_dir = root / "first-interface.calm"
    output_dir = root / "outputs"

    # --8<-- [start:first-interface-materials-surfaces]
    project = open_project(project_dir)
    project.add_material(
        Material.from_ase(tutorial_structure("lif"), name="LiF"),
        name="LiF",
    )
    project.add_material(
        Material.from_ase(tutorial_structure("li2o"), name="Li2O"),
        name="Li2O",
    )

    project.generate_surfaces(
        ["LiF", "Li2O"],
        millers=[(1, 0, 0)],
        layers=4,
        vacuum=15.0,
    )
    lif_surface = project.surface(
        material="LiF",
        miller=(1, 0, 0),
        termination="LiF",
        termination_shift=0,
    )
    li2o_surface = project.surface(
        material="Li2O",
        miller=(1, 0, 0),
        termination_bottom="O",
        termination_shift=1,
    )
    # --8<-- [end:first-interface-materials-surfaces]

    # --8<-- [start:first-interface-search]
    search = project.search_interfaces(
        lif_surface,
        li2o_surface,
        settings=SearchSettings(
            max_principal_strain=0.15,
            max_supercell_index=12,
            max_atoms=1000,
            max_candidates=500,
            mismatch_weight=0.5,
        ),
        name=SEARCH_NAME,
    )
    if search.empty:
        raise RuntimeError(search.explain())
    readiness = search.buildability_summary()
    if not readiness.ok:
        raise RuntimeError(readiness.explain())
    # --8<-- [end:first-interface-search]

    # --8<-- [start:first-interface-build-export]
    interfaces = project.build_interfaces(
        search,
        top=1,
        settings=BuildSettings(
            strain_partition="both",
            alpha=0.5,
            gap=1.5,
            vacuum=15.0,
            translation=(0.0, 0.0),
        ),
        name_prefix=INTERFACE_PREFIX,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    interfaces.write_structures(output_dir, format="vasp")
    interfaces.write_table(output_dir / "interfaces.csv", view="construction")
    # --8<-- [end:first-interface-build-export]

    saved_interface = project.interface(f"{INTERFACE_PREFIX}_0000")
    summary: dict[str, object] = {
        "schema_version": "calm.tutorial_run.v1",
        "tutorial": "first-interface",
        "calculator_required": False,
        "structures": ["lif", "li2o"],
        "project": project_dir.name,
        "search": SEARCH_NAME,
        "candidate_count": len(search.candidates()),
        "interface": saved_interface.label,
        "interface_stage": saved_interface.stage,
        "artifacts": sorted(
            {path.name for path in output_dir.iterdir()} | {"run-summary.json"}
        ),
    }
    write_run_summary(output_dir, summary)

    expected = expectation("first-interface")
    print(f"[tutorial] outcome: {expected['outcome']}")
    print(f"[tutorial] project: {project_dir}")
    print(f"[tutorial] search candidates: {summary['candidate_count']}")
    print(
        f"[tutorial] interface: {summary['interface']} "
        f"({summary['interface_stage']})"
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=default_work_dir("first-interface"),
        help="directory in which CALM creates the tutorial project and outputs",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="replace an existing tutorial output directory",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run(args.work_dir, reset=args.reset)


if __name__ == "__main__":
    main()
