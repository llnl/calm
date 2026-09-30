"""benchmarks.diagnose_pair

Diagnose discrepancies between two benchmark result CSVs for a specific pair
and max_area.

Main use case
-------------
Explain differences between production coupled CALM and pymatgen ZSL.

This script computes:
- total match counts per method
- cross-gating (apply ZSL-style length/angle gates to CALM; apply strain gate to pymatgen)
- intersection/union based on canonical match signatures
- Pareto-front agreement

It also writes a small set of diagnostic CSV files so you can inspect the
specific extra matches.

Usage (as a module)
-------------------
python -m benchmarks.diagnose_pair \
  --pymatgen results_pymatgen.csv \
  --calm results_calm.csv \
  --pair oblique_tradeoff \
  --max-area 400

"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .pareto import pareto_front_df


@dataclass(frozen=True)
class Gates:
    max_length_tol: float
    max_angle_tol: float
    eps_principal_max: float


def _zsl_pass(df: pd.DataFrame, gates: Gates) -> pd.Series:
    return (
        (df["rel_da"] <= gates.max_length_tol)
        & (df["rel_db"] <= gates.max_length_tol)
        & (df["rel_dgamma"] <= gates.max_angle_tol)
    )


def _strain_pass(df: pd.DataFrame, gates: Gates) -> pd.Series:
    return df["max_abs_principal_strain"] <= gates.eps_principal_max


def diagnose_pair_discrepancy(
    pymatgen_csv: str,
    calm_csv: str,
    *,
    pair: str,
    max_area: float,
    out_prefix: Optional[str] = None,
    max_length_tol: float = 0.03,
    max_angle_tol: float = 0.01,
    eps_principal_max: float = 0.03,
) -> None:
    """Core diagnostic entrypoint used both by CLI and notebooks."""

    gates = Gates(max_length_tol=max_length_tol, max_angle_tol=max_angle_tol, eps_principal_max=eps_principal_max)

    df_p = pd.read_csv(pymatgen_csv)
    df_s = pd.read_csv(calm_csv)

    label_s = "calm"
    if not df_s.empty and "method" in df_s.columns:
        try:
            label_s = str(df_s["method"].iloc[0])
        except Exception:
            label_s = "calm"
    label_s_safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in label_s)

    df_p = df_p[(df_p["pair"] == pair) & (df_p["max_area"] == max_area)].copy()
    df_s = df_s[(df_s["pair"] == pair) & (df_s["max_area"] == max_area)].copy()

    # Basic counts
    print(f"=== Diagnose: pair={pair} max_area={max_area} ===")
    if df_p.empty and df_s.empty:
        print("No rows found for this pair/max_area in either file.")
        return

    print(f"pymatgen_zsl: n={len(df_p)}  (max_length_tol={max_length_tol}, max_angle_tol={max_angle_tol})")
    print(f"{label_s_safe}:      n={len(df_s)}  (eps_principal_max={eps_principal_max})")
    print()

    # Cross-gating
    s_pass_zsl = _zsl_pass(df_s, gates)
    p_pass_strain = _strain_pass(df_p, gates)

    print(f"{label_s_safe} matches that pass ZSL-style (rel_da, rel_db, rel_dgamma) gates: {int(s_pass_zsl.sum())} / {len(df_s)}")
    print(f"pymatgen matches that pass {label_s_safe} principal-strain gate: {int(p_pass_strain.sum())} / {len(df_p)}")
    print()

    viol_len = int(((df_s['rel_da'] > max_length_tol) | (df_s['rel_db'] > max_length_tol)).sum())
    print(f"{label_s_safe} violating length tol: {viol_len} / {len(df_s)}")
    print(f"{label_s_safe} violating angle  tol: {int((df_s['rel_dgamma']>max_angle_tol).sum())} / {len(df_s)}")
    print()

    # Distribution summaries
    def q(df: pd.DataFrame, col: str):
        x = df[col].to_numpy()
        qs = np.quantile(x[np.isfinite(x)], [0, 0.5, 0.9, 0.99, 1.0])
        return dict(zip(["q00", "q50", "q90", "q99", "q100"], [float(v) for v in qs]))

    print("pymatgen rel_dgamma / max_abs_principal_strain:")
    print(f"  rel_dgamma: {q(df_p, 'rel_dgamma')}")
    print(f"  max_abs_principal_strain: {q(df_p, 'max_abs_principal_strain')}")
    print(f"{label_s_safe} rel_dgamma / max_abs_principal_strain:")
    print(f"  rel_dgamma: {q(df_s, 'rel_dgamma')}")
    print(f"  max_abs_principal_strain: {q(df_s, 'max_abs_principal_strain')}")
    print()

    # Signature overlap
    if ("match_sig" in df_p.columns) and ("match_sig" in df_s.columns):
        sig_p = set(df_p["match_sig"].astype(str))
        sig_s = set(df_s["match_sig"].astype(str))
        inter = sig_p & sig_s
        print("Signature overlap:")
        print(f"  |pymatgen sigs| = {len(sig_p)}")
        print(f"  |{label_s_safe}  sigs| = {len(sig_s)}")
        print(f"  |intersection|  = {len(inter)}")
        print(f"  |pymatgen-only| = {len(sig_p - sig_s)}")
        print(f"  |{label_s_safe}-only|  = {len(sig_s - sig_p)}")
        print()
    else:
        print("[WARN] match_sig column missing; signature overlap skipped.\n")

    # Pareto fronts
    front_p = pareto_front_df(df_p, x_col="d_size", y_col="d_cell")
    front_s = pareto_front_df(df_s, x_col="d_size", y_col="d_cell")
    print(f"Pareto counts: pymatgen={len(front_p)} {label_s_safe}={len(front_s)}")

    if ("match_sig" in front_p.columns) and ("match_sig" in front_s.columns):
        fp = set(front_p["match_sig"].astype(str))
        fs = set(front_s["match_sig"].astype(str))
        print(f"Pareto signature overlap: |intersection|={len(fp & fs)} (expected = {max(len(fp),len(fs))} if identical)")
    print()

    # Extra CALM matches that violate the ZSL angle tolerance.
    extra_s = df_s[df_s["rel_dgamma"] > max_angle_tol].copy()
    print(f"Extra {label_s_safe} matches (violating ZSL angle tol): {len(extra_s)}")
    if len(extra_s) > 0:
        cols = ["kA","kB","d_cell","d_size","rel_da","rel_db","rel_dgamma","d_gamma_deg","max_abs_principal_strain","match_sig"]
        cols = [c for c in cols if c in extra_s.columns]
        top = extra_s.sort_values("d_cell").head(10)[cols]
        print("Top 10 by smallest d_cell among those (these are 'best' extra matches):")
        print(top.to_string(index=False))

    # Write diagnostics
    if out_prefix is None:
        out_prefix = f"diag_{pair}_area_{int(max_area)}"

    df_p.to_csv(f"{out_prefix}_pymatgen.csv", index=False)
    df_s.to_csv(f"{out_prefix}_{label_s_safe}.csv", index=False)
    extra_s.to_csv(f"{out_prefix}_extra_{label_s_safe}.csv", index=False)
    print()
    print(f"Wrote diagnostic CSVs with prefix: {out_prefix}_*.csv")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Diagnose discrepancies between pymatgen ZSL and production coupled CALM for a benchmark pair and max_area. "
            "Writes diagnostic CSVs for each method and the method-specific extra set."
        )
    )
    ap.add_argument("--pymatgen", required=True, help="results_pymatgen.csv")
    ap.add_argument("--calm", required=True, help="results_calm.csv")
    ap.add_argument("--pair", required=True, help="benchmark pair name")
    ap.add_argument("--max-area", type=float, required=True, help="max_area to filter on")
    ap.add_argument("--out-prefix", type=str, default=None)
    ap.add_argument(
        "--outdir",
        type=str,
        default=None,
        help=(
            "Output directory for diagnostic CSVs. If provided and --out-prefix is not set, "
            "a deterministic prefix of the form '{outdir}/diag_{pair}_area_{max_area}' will be used. "
            "If both --outdir and --out-prefix are provided, --out-prefix is interpreted as a file prefix "
            "relative to --outdir unless it already contains a path separator."
        ),
    )
    ap.add_argument("--max-length-tol", type=float, default=0.03)
    ap.add_argument("--max-angle-tol", type=float, default=0.01)
    ap.add_argument("--eps-principal-max", type=float, default=0.03)
    args = ap.parse_args()

    out_prefix = args.out_prefix
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        if out_prefix is None:
            # Default prefix aligned with README examples.
            out_prefix = os.path.join(args.outdir, f"diag_{args.pair}_area_{int(args.max_area)}")
        else:
            # If user passed just a basename, place it under outdir.
            if os.path.sep not in out_prefix:
                out_prefix = os.path.join(args.outdir, out_prefix)

    diagnose_pair_discrepancy(
        args.pymatgen,
        args.calm,
        pair=args.pair,
        max_area=args.max_area,
        out_prefix=out_prefix,
        max_length_tol=args.max_length_tol,
        max_angle_tol=args.max_angle_tol,
        eps_principal_max=args.eps_principal_max,
    )


if __name__ == "__main__":
    main()
