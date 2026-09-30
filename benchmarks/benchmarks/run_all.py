"""benchmarks.run_all

One-command benchmark runner: executes production coupled CALM and pymatgen ZSL benchmarks and
generates plots and diagnostics.

Usage
-----
python -m benchmarks.run_all --outdir bench_out

This will create:
- bench_out/results_calm.csv
- bench_out/results_pymatgen.csv
- bench_out/figs/*.png
- bench_out/diag_*.csv (for oblique_tradeoff @ pareto_area)

"""

from __future__ import annotations

import argparse
from pathlib import Path

from .run_calm import main as run_calm_main
from .run_pymatgen_zsl import main as run_pymatgen_main
from .plot_benchmarks import main as plot_main
from .diagnose_pair import main as diagnose_main


def _call_as_cli(main_fn, argv):
    import sys

    old = sys.argv
    try:
        sys.argv = [old[0]] + list(argv)
        main_fn()
    finally:
        sys.argv = old


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=str, default="bench_out")
    ap.add_argument("--max-areas", type=str, default="50,100,200,400")
    ap.add_argument("--pareto-area", type=float, default=400.0)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    calm_csv = outdir / "results_calm.csv"
    pym_csv = outdir / "results_pymatgen.csv"
    figs_dir = outdir / "figs"

    _call_as_cli(run_calm_main, ["--out", str(calm_csv), "--max-areas", args.max_areas] + (["--debug"] if args.debug else []))
    _call_as_cli(run_pymatgen_main, ["--out", str(pym_csv), "--max-areas", args.max_areas] + (["--debug"] if args.debug else []))
    _call_as_cli(plot_main, ["--calm", str(calm_csv), "--pymatgen", str(pym_csv), "--outdir", str(figs_dir), "--pareto-area", str(args.pareto_area)])
    _call_as_cli(
        diagnose_main,
        [
            "--pymatgen",
            str(pym_csv),
            "--calm",
            str(calm_csv),
            "--pair",
            "oblique_tradeoff",
            "--max-area",
            str(args.pareto_area),
            "--out-prefix",
            str(outdir / f"diag_oblique_tradeoff_area_{int(args.pareto_area)}"),
        ],
    )

    print(f"All outputs written under: {outdir}")


if __name__ == "__main__":
    main()
