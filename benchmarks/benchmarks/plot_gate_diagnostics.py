"""benchmarks.plot_gate_diagnostics

Gate-diagnostic scatter plot for comparing CALM vs pymatgen ZSL.

This plot is intended for *publication-quality* figures:

- CALM points are rendered with high transparency so they do not obscure other
  methods.
- pymatgen points are rendered on top (higher z-order) so discrepancies remain
  visible.
- Optional percent scaling makes the gates interpretable (e.g., 0.03 -> 3%).

The x-axis is the Zur–McGill / ZSL reduced-angle mismatch
    rel_dgamma = |Δγ| / mean(γ)

The y-axis is the CALM intrinsic gate
    max_abs_principal_strain = max_i |ε_{H,i}|

Both quantities are dimensionless. With --percent, they are multiplied by 100.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

from .common_metrics import load_csv, filter_rows


def _configure_matplotlib(*, paper: bool = True) -> None:
    """Apply a small set of rcParams that tend to work well for papers."""
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


def _extract_xy(rows: List[dict]) -> Tuple[np.ndarray, np.ndarray]:
    """Extract (rel_dgamma, max_abs_principal_strain) arrays from CSV rows."""
    x = np.array([float(r.get("rel_dgamma", "nan")) for r in rows], dtype=float)
    y = np.array([float(r.get("max_abs_principal_strain", "nan")) for r in rows], dtype=float)

    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _save_fig_multi(fig: plt.Figure, outbase: Path, formats: str) -> None:
    """Save to one or more formats, e.g. 'png,pdf'."""
    fmts = [f.strip().lower() for f in formats.split(",") if f.strip()]
    if not fmts:
        fmts = ["png"]

    outbase.parent.mkdir(parents=True, exist_ok=True)
    for fmt in fmts:
        fig.savefig(outbase.with_suffix(f".{fmt}"), bbox_inches="tight")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pymatgen", required=True, help="CSV from benchmarks.run_pymatgen_zsl")
    ap.add_argument("--calm", required=True, help="CSV from benchmarks.run_calm")
    ap.add_argument("--pair", required=True)
    ap.add_argument("--max-area", type=float, required=True)

    ap.add_argument("--max-angle-tol", type=float, default=0.01)
    ap.add_argument("--eps-principal-max", type=float, default=0.03)

    ap.add_argument("--outdir", default="figs")
    ap.add_argument("--formats", default="png", help="Comma-separated formats, e.g. png,pdf")

    ap.add_argument(
        "--percent",
        action="store_true",
        help="Scale both axes by 100 and label as percent.",
    )

    ap.add_argument("--alpha-calm", type=float, default=0.22)
    ap.add_argument("--alpha-pymatgen", type=float, default=0.75)
    ap.add_argument("--s-calm", type=float, default=16.0)
    ap.add_argument("--s-pymatgen", type=float, default=20.0)

    ap.add_argument(
        "--paper-style",
        action="store_true",
        help="Use paper-oriented matplotlib rcParams.",
    )
    ap.add_argument(
        "--no-title",
        action="store_true",
        help="Do not add a title (useful when composing multi-panel figures).",
    )

    args = ap.parse_args()

    _configure_matplotlib(paper=bool(args.paper_style))

    rows_zsl = filter_rows(load_csv(args.pymatgen), pair=args.pair, max_area=float(args.max_area))
    rows_calm = filter_rows(load_csv(args.calm), pair=args.pair, max_area=float(args.max_area))

    x_zsl, y_zsl = _extract_xy(rows_zsl)
    x_calm, y_calm = _extract_xy(rows_calm)

    scale = 100.0 if bool(args.percent) else 1.0
    x_zsl *= scale
    y_zsl *= scale
    x_calm *= scale
    y_calm *= scale

    vline = float(args.max_angle_tol) * scale
    hline = float(args.eps_principal_max) * scale

    fig, ax = plt.subplots(figsize=(4.2, 3.2))

    # Draw CALM first (more points), then pymatgen on top.
    # Use explicit C0/C1 so colors remain stable regardless of draw order.
    ax.scatter(
        x_calm,
        y_calm,
        s=float(args.s_calm),
        alpha=float(args.alpha_calm),
        label=f"calm (n={len(x_calm)})",
        color="C1",
        edgecolors="none",
        rasterized=True,
        zorder=2,
    )
    ax.scatter(
        x_zsl,
        y_zsl,
        s=float(args.s_pymatgen),
        alpha=float(args.alpha_pymatgen),
        label=f"pymatgen_zsl (n={len(x_zsl)})",
        color="C0",
        edgecolors="none",
        rasterized=True,
        zorder=3,
    )

    ax.axvline(vline, linestyle="--", linewidth=1.2, zorder=1)
    ax.axhline(hline, linestyle="--", linewidth=1.2, zorder=1)

    if not args.no_title:
        ax.set_title(f"Gate diagnostics: {args.pair} @ max_area={float(args.max_area):g}")

    if args.percent:
        ax.set_xlabel(r"$|\Delta\gamma|/\bar{\gamma}$ (%)")
        ax.set_ylabel(r"$\max_i |\varepsilon_{H,i}|$ (%)")
    else:
        ax.set_xlabel(r"$|\Delta\gamma|/\bar{\gamma}$")
        ax.set_ylabel(r"$\max_i |\varepsilon_{H,i}|$")

    ax.set_xlim(left=0.0)
    ax.set_ylim(bottom=0.0)

    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.legend(frameon=False, loc="upper right")

    outdir = Path(args.outdir)
    outbase = outdir / f"gate_diag_rel_dgamma_vs_principal_{args.pair}_area_{float(args.max_area):g}"
    _save_fig_multi(fig, outbase, str(args.formats))

    plt.close(fig)


if __name__ == "__main__":
    main()
