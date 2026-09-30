"""benchmarks.plot_benchmarks

Load benchmark CSV outputs and generate comparison plots.

Plots
-----
1) Match-count scaling vs max_area
   - raw counts (rows)
   - optional unique counts (by match_sig)

2) Pareto-front size vs max_area (optional; recommended)
   - number of Pareto-efficient points at each max_area

3) Mismatch–size Pareto overlays at a fixed max_area
   - scatter: all matches
   - line: Pareto front (minimize d_size and d_cell)

Usage
-----
python -m benchmarks.plot_benchmarks \
  --calm results_calm.csv \
  --pymatgen results_pymatgen.csv \
  --outdir figs \
  --pareto-area 400 \
  --unique-counts \
  --pareto-counts

"""

from __future__ import annotations

import argparse
import os

import pandas as pd
import matplotlib.pyplot as plt

from .pareto import pareto_front_df


def _ensure_outdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _load_and_tag(path: str, method: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "method" not in df.columns:
        df["method"] = method
    return df


def plot_counts_vs_area(df: pd.DataFrame, outdir: str, *, use_unique: bool = False) -> None:
    """Plot #matches vs max_area for each pair (lines by method)."""

    _ensure_outdir(outdir)
    if df.empty:
        print("No data to plot.")
        return

    for pair, d_pair in df.groupby("pair"):
        fig = plt.figure()
        ax = fig.add_subplot(111)

        for method, d_m in d_pair.groupby("method"):
            if use_unique and ("match_sig" in d_m.columns):
                counts = (
                    d_m.groupby("max_area")["match_sig"]
                    .nunique()
                    .reset_index(name="n_matches")
                    .sort_values("max_area")
                )
            else:
                counts = d_m.groupby("max_area").size().reset_index(name="n_matches").sort_values("max_area")

            ax.plot(counts["max_area"], counts["n_matches"], marker="o", label=method)

        ax.set_xlabel("max_area")
        ax.set_ylabel("# matches" + (" (unique by signature)" if use_unique else ""))
        ax.set_title(f"Match count vs area: {pair}")
        ax.legend(loc="best")

        fname = f"counts_vs_area_{pair}{'_unique' if use_unique else ''}.png"
        fig.savefig(os.path.join(outdir, fname), dpi=200, bbox_inches="tight")
        plt.close(fig)


def plot_pareto_counts_vs_area(df: pd.DataFrame, outdir: str) -> None:
    """Plot the number of Pareto-efficient points vs max_area for each pair."""

    _ensure_outdir(outdir)
    if df.empty:
        print("No data to plot.")
        return

    for pair, d_pair in df.groupby("pair"):
        fig = plt.figure()
        ax = fig.add_subplot(111)

        for method, d_m in d_pair.groupby("method"):
            rows = []
            for max_area, d_ma in d_m.groupby("max_area"):
                front = pareto_front_df(d_ma, x_col="d_size", y_col="d_cell")
                rows.append((float(max_area), int(len(front))))
            rows.sort(key=lambda t: t[0])
            x = [r[0] for r in rows]
            y = [r[1] for r in rows]
            ax.plot(x, y, marker="o", label=method)

        ax.set_xlabel("max_area")
        ax.set_ylabel("# Pareto points")
        ax.set_title(f"Pareto-front size vs area: {pair}")
        ax.legend(loc="best")

        fname = f"pareto_count_vs_area_{pair}.png"
        fig.savefig(os.path.join(outdir, fname), dpi=200, bbox_inches="tight")
        plt.close(fig)


def plot_pareto_overlays(df: pd.DataFrame, outdir: str, *, pareto_area: float) -> None:
    """For each pair, scatter (d_size,d_cell) and overlay Pareto front at pareto_area."""

    _ensure_outdir(outdir)

    if df.empty:
        print("No data to plot.")
        return

    for pair, d_pair_all in df.groupby("pair"):
        d_pair = d_pair_all[d_pair_all["max_area"] == pareto_area].copy()
        if d_pair.empty:
            print(f"[WARN] No rows for pair={pair} at max_area={pareto_area}")
            continue

        fig = plt.figure()
        ax = fig.add_subplot(111)

        for method, d_m in d_pair.groupby("method"):
            ax.scatter(d_m["d_size"], d_m["d_cell"], s=20, alpha=0.8, label=f"{method} (n={len(d_m)})")

            front = pareto_front_df(d_m, x_col="d_size", y_col="d_cell")
            if len(front) >= 2:
                ax.plot(front["d_size"], front["d_cell"], marker="o")
            elif len(front) == 1:
                ax.plot(front["d_size"], front["d_cell"], marker="o")

        ax.set_xlabel(r"$d_{size}$ (log size proxy)")
        ax.set_ylabel(r"$d_{cell}$ (AIRM distance)")
        ax.set_title(f"Pareto overlay: {pair} @ max_area={pareto_area}")
        ax.legend(loc="best")

        fname = f"pareto_{pair}_area_{int(pareto_area)}.png"
        fig.savefig(os.path.join(outdir, fname), dpi=200, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pymatgen", type=str, required=True)
    ap.add_argument("--calm", type=str, required=True, help="CSV from benchmarks.run_calm")
    ap.add_argument("--outdir", type=str, default="figs")
    ap.add_argument("--pareto-area", type=float, default=400.0)
    ap.add_argument("--unique-counts", action="store_true", help="use match_sig unique counts in count-vs-area plots")
    ap.add_argument("--pareto-counts", action="store_true", help="also plot #Pareto points vs max_area")
    args = ap.parse_args()

    df_s = _load_and_tag(args.calm, "calm_coupled_v2")
    df_p = _load_and_tag(args.pymatgen, "pymatgen_zsl")
    df = pd.concat([df_s, df_p], ignore_index=True)

    plot_counts_vs_area(df, args.outdir, use_unique=bool(args.unique_counts))
    if args.pareto_counts:
        plot_pareto_counts_vs_area(df, args.outdir)

    plot_pareto_overlays(df, args.outdir, pareto_area=float(args.pareto_area))

    print(f"Wrote plots to: {args.outdir}")


if __name__ == "__main__":
    main()
