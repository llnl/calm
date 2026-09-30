"""benchmarks.figure_hencky_triptych

Generate a *single*, publication-ready 3-panel figure for the Hencky-strain
experiment:

(a) Histogram overlay of max |Hencky principal strain| for all ZSL matches and
    all CALM matches.
(b) Histogram of CALM matches split by whether they pass the ZSL (rel_da, rel_db,
    rel_dgamma) gates.
(c) Gate diagnostics scatter: rel_dgamma vs max |Hencky principal strain|,
    showing the ZSL angle gate (vertical) and CALM strain gate (horizontal).

This script is designed to produce the exact panel set shown in the draft figure,
but with improved layering/transparency and more publication-friendly aesthetics.

Example
-------
python -m benchmarks.figure_hencky_triptych \
  --pair oblique_tradeoff \
  --max-area 400 \
  --max-length-tol 0.03 \
  --max-angle-tol 0.01 \
  --epsilon-max 0.03 \
  --tau-max 0.06 \
  --percent --density \
  --outdir figs \
  --formats png,pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Tuple

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from .benchmark_pairs import get_benchmark_pair
from .run_pymatgen_zsl import run_zsl_for_pair
from .run_calm import run_calm_for_pair


def _configure_matplotlib(paper: bool = True) -> None:
    if not paper:
        return
    mpl.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            # Export at high DPI by default (PNG). PDF remains vector.
            "savefig.dpi": 600,
            # Keep grid light when enabled.
            "grid.linewidth": 0.5,
            "grid.alpha": 0.25,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def _method_colors() -> Tuple[str, str]:
    """Return (color_zsl, color_calm) using matplotlib's default color cycle.

    We use the first two entries of the active axes color cycle to keep the
    method colors consistent across panels, irrespective of call ordering.
    """

    colors = mpl.rcParams.get("axes.prop_cycle", None)
    if colors is None:
        return ("C0", "C1")

    seq = colors.by_key().get("color", [])
    if len(seq) >= 2:
        return (str(seq[0]), str(seq[1]))
    if len(seq) == 1:
        return (str(seq[0]), "C1")
    return ("C0", "C1")


def _style_axis(ax: plt.Axes) -> None:
    """Apply a light, publication-friendly axis style."""

    # Minimal spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.8)
    ax.set_axisbelow(True)


def _split_by_zsl_gates(rows: List[dict], *, max_length_tol: float, max_angle_tol: float) -> Tuple[List[dict], List[dict]]:
    """Split rows into (pass, fail) by ZSL-style gates."""
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
        if (rel_da <= max_length_tol + 1e-15) and (rel_db <= max_length_tol + 1e-15) and (rel_dg <= max_angle_tol + 1e-15):
            passed.append(r)
        else:
            failed.append(r)
    return passed, failed


def _extract_max_principal(rows: List[dict]) -> np.ndarray:
    out: List[float] = []
    for r in rows:
        try:
            out.append(float(r.get("max_abs_principal_strain")))
        except Exception:
            continue
    arr = np.asarray(out, dtype=float)
    return arr[np.isfinite(arr)]


def _extract_gate_xy(rows: List[dict]) -> Tuple[np.ndarray, np.ndarray]:
    xs: List[float] = []
    ys: List[float] = []
    for r in rows:
        try:
            xs.append(float(r.get("rel_dgamma")))
            ys.append(float(r.get("max_abs_principal_strain")))
        except Exception:
            continue
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    return x[ok], y[ok]


def _save_multi(fig: plt.Figure, outbase: Path, formats: str) -> None:
    outbase.parent.mkdir(parents=True, exist_ok=True)
    fmts = [f.strip().lower() for f in formats.split(",") if f.strip()]
    if not fmts:
        fmts = ["png"]
    for ext in fmts:
        save_kw = {"bbox_inches": "tight"}
        # Prefer high resolution for raster formats.
        if ext in {"png", "jpg", "jpeg", "tif", "tiff"}:
            save_kw["dpi"] = 600
        fig.savefig(outbase.with_suffix("." + ext), **save_kw)


def _panel_label(ax: plt.Axes, label: str) -> None:
    """Add an (a)/(b)/(c) panel label in the upper-left corner."""
    ax.text(
        0.01,
        0.99,
        f"{label})",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontweight="bold",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 0.4},
    )


def _annotate_vline(
    ax: plt.Axes,
    x: float,
    text: str,
    *,
    color: str = "0.2",
    fontsize: float = 8.0,
    dx_points: float = 3.0,
    dy_points: float = -2.0,
) -> None:
    """Annotate a vertical threshold line with rotated text.

    Notes
    -----
    We intentionally keep this out of the legend to avoid a third legend row
    (panels a/b), which tends to dominate the small subplot area.
    """
    # Place the text at the top of the current y-range with a small inboard offset.
    y_top = ax.get_ylim()[1]
    ax.annotate(
        text,
        xy=(float(x), float(y_top)),
        xycoords=("data", "data"),
        xytext=(float(dx_points), float(dy_points)),
        textcoords="offset points",
        rotation=90,
        ha="left",
        va="top",
        color=color,
        fontsize=float(fontsize),
    )


def main() -> None:
    ap = argparse.ArgumentParser()

    ap.add_argument("--pair", required=True)
    ap.add_argument("--max-area", type=float, required=True)

    ap.add_argument("--max-length-tol", type=float, default=0.03)
    ap.add_argument("--max-angle-tol", type=float, default=0.01)
    ap.add_argument("--max-area-ratio-tol", type=float, default=0.09,
                    help="ZSL max_area_ratio_tol parameter (area ratio mismatch tolerance).")

    ap.add_argument("--epsilon-max", type=float, default=0.03)
    ap.add_argument("--tau-max", type=float, default=0.06)

    ap.add_argument("--cond-max", type=float, default=1e6)
    ap.add_argument("--niggli-tol", type=float, default=1e-12)
    ap.add_argument("--nA-prim", type=int, default=1)
    ap.add_argument("--nB-prim", type=int, default=1)
    ap.add_argument("--N-at-max", type=int, default=1000)
    ap.add_argument("--w-match", type=float, default=1.0)

    ap.add_argument("--bins", type=int, default=40)
    ap.add_argument("--density", action="store_true")
    ap.add_argument("--percent", action="store_true", help="Plot x/y strain axes in percent (×100).")

    ap.add_argument("--outdir", default="figs")
    ap.add_argument("--formats", default="png", help="Comma-separated formats, e.g. png,pdf")

    ap.add_argument("--paper-style", action="store_true")
    ap.add_argument("--no-title", action="store_true")
    ap.add_argument(
        "--panel-labels",
        action="store_true",
        help="Add a), b), c) panel labels (off by default for publication figures).",
    )

    # Plot-tuning knobs
    # Scatter opacity: CALM is typically the denser point cloud, so keep it
    # fairly translucent by default to preserve visibility of overlapping
    # ZSL points (and the gate lines) in the same region.
    ap.add_argument("--alpha-calm", type=float, default=0.25)
    ap.add_argument("--alpha-pymatgen", type=float, default=0.65)
    ap.add_argument("--s-calm", type=float, default=12.0)
    ap.add_argument("--s-pymatgen", type=float, default=14.0)

    args = ap.parse_args()

    _configure_matplotlib(paper=bool(args.paper_style))

    pair_cfg = get_benchmark_pair(str(args.pair))

    # NOTE: run_zsl_for_pair expects the 2×2 in-plane bases as A2/B2
    # (columns are lattice vectors). The benchmark pair stores these as
    # pair_cfg.A and pair_cfg.B.
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
        sig_tol=float(args.niggli_tol),
        sig_scale=1e10,
        debug=False,
    )

    rows_calm = run_calm_for_pair(
        pair_name=str(args.pair),
        A2=pair_cfg.A,
        B2=pair_cfg.B,
        max_area=float(args.max_area),
        eps_principal_max=float(args.epsilon_max),
        tau_max=float(args.tau_max),
        cond_max=float(args.cond_max),
        nA_prim=int(args.nA_prim),
        nB_prim=int(args.nB_prim),
        N_at_max=int(args.N_at_max),
        w_match=float(args.w_match),
        sig_tol=float(args.niggli_tol),
        sig_scale=1e10,
        debug=False,
    )

    calm_pass, calm_fail = _split_by_zsl_gates(
        rows_calm,
        max_length_tol=float(args.max_length_tol),
        max_angle_tol=float(args.max_angle_tol),
    )

    # Extract arrays
    zsl_eps = _extract_max_principal(rows_zsl)
    calm_eps = _extract_max_principal(rows_calm)
    calm_pass_eps = _extract_max_principal(calm_pass)
    calm_fail_eps = _extract_max_principal(calm_fail)

    x_zsl, y_zsl = _extract_gate_xy(rows_zsl)
    x_calm, y_calm = _extract_gate_xy(rows_calm)

    scale = 100.0 if args.percent else 1.0

    # Histogram axes in percent are typically more interpretable
    zsl_eps_p = zsl_eps * scale
    calm_eps_p = calm_eps * scale
    calm_pass_eps_p = calm_pass_eps * scale
    calm_fail_eps_p = calm_fail_eps * scale

    # Scatter axes (also scaled if requested)
    x_zsl_p = x_zsl * scale
    x_calm_p = x_calm * scale
    y_zsl_p = y_zsl * scale
    y_calm_p = y_calm * scale

    eps_line = float(args.epsilon_max) * scale
    dg_line = float(args.max_angle_tol) * scale

    # Keep the epsilon label TeX-safe (place the percent sign inside math mode).
    if args.percent:
        eps_label = fr"$\varepsilon_{{\max}}={eps_line:g}\%$"
    else:
        eps_label = fr"$\varepsilon_{{\max}}={eps_line:g}$"

    # Shared histogram bins
    all_eps = np.concatenate([zsl_eps_p, calm_eps_p]) if (
        zsl_eps_p.size and calm_eps_p.size) else (zsl_eps_p if zsl_eps_p.size else calm_eps_p)
    if all_eps.size:
        lo = float(max(0.0, np.min(all_eps) - 0.02 * scale))
        hi = float(max(eps_line, np.max(all_eps)) + 0.02 * scale)
    else:
        lo, hi = 0.0, eps_line * 1.2

    bins = np.linspace(lo, hi, int(args.bins) + 1)

    # --- Figure
    # Slightly taller than a default 1x3 strip so axis labels and legends
    # have breathing room when exported at journal-ready DPI.
    # Slightly taller than a 1×3 strip so legends can sit *above* each panel
    # without crowding the plotting area.
    fig = plt.figure(figsize=(10.4, 3.6), constrained_layout=True)

    # Reserve top margin for a figure-level legend so it never overlaps the axes.
    try:
        fig.get_layout_engine().set(rect=(0, 0, 1, 0.88))  # (left, bottom, right, top)
    except Exception:
        # Older Matplotlib: no-op; you can alternatively increase figsize[1] slightly.
        pass

    # Give scatter a bit more width than the histogram
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.25])

    ax0 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    # (a) overlay
    ax0.hist(
        zsl_eps_p,
        bins=bins,
        density=bool(args.density),
        histtype="step",
        linewidth=1.5,
        color="C0",
        label="_nolegend_",
    )
    ax0.hist(
        calm_eps_p,
        bins=bins,
        density=bool(args.density),
        histtype="stepfilled",
        alpha=0.35,
        color="C1",
        label="_nolegend_",
    )
    ax0.axvline(eps_line, linestyle="--", linewidth=1.2, color="0.2", label="_nolegend_")

    ax0.set_xlabel("max |Principal strain|" + (" (%)" if args.percent else ""))
    ax0.set_ylabel("density" if args.density else "count")
    ax0.grid(True, axis="y", alpha=0.22, linewidth=0.6)

    # Harmonize histogram y-limits for visual comparison.
    y_max = ax0.get_ylim()[1]
    ax0.set_ylim(0.0, y_max)

    # --- Legends (panels a/b)
    # Use compact, custom handles so the legends are shorter and do not include
    # the vertical epsilon threshold line (which is labeled directly instead).
    # Place legends *above* each axis to avoid obscuring the data.
    leg_kw = dict(
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.02),
        borderaxespad=0.0,
        handlelength=1.6,
        handletextpad=0.5,
        labelspacing=0.25,
    )

    # Label the epsilon cutoff line directly (cleaner than legend entries).
    _annotate_vline(ax0, eps_line, eps_label)

    # --- Single shared legend for the whole figure (patches only)
    zsl_color, calm_color = _method_colors()

    handles = [
        Patch(facecolor=zsl_color, edgecolor="none", alpha=0.35, label=f"ZSL (n={len(rows_zsl):,})"),
        Patch(facecolor=calm_color, edgecolor="none", alpha=0.35, label=f"CALM (n={len(rows_calm):,})"),
    ]

    fig_leg = fig.legend(
        handles=handles,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.06),  # was ~1.02; push it up
        ncol=2,
        columnspacing=1.0,
        handlelength=1.6,
        handletextpad=0.5,
        labelspacing=0.25,
    )
    fig_leg.set_in_layout(True)

    # (c) scatter gate diagnostics
    # Draw CALM first and lightly, then pymatgen on top. Use hollow markers
    # for pymatgen to keep CALM points visible in the overlap region.
    ax2.scatter(
        x_calm_p,
        y_calm_p,
        s=float(args.s_calm),
        alpha=float(args.alpha_calm),
        color="C1",
        edgecolors="none",
        rasterized=True,
        label=f"CALM (n={len(rows_calm)})",
        zorder=2,
    )
    ax2.scatter(
        x_zsl_p,
        y_zsl_p,
        s=float(args.s_pymatgen),
        alpha=float(args.alpha_pymatgen),
        facecolors="none",
        edgecolors="C0",
        linewidths=0.5,
        rasterized=True,
        label=f"pymatgen-ZSL (n={len(rows_zsl)})",
        zorder=3,
    )

    ax2.axvline(dg_line, linestyle="--", linewidth=1.1, color="0.2")
    ax2.axhline(eps_line, linestyle="--", linewidth=1.1, color="0.2")

    ax2.set_xlabel(r"$|\Delta\gamma|/\bar{\gamma}$" + (" (%)" if args.percent else ""))
    ax2.set_ylabel(r"max |Principal strain|" + (" (%)" if args.percent else ""))
    ax2.grid(True, alpha=0.22, linewidth=0.6)

    # Consistent axis styling (spines/ticks). Applied after all artists are added.
    for ax in (ax0, ax2):
        _style_axis(ax)

    # Optional panel labels (disabled by default for publication-ready plots).
    if args.panel_labels:
        for ax, lab in ((ax0, "a"), (ax2, "b")):
            _panel_label(ax, lab)

    # if not args.no_title:
    #     fig.suptitle(
    #         f"Hencky strain gates: {args.pair}  (max_area={float(args.max_area):g})",
    #         y=1.02,
    #     )

    outdir = Path(args.outdir)
    outbase = outdir / f"hencky_triptych_{args.pair}_area_{float(args.max_area):g}"
    _save_multi(fig, outbase, str(args.formats))
    plt.close(fig)

    print(f"Wrote: {outbase}.[{args.formats}]")


if __name__ == "__main__":
    main()
