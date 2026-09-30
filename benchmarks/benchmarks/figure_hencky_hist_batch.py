"""benchmarks.figure_hencky_hist_batch

Convenience wrapper that runs :mod:`benchmarks.figure_hencky_hist` for multiple
benchmark lattice pairs.

This is useful when you want to show that the histogram-based conclusion is not
specific to a single synthetic pair (e.g. oblique_tradeoff), but is consistent
across several canonical test cases.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def _split_csv(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pairs",
        type=str,
        default="rect_small_mismatch,hex_near_degenerate,oblique_tradeoff",
        help="Comma-separated list of benchmark pair names",
    )
    ap.add_argument("--max-area", type=float, required=True)
    ap.add_argument("--max-length-tol", type=float, default=0.03)
    ap.add_argument("--max-angle-tol", type=float, default=0.01)
    ap.add_argument("--epsilon-max", type=float, default=0.03)
    ap.add_argument("--tau-max", type=float, default=0.06)
    ap.add_argument("--max-area-ratio-tol", type=float, default=0.09)
    ap.add_argument("--percent", action="store_true")
    ap.add_argument("--density", action="store_true")
    ap.add_argument("--dump-csv", action="store_true")
    ap.add_argument("--outdir", type=str, default="figs")
    args = ap.parse_args()

    pairs = _split_csv(args.pairs)
    if not pairs:
        raise SystemExit("No pairs provided")

    for pair in pairs:
        cmd = [
            sys.executable,
            "-m",
            "benchmarks.figure_hencky_hist",
            "--pair",
            pair,
            "--max-area",
            str(args.max_area),
            "--max-length-tol",
            str(args.max_length_tol),
            "--max-angle-tol",
            str(args.max_angle_tol),
            "--max-area-ratio-tol",
            str(args.max_area_ratio_tol),
            "--epsilon-max",
            str(args.epsilon_max),
            "--tau-max",
            str(args.tau_max),
            "--outdir",
            str(args.outdir),
        ]
        if args.percent:
            cmd.append("--percent")
        if args.density:
            cmd.append("--density")
        if args.dump_csv:
            cmd.append("--dump-csv")

        print(f"\n=== Running hencky_hist for pair={pair} ===")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
