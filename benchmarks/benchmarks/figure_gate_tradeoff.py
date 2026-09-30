r"""benchmarks.figure_gate_tradeoff

Generate tradeoff curves that relate pymatgen ZSL heuristic gates
(length/angle tolerances on reduced (a,b,\gamma)) to CALM's principal-strain admission rule and an optional post-search
log-area reporting filter (\tau_max).

The core output is a CSV summarizing, for a sweep of ZSL angle tolerances:

  - ZSL match count
  - CALM match count (fixed by \epsilon_max and optional \tau_max reporting filter)
  - overlap count (by canonical match signature)
  - recall = |ZSL ∩ CALM| / |CALM|
  - precision = |ZSL ∩ CALM| / |ZSL|
  - Jaccard = |∩| / |∪|

Optionally, a plot is produced showing recall/precision as a function
of the swept tolerance.

This is intended for inclusion in the Supporting Information (or as a
main-text robustness figure) to quantify how conservative a fixed
ZSL-style angle gate is relative to an explicit strain budget.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd


def _parse_csv_floats(s: str) -> List[float]:
    out: List[float] = []
    for tok in (s or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("Expected a non-empty comma-separated list of floats")
    return out


def _ensure_outdir(path: str) -> str:
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    return path


def _sigset(rows: Sequence[dict]) -> set[str]:
    """Return the set of canonical match signatures present in rows."""
    return {str(r["match_sig"]) for r in rows if r.get("match_sig") not in (None, "")}


@dataclass(frozen=True)
class TradeoffRow:
    angle_tol: float
    n_zsl: int
    n_calm: int
    n_intersection: int
    n_union: int
    recall: float
    precision: float
    jaccard: float


def compute_tradeoff(
    *,
    pair: str,
    max_area: float,
    max_length_tol: float,
    angle_tols: Iterable[float],
    max_area_ratio_tol: float,
    epsilon_max: float,
    tau_max: float,
    nA_prim: int,
    nB_prim: int,
    N_at_max: int,
    w_match: float,
    sig_tol: float,
    sig_scale: float,
) -> List[TradeoffRow]:
    """Compute overlap metrics for a sweep of ZSL angle tolerances."""

    from .benchmark_pairs import get_benchmark_pair
    from .run_pymatgen_zsl import run_zsl_for_pair
    from .run_calm import run_calm_for_pair

    pair_cfg = get_benchmark_pair(pair)

    # -- Baseline CALM set (principal-strain admission with optional tau_max reporting filter)
    rows_calm = run_calm_for_pair(
        pair_name=pair,
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=max_area,
        cond_max=1e6,
        tau_max=float(tau_max),
        eps_principal_max=float(epsilon_max),
        N_at_max=int(N_at_max),
        w_match=float(w_match),
        nA_prim=int(nA_prim),
        nB_prim=int(nB_prim),
        sig_tol=float(sig_tol),
        sig_scale=float(sig_scale),
    )
    calm_sigs = _sigset(rows_calm)

    out: List[TradeoffRow] = []

    # -- ZSL sweep
    for ang in angle_tols:
        rows_zsl = run_zsl_for_pair(
            pair_name=pair,
            A2=pair_cfg.A,
            B2=pair_cfg.B,
            max_area=max_area,
            max_length_tol=float(max_length_tol),
            max_angle_tol=float(ang),
            max_area_ratio_tol=float(max_area_ratio_tol),
            nA_prim=int(nA_prim),
            nB_prim=int(nB_prim),
            N_at_max=int(N_at_max),
            eps_principal_max=float(epsilon_max),
            w_match=float(w_match),
            sig_tol=float(sig_tol),
            sig_scale=float(sig_scale),
        )
        zsl_sigs = _sigset(rows_zsl)

        inter = zsl_sigs & calm_sigs
        union = zsl_sigs | calm_sigs

        n_zsl = len(zsl_sigs)
        n_calm = len(calm_sigs)
        n_inter = len(inter)
        n_union = len(union)

        recall = (n_inter / n_calm) if n_calm else float("nan")
        precision = (n_inter / n_zsl) if n_zsl else float("nan")
        jaccard = (n_inter / n_union) if n_union else float("nan")

        out.append(
            TradeoffRow(
                angle_tol=float(ang),
                n_zsl=int(n_zsl),
                n_calm=int(n_calm),
                n_intersection=int(n_inter),
                n_union=int(n_union),
                recall=float(recall),
                precision=float(precision),
                jaccard=float(jaccard),
            )
        )

    # Deterministic order
    out.sort(key=lambda r: r.angle_tol)
    return out


def _plot_tradeoff(
    *,
    rows: Sequence[TradeoffRow],
    outpath: str,
    percent: bool,
    title: str,
) -> None:
    import matplotlib.pyplot as plt

    x = np.array([r.angle_tol for r in rows], dtype=float)
    if percent:
        x = 100.0 * x

    recall = np.array([r.recall for r in rows], dtype=float)
    precision = np.array([r.precision for r in rows], dtype=float)
    jaccard = np.array([r.jaccard for r in rows], dtype=float)

    plt.figure(figsize=(7.2, 4.5))
    plt.plot(x, recall, marker="o", label="recall (ZSL ∩ CALM) / CALM")
    plt.plot(x, precision, marker="o", label="precision (ZSL ∩ CALM) / ZSL")
    plt.plot(x, jaccard, marker="o", label="Jaccard |∩|/|∪|")
    plt.ylim(-0.02, 1.02)
    plt.grid(True, alpha=0.3)
    plt.xlabel("ZSL angle tolerance" + (" (%)" if percent else ""))
    plt.ylabel("set agreement")
    plt.title(title)
    plt.legend(loc="best")
    plt.tight_layout()
    plt.savefig(outpath, dpi=200)
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Sweep pymatgen ZSL angle tolerance and quantify overlap with CALM "
            "(Hencky/area-gated) matches using canonical match signatures."
        )
    )
    ap.add_argument("--pair", required=True, help="Benchmark pair name (e.g. oblique_tradeoff)")
    ap.add_argument("--max-area", type=float, required=True, help="Max supercell area")
    ap.add_argument("--max-length-tol", type=float, default=0.03, help="ZSL max length tolerance")
    ap.add_argument(
        "--angle-tols",
        type=str,
        required=True,
        help="Comma-separated list of ZSL angle tolerances to sweep (e.g. 0.005,0.01,0.02)",
    )
    ap.add_argument(
        "--max-area-ratio-tol",
        type=float,
        default=0.01,
        help="ZSL max area-ratio tolerance (r1/r2 approximation tolerance)",
    )
    ap.add_argument("--epsilon-max", type=float, default=0.03, help="CALM max principal Hencky")
    ap.add_argument("--tau-max", type=float, default=0.06, help="Optional post-search |log area ratio| reporting filter")
    ap.add_argument("--nA-prim", type=int, default=1, help="Primitive atoms in A (size proxy)")
    ap.add_argument("--nB-prim", type=int, default=1, help="Primitive atoms in B (size proxy)")
    ap.add_argument("--N-at-max", type=int, default=1000, help="Atom-count budget proxy")
    ap.add_argument("--w-match", type=float, default=1.0, help="Match objective weight")
    ap.add_argument("--sig-tol", type=float, default=1e-12)
    ap.add_argument("--sig-scale", type=float, default=1e10)
    ap.add_argument("--percent", action="store_true", help="Display tolerances in percent")
    ap.add_argument("--no-plot", action="store_true", help="Only write CSV, do not plot")
    ap.add_argument("--outdir", type=str, default="figs", help="Output directory")
    ap.add_argument(
        "--outfile",
        type=str,
        default=None,
        help="CSV filename (default: gate_tradeoff_<pair>_area_<max_area>.csv)",
    )

    args = ap.parse_args()
    outdir = _ensure_outdir(args.outdir)
    angle_tols = _parse_csv_floats(args.angle_tols)

    rows = compute_tradeoff(
        pair=str(args.pair),
        max_area=float(args.max_area),
        max_length_tol=float(args.max_length_tol),
        angle_tols=angle_tols,
        max_area_ratio_tol=float(args.max_area_ratio_tol),
        epsilon_max=float(args.epsilon_max),
        tau_max=float(args.tau_max),
        nA_prim=int(args.nA_prim),
        nB_prim=int(args.nB_prim),
        N_at_max=int(args.N_at_max),
        w_match=float(args.w_match),
        sig_tol=float(args.sig_tol),
        sig_scale=float(args.sig_scale),
    )

    df = pd.DataFrame([r.__dict__ for r in rows])
    if args.outfile is None:
        stem = f"gate_tradeoff_{args.pair}_area_{args.max_area:g}.csv"
        out_csv = os.path.join(outdir, stem)
    else:
        out_csv = os.path.join(outdir, str(args.outfile))
    df.to_csv(out_csv, index=False)
    print(f"Wrote CSV: {out_csv}")

    if not args.no_plot:
        out_png = os.path.join(outdir, f"gate_tradeoff_{args.pair}_area_{args.max_area:g}.png")
        title = (
            f"Gate tradeoff: {args.pair} @ max_area={args.max_area:g} "
            f"(len_tol={args.max_length_tol:g}, eps={args.epsilon_max:g}, tau={args.tau_max:g})"
        )
        _plot_tradeoff(rows=rows, outpath=out_png, percent=bool(args.percent), title=title)
        print(f"Wrote: {out_png}")


if __name__ == "__main__":
    main()
