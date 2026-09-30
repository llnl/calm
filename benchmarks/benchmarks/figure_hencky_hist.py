"""benchmarks.figure_hencky_hist

Histogram-based comparison of lattice-matching gate behavior.

This script supports the paper figure demonstrating that:
(i) ZSL's traditional Zur–McGill style gates (separate tolerances on reduced
    lengths and reduced angle) can be conservative relative to a direct bound on
    principal Hencky strain; and
(ii) CALM's intrinsic principal-strain gate controls scientific admission,
    while tau_max is only an optional post-search reporting filter.

Compared to earlier drafts, this version improves plot quality for
publication:
- Step/outlined histograms to avoid muddy overplotting.
- Optional paper-style rcParams.
- Multi-format saving (png,pdf).
- Optional title suppression for composing multi-panel figures.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

from .benchmark_pairs import get_benchmark_pair
from .run_pymatgen_zsl import run_zsl_for_pair
from .run_calm import run_calm_for_pair


def _configure_matplotlib(paper: bool = True) -> None:
    if not paper:
        return
    mpl.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _save_fig_multi(fig: plt.Figure, outbase: Path, formats: str) -> None:
    fmts = [f.strip().lower() for f in formats.split(",") if f.strip()]
    if not fmts:
        fmts = ["png"]
    outbase.parent.mkdir(parents=True, exist_ok=True)
    for fmt in fmts:
        fig.savefig(outbase.with_suffix(f".{fmt}"), bbox_inches="tight")


def _extract_max_principal(rows: List[dict], *, percent: bool) -> np.ndarray:
    arr = np.array([float(r.get("max_abs_principal_strain", "nan")) for r in rows], dtype=float)
    arr = arr[np.isfinite(arr)]
    if percent:
        arr = 100.0 * arr
    return arr


def _split_by_zsl_gates(
    rows: List[dict],
    *,
    max_length_tol: float,
    max_angle_tol: float,
) -> Tuple[List[dict], List[dict]]:
    """Split CALM rows into (pass ZSL, fail ZSL) using rel_da/rel_db/rel_dgamma."""
    passed: List[dict] = []
    failed: List[dict] = []

    for r in rows:
        try:
            rel_da = float(r.get("rel_da"))
            rel_db = float(r.get("rel_db"))
            rel_dg = float(r.get("rel_dgamma"))
        except Exception:
            failed.append(r)
            continue

        ok = (rel_da <= max_length_tol) and (rel_db <= max_length_tol) and (rel_dg <= max_angle_tol)
        (passed if ok else failed).append(r)

    return passed, failed


def _plot_hist_overlay(
    *,
    pair: str,
    max_area: float,
    data_zsl: np.ndarray,
    data_calm: np.ndarray,
    epsilon_max: Optional[float],
    percent: bool,
    density: bool,
    bins: int,
    outdir: Path,
    formats: str,
    no_title: bool,
) -> None:
    fig, ax = plt.subplots(figsize=(4.0, 3.0))

    # Shared bin edges for direct comparison
    lo = 0.0
    hi = float(np.max([np.max(data_zsl) if data_zsl.size else 0.0, np.max(data_calm) if data_calm.size else 0.0]))
    if epsilon_max is not None:
        hi = max(hi, float(epsilon_max) * (100.0 if percent else 1.0))

    # Add small headroom to avoid clipping of right-most bin
    hi = hi * 1.05 if hi > 0 else 1.0

    edges = np.linspace(lo, hi, int(bins) + 1)

    # Outline for pymatgen; filled for CALM to keep both visible
    ax.hist(
        data_zsl,
        bins=edges,
        density=bool(density),
        histtype="step",
        linewidth=1.6,
        label=f"pymatgen_zsl (n={data_zsl.size})",
        color="C0",
        zorder=3,
    )
    ax.hist(
        data_calm,
        bins=edges,
        density=bool(density),
        histtype="stepfilled",
        alpha=0.35,
        label=f"calm (n={data_calm.size})",
        color="C1",
        zorder=2,
    )

    if epsilon_max is not None:
        xline = float(epsilon_max) * (100.0 if percent else 1.0)
        ax.axvline(xline, linestyle="--", linewidth=1.2, label=rf"$\varepsilon_{{\max}}={xline:g}$" + ("%" if percent else ""))

    if not no_title:
        ax.set_title(f"Hencky strain histogram: {pair} @ max_area={max_area:g}")

    ax.set_xlabel("max |Hencky principal strain|" + (" (%)" if percent else ""))
    ax.set_ylabel("density" if density else "count")

    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False)

    outbase = outdir / f"hencky_hist_overlay_{pair}_area_{max_area:g}"
    _save_fig_multi(fig, outbase, formats)
    plt.close(fig)


def _plot_hist_calm_split(
    *,
    pair: str,
    max_area: float,
    data_pass: np.ndarray,
    data_fail: np.ndarray,
    epsilon_max: Optional[float],
    percent: bool,
    density: bool,
    bins: int,
    outdir: Path,
    formats: str,
    no_title: bool,
    max_angle_tol: float,
) -> None:
    fig, ax = plt.subplots(figsize=(4.0, 3.0))

    lo = 0.0
    hi = float(np.max([np.max(data_pass) if data_pass.size else 0.0, np.max(data_fail) if data_fail.size else 0.0]))
    if epsilon_max is not None:
        hi = max(hi, float(epsilon_max) * (100.0 if percent else 1.0))
    hi = hi * 1.05 if hi > 0 else 1.0

    edges = np.linspace(lo, hi, int(bins) + 1)

    # Both as stepfilled but with different alpha
    ax.hist(
        data_pass,
        bins=edges,
        density=bool(density),
        histtype="stepfilled",
        alpha=0.35,
        label=f"calm & passes ZSL (n={data_pass.size})",
        color="C0",
        zorder=2,
    )
    ax.hist(
        data_fail,
        bins=edges,
        density=bool(density),
        histtype="stepfilled",
        alpha=0.35,
        label=f"calm but fails ZSL (n={data_fail.size})",
        color="C1",
        zorder=1,
    )

    if epsilon_max is not None:
        xline = float(epsilon_max) * (100.0 if percent else 1.0)
        ax.axvline(xline, linestyle="--", linewidth=1.2, label=rf"$\varepsilon_{{\max}}={xline:g}$" + ("%" if percent else ""))

    if not no_title:
        ax.set_title(
            f"CALM matches split by ZSL gates: {pair} @ max_area={max_area:g} (angle tol={max_angle_tol:g})"
        )

    ax.set_xlabel("max |Hencky principal strain|" + (" (%)" if percent else ""))
    ax.set_ylabel("density" if density else "count")

    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False)

    outbase = outdir / f"hencky_hist_calm_split_{pair}_area_{max_area:g}"
    _save_fig_multi(fig, outbase, formats)
    plt.close(fig)


def _dump_csv(outpath: Path, rows: List[dict]) -> None:
    import csv

    outpath.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        # Still write headers so downstream scripts don't crash.
        with outpath.open("w", newline="") as f:
            f.write("\n")
        return

    # Stable column order: sort keys
    keys = sorted({k for r in rows for k in r.keys()})
    with outpath.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _load_methods(
    *,
    pair: str,
    max_area: float,
    max_length_tol: float,
    max_angle_tol: float,
    epsilon_max: float,
    tau_max: float,
    cond_max: float,
    niggli_tol: float,
    nA_prim: int,
    nB_prim: int,
    N_at_max: int,
    w_match: float,
) -> Tuple[List[dict], List[dict]]:
    """Run both methods and return raw match rows."""

    pair_cfg = get_benchmark_pair(pair)

    # ZSL
    rows_zsl = run_zsl_for_pair(
        pair_name=pair,
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=float(max_area),
        max_length_tol=float(max_length_tol),
        max_angle_tol=float(max_angle_tol),
        max_area_ratio_tol=float(max_angle_tol),
        nA_prim=int(nA_prim),
        nB_prim=int(nB_prim),
        N_at_max=int(N_at_max),
        eps_principal_max=float(epsilon_max),
        w_match=float(w_match),
        sig_tol=float(niggli_tol),
        sig_scale=1e10,
        debug=False,
    )

    # CALM
    rows_calm = run_calm_for_pair(
        pair_name=pair,
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=float(max_area),
        eps_principal_max=float(epsilon_max),
        tau_max=float(tau_max),
        cond_max=float(cond_max),
        nA_prim=int(nA_prim),
        nB_prim=int(nB_prim),
        N_at_max=int(N_at_max),
        w_match=float(w_match),
        sig_tol=float(niggli_tol),
        sig_scale=1e10,
        debug=False,
    )

    return rows_zsl, rows_calm


def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--pair", required=True)
    ap.add_argument("--max-area", type=float, required=True)

    # ZSL gates
    ap.add_argument("--max-length-tol", type=float, default=0.03)
    ap.add_argument("--max-angle-tol", type=float, default=0.01)

    # CALM admission and reporting controls
    ap.add_argument("--epsilon-max", type=float, default=0.03)
    ap.add_argument("--tau-max", type=float, default=0.06)

    # Shared
    ap.add_argument("--cond-max", type=float, default=1e6)
    ap.add_argument("--niggli-tol", type=float, default=1e-12)
    ap.add_argument("--nA-prim", type=int, default=1)
    ap.add_argument("--nB-prim", type=int, default=1)
    ap.add_argument("--N-at-max", type=int, default=1000)
    ap.add_argument("--w-match", type=float, default=1.0)

    ap.add_argument("--bins", type=int, default=40)
    ap.add_argument("--density", action="store_true")
    ap.add_argument("--percent", action="store_true")

    ap.add_argument("--dump-csv", action="store_true")
    ap.add_argument("--outdir", default="figs")
    ap.add_argument("--formats", default="png", help="Comma-separated formats, e.g. png,pdf")

    ap.add_argument("--paper-style", action="store_true")
    ap.add_argument("--no-title", action="store_true")

    args = ap.parse_args()

    _configure_matplotlib(paper=bool(args.paper_style))

    rows_zsl, rows_calm = _load_methods(
        pair=str(args.pair),
        max_area=float(args.max_area),
        max_length_tol=float(args.max_length_tol),
        max_angle_tol=float(args.max_angle_tol),
        epsilon_max=float(args.epsilon_max),
        tau_max=float(args.tau_max),
        cond_max=float(args.cond_max),
        niggli_tol=float(args.niggli_tol),
        nA_prim=int(args.nA_prim),
        nB_prim=int(args.nB_prim),
        N_at_max=int(args.N_at_max),
        w_match=float(args.w_match),
    )

    # Split CALM by ZSL gates
    calm_pass, calm_fail = _split_by_zsl_gates(
        rows_calm,
        max_length_tol=float(args.max_length_tol),
        max_angle_tol=float(args.max_angle_tol),
    )

    # Extract Hencky max principal arrays
    zsl_eps = _extract_max_principal(rows_zsl, percent=bool(args.percent))
    calm_eps = _extract_max_principal(rows_calm, percent=bool(args.percent))
    calm_pass_eps = _extract_max_principal(calm_pass, percent=bool(args.percent))
    calm_fail_eps = _extract_max_principal(calm_fail, percent=bool(args.percent))

    outdir = Path(args.outdir)

    # CSV dumps
    if args.dump_csv:
        _dump_csv(
            outdir / f"hencky_hist_{args.pair}_area_{float(args.max_area):g}_pymatgen_zsl.csv",
            rows_zsl,
        )
        _dump_csv(
            outdir / f"hencky_hist_{args.pair}_area_{float(args.max_area):g}_calm.csv",
            rows_calm,
        )

    # Plots
    _plot_hist_overlay(
        pair=str(args.pair),
        max_area=float(args.max_area),
        data_zsl=zsl_eps,
        data_calm=calm_eps,
        epsilon_max=float(args.epsilon_max),
        percent=bool(args.percent),
        density=bool(args.density),
        bins=int(args.bins),
        outdir=outdir,
        formats=str(args.formats),
        no_title=bool(args.no_title),
    )

    _plot_hist_calm_split(
        pair=str(args.pair),
        max_area=float(args.max_area),
        data_pass=calm_pass_eps,
        data_fail=calm_fail_eps,
        epsilon_max=float(args.epsilon_max),
        percent=bool(args.percent),
        density=bool(args.density),
        bins=int(args.bins),
        outdir=outdir,
        formats=str(args.formats),
        no_title=bool(args.no_title),
        max_angle_tol=float(args.max_angle_tol),
    )

    # Console summary
    print("=== Hencky histogram ===")
    print(f"pair={args.pair}  max_area={float(args.max_area):g}")
    print(f"pymatgen_zsl: n={len(rows_zsl)} (len_tol={args.max_length_tol}, angle_tol={args.max_angle_tol})")
    print(f"calm:        n={len(rows_calm)} (epsilon_max={args.epsilon_max}, tau_max={args.tau_max})")
    print()
    print("Overlap diagnostics")
    print(f"  calm matches that also pass ZSL gates: {len(calm_pass)} / {len(rows_calm)}")
    print(f"  calm matches that fail ZSL gates:      {len(calm_fail)} / {len(rows_calm)}")

    # ZSL -> CALM feasibility
    zsl_pass_calm = 0
    for r in rows_zsl:
        try:
            eps = float(r.get("max_abs_principal_strain"))
            tau = abs(float(r.get("log_area_ratio")))
        except Exception:
            continue
        if (eps <= float(args.epsilon_max) + 1e-12) and (tau <= float(args.tau_max) + 1e-12):
            zsl_pass_calm += 1

    print(f"  ZSL matches that pass the CALM strain bound and tau reporting filter: {zsl_pass_calm} / {len(rows_zsl)}")

    if args.dump_csv:
        print(f"Wrote CSV: {outdir / f'hencky_hist_{args.pair}_area_{float(args.max_area):g}_pymatgen_zsl.csv'}")
        print(f"Wrote CSV: {outdir / f'hencky_hist_{args.pair}_area_{float(args.max_area):g}_calm.csv'}")

    print(f"Wrote overlay plot base: {outdir / f'hencky_hist_overlay_{args.pair}_area_{float(args.max_area):g}.*'}")
    print(f"Wrote split plot base:   {outdir / f'hencky_hist_calm_split_{args.pair}_area_{float(args.max_area):g}.*'}")


if __name__ == "__main__":
    main()
