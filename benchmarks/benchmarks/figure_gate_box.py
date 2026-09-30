"""benchmarks.figure_gate_box

2D feasibility-gate visualization in (|log area ratio|, max principal Hencky strain).

This figure complements the 1D Hencky histogram:

- The x-axis (|log area ratio|) is an intrinsic area-mismatch diagnostic. An
  optional tau_max filter can be applied after coupled matching for reporting.
- The y-axis (max |Hencky principal strain|) is CALM's hard scientific
  feasibility gate (epsilon_max).

The plot overlays *accepted* matches returned by:
- pymatgen ZSL (with (a,b,gamma) heuristic tolerances)
- CALM coupled-v2 (principal-strain admission plus optional tau_max reporting filter)

and draws the selected reporting rectangle to show (i) that CALM enforces the
principal-strain bound by construction and (ii) that ZSL heuristic tolerances do not directly correspond to
those bounds (some ZSL matches may lie outside and many admissible CALM matches may
be rejected by ZSL).
"""

from __future__ import annotations

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd

from .benchmark_pairs import get_benchmark_pair
from .run_pymatgen_zsl import run_zsl_for_pair
from .run_calm import run_calm_for_pair


def _ensure_outdir(outdir: str) -> str:
    outdir = os.path.abspath(os.path.expanduser(outdir))
    os.makedirs(outdir, exist_ok=True)
    return outdir


def _scale(x: float, percent: bool) -> float:
    return 100.0 * x if percent else x


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pair", required=True)
    ap.add_argument("--max-area", type=float, required=True)

    # ZSL gates
    ap.add_argument("--max-length-tol", type=float, default=0.03)
    ap.add_argument("--max-angle-tol", type=float, default=0.01)
    ap.add_argument("--max-area-ratio-tol", type=float, default=0.01)
    ap.add_argument("--nA-prim", type=int, default=1)
    ap.add_argument("--nB-prim", type=int, default=1)

    # CALM admission and reporting controls
    ap.add_argument("--epsilon-max", type=float, default=0.03)
    ap.add_argument("--tau-max", type=float, default=0.06)

    # shared
    ap.add_argument("--N-at-max", type=int, default=1000)
    ap.add_argument("--w-match", type=float, default=1.0)
    ap.add_argument("--sig-tol", type=float, default=1e-12)
    ap.add_argument("--sig-scale", type=float, default=1e10)

    ap.add_argument("--percent", action="store_true", help="Show x/y in percent")
    ap.add_argument("--alpha", type=float, default=0.35)
    ap.add_argument("--outdir", type=str, default="figs")
    ap.add_argument("--dump-csv", action="store_true", help="Also dump per-point CSVs")

    args = ap.parse_args()
    outdir = _ensure_outdir(args.outdir)

    # -- Run both methods
    pair_cfg = get_benchmark_pair(str(args.pair))
    rows_zsl = run_zsl_for_pair(
        pair_name=str(args.pair),
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=float(args.max_area),
        max_length_tol=float(args.max_length_tol),
        max_angle_tol=float(args.max_angle_tol),
        max_area_ratio_tol=float(args.max_area_ratio_tol),
        nA_prim=int(args.nA_prim),
        nB_prim=int(args.nB_prim),
        N_at_max=int(args.N_at_max),
        eps_principal_max=float(args.epsilon_max),
        w_match=float(args.w_match),
        sig_tol=float(args.sig_tol),
        sig_scale=float(args.sig_scale),
    )
    rows_calm = run_calm_for_pair(
        pair_name=str(args.pair),
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=float(args.max_area),
        tau_max=float(args.tau_max),
        eps_principal_max=float(args.epsilon_max),
        nA_prim=int(args.nA_prim),
        nB_prim=int(args.nB_prim),
        N_at_max=int(args.N_at_max),
        w_match=float(args.w_match),
        sig_tol=float(args.sig_tol),
        sig_scale=float(args.sig_scale),
    )

    df_zsl = pd.DataFrame(rows_zsl)
    df_calm = pd.DataFrame(rows_calm)

    # sanity: columns present
    for col in ("log_area_ratio", "max_abs_principal_strain"):
        if col not in df_zsl.columns or col not in df_calm.columns:
            raise RuntimeError(f"Expected column '{col}' in both methods.")

    xlab = r"$|\log(A_A/A_B)|$"
    ylab = r"$\max_i |\varepsilon_{H,i}|$"
    if args.percent:
        xlab += " (%)"
        ylab += " (%)"
    else:
        xlab += " (dimensionless)"
        ylab += " (dimensionless)"

    # Plot
    fig = plt.figure()
    plt.scatter(
        [_scale(x, args.percent) for x in df_zsl["log_area_ratio"].to_list()],
        [_scale(y, args.percent) for y in df_zsl["max_abs_principal_strain"].to_list()],
        alpha=float(args.alpha),
        label=f"pymatgen_zsl (n={len(df_zsl)})",
    )
    plt.scatter(
        [_scale(x, args.percent) for x in df_calm["log_area_ratio"].to_list()],
        [_scale(y, args.percent) for y in df_calm["max_abs_principal_strain"].to_list()],
        alpha=float(args.alpha),
        label=f"calm (n={len(df_calm)})",
    )

    # CALM admissible rectangle
    x_gate = _scale(float(args.tau_max), args.percent)
    y_gate = _scale(float(args.epsilon_max), args.percent)
    plt.axvline(x_gate, linestyle="--")
    plt.axhline(y_gate, linestyle="--")

    plt.xlabel(xlab)
    plt.ylabel(ylab)
    plt.title(f"Feasibility gates: {args.pair} @ max_area={args.max_area:g}")
    plt.legend()

    out_png = os.path.join(outdir, f"gate_box_{args.pair}_area_{args.max_area:g}.png")
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote: {out_png}")

    if args.dump_csv:
        out_csv_zsl = os.path.join(outdir, f"gate_box_{args.pair}_area_{args.max_area:g}_pymatgen_zsl.csv")
        out_csv_calm = os.path.join(outdir, f"gate_box_{args.pair}_area_{args.max_area:g}_calm.csv")
        df_zsl.to_csv(out_csv_zsl, index=False)
        df_calm.to_csv(out_csv_calm, index=False)
        print(f"Wrote CSV: {out_csv_zsl}")
        print(f"Wrote CSV: {out_csv_calm}")


if __name__ == "__main__":
    main()
