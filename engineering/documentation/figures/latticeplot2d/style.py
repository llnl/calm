"""Publication-oriented Matplotlib styles for lattice figures."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Literal

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

MM_TO_INCH = 1.0 / 25.4

FIGURE_WIDTHS_MM = {
    "single": 89.0,
    "double": 183.0,
}

MAX_FIGURE_HEIGHT_MM = 170.0

# Colorblind-accessible palette suitable for scientific figures.
COLORS = {
    "black": "#000000",
    "gray": "#666666",
    "light_gray": "#B3B3B3",
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "reddish_purple": "#CC79A7",
}

NPJ_RCPARAMS = {
    # Typography
    "font.family": "sans-serif",
    "font.sans-serif": [
        "Arial",
        "Helvetica",
        "Liberation Sans",
        "DejaVu Sans",
    ],
    "font.size": 8.0,
    "axes.labelsize": 8.0,
    "axes.titlesize": 8.0,
    "xtick.labelsize": 8.0,
    "ytick.labelsize": 8.0,
    "legend.fontsize": 8.0,
    "mathtext.fontset": "dejavusans",
    # Axes and ticks
    "axes.linewidth": 1.0,
    "axes.grid": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 1.0,
    "ytick.major.width": 1.0,
    "xtick.major.size": 3.0,
    "ytick.major.size": 3.0,
    "xtick.minor.width": 1.0,
    "ytick.minor.width": 1.0,
    "xtick.minor.size": 1.5,
    "ytick.minor.size": 1.5,
    # Lines, markers, and patches
    "lines.linewidth": 1.0,
    "lines.markersize": 5.0,
    "patch.linewidth": 1.0,
    # Legends
    "legend.frameon": False,
    "legend.handlelength": 2.0,
    "legend.handletextpad": 0.5,
    "legend.borderaxespad": 0.4,
    # Background and export
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
}


@contextmanager
def npj_style() -> Iterator[None]:
    """Temporarily apply the latticeplot2d publication style."""
    with mpl.rc_context(NPJ_RCPARAMS):
        yield


def figure_size(
    column: Literal["single", "double"] = "single",
    *,
    height_ratio: float = 1.0,
) -> tuple[float, float]:
    """Return a publication-sized ``(width, height)`` tuple in inches."""
    if column not in FIGURE_WIDTHS_MM:
        allowed = ", ".join(repr(value) for value in FIGURE_WIDTHS_MM)
        raise ValueError(f"column must be one of {allowed}.")

    if not 0.0 < height_ratio:
        raise ValueError("height_ratio must be positive.")

    width_mm = FIGURE_WIDTHS_MM[column]
    height_mm = width_mm * height_ratio

    if height_mm > MAX_FIGURE_HEIGHT_MM:
        raise ValueError(
            f"Requested height is {height_mm:.1f} mm, which exceeds "
            f"the {MAX_FIGURE_HEIGHT_MM:.0f} mm maximum."
        )

    return width_mm * MM_TO_INCH, height_mm * MM_TO_INCH


def npj_figure(
    column: Literal["single", "double"] = "single",
    *,
    height_ratio: float = 1.0,
    constrained_layout: bool = True,
) -> tuple[Figure, Axes]:
    """Create a publication-sized Matplotlib figure and one axes."""
    layout = "constrained" if constrained_layout else None
    return plt.subplots(
        figsize=figure_size(column, height_ratio=height_ratio),
        layout=layout,
    )


def add_panel_label(
    ax: Axes,
    label: str,
    *,
    x: float = -0.13,
    y: float = 1.02,
) -> None:
    """Add a bold panel label in axes coordinates."""
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.0,
        fontweight="bold",
        color="black",
        clip_on=False,
    )
