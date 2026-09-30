"""Compare LiF/Li2O candidates without requiring a calculator.

The program creates its own project and therefore does not depend on the first
interface tutorial having been run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from calm import Material, SearchSettings, open_project, tutorial_structure

from _support import (
    default_work_dir,
    expectation,
    prepare_directory,
    write_run_summary,
)

SEARCH_NAME = "lif-li2o-candidate-comparison"


def run(
    work_dir: Path,
    *,
    reset: bool = False,
    plot: bool = False,
) -> dict[str, object]:
    root = prepare_directory(work_dir, reset=reset)
    project_dir = root / "compare-candidates.calm"
    output_dir = root / "outputs"

    project = open_project(project_dir)
    project.add_material(Material.from_ase(tutorial_structure("lif"), name="LiF"))
    project.add_material(Material.from_ase(tutorial_structure("li2o"), name="Li2O"))
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
    # --8<-- [start:compare-candidates-search]
    search = project.search_interfaces(
        lif_surface,
        li2o_surface,
        settings=SearchSettings(
            max_principal_strain=0.15,
            max_supercell_index=20,
            max_atoms=1500,
            max_candidates=1000,
            mismatch_weight=0.5,
        ),
        name=SEARCH_NAME,
    )
    if search.empty:
        raise RuntimeError(search.explain())
    # --8<-- [end:compare-candidates-search]

    # --8<-- [start:compare-candidates-select]
    candidates = search.candidates()
    pareto = candidates.select(pareto=True)
    shortlist = pareto.where(
        max_principal_strain=(None, 0.08),
    ).select_top(5, by="score")
    if len(shortlist) == 0:
        shortlist = pareto.select_top(5, by="score")
    # --8<-- [end:compare-candidates-select]

    # --8<-- [start:compare-candidates-export]
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates.write_table(output_dir / "candidates-all.csv")
    pareto.write_table(output_dir / "candidates-pareto.csv")
    shortlist.write_table(output_dir / "candidates-shortlist.csv")
    if plot:
        candidates.plot_pareto(
            x="n_atoms_estimate",
            y="d_cell",
            front_style="step",
            front_plot_style=None,
            save=output_dir / "candidate-pareto.png",
        )
    # --8<-- [end:compare-candidates-export]

    selected = shortlist.records()[0]
    summary: dict[str, object] = {
        "schema_version": "calm.tutorial_run.v1",
        "tutorial": "compare-candidates",
        "calculator_required": False,
        "structures": ["lif", "li2o"],
        "project": project_dir.name,
        "search": SEARCH_NAME,
        "candidate_count": len(candidates),
        "pareto_count": len(pareto),
        "shortlist_count": len(shortlist),
        "selected_candidate": selected.id_short,
        "artifacts": sorted(
            {path.name for path in output_dir.iterdir()} | {"run-summary.json"}
        ),
    }
    write_run_summary(output_dir, summary)

    expected = expectation("compare-candidates")
    print(f"[tutorial] outcome: {expected['outcome']}")
    print(f"[tutorial] candidates: {len(candidates)}")
    print(f"[tutorial] Pareto candidates: {len(pareto)}")
    print(f"[tutorial] shortlist: {len(shortlist)}")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=default_work_dir("compare-candidates"),
    )
    parser.add_argument("--reset", action="store_true")
    parser.add_argument(
        "--plot",
        action="store_true",
        help="write a Pareto plot; requires the plotting extra",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run(args.work_dir, reset=args.reset, plot=args.plot)


if __name__ == "__main__":
    main()
