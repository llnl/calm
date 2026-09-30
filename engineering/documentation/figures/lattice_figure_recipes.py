"""Figure recipes built with CALM's vendored latticeplot2d tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
from numpy.typing import NDArray

_TOOL_ROOT = Path(__file__).resolve().parent
if str(_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_ROOT))

import latticeplot2d  # noqa: E402
from latticeplot2d import (  # noqa: E402
    COLORS,
    StrainPartitionFrame,
    add_panel_label,
    center_on_cell,
    npj_style,
    plot_coupled_match,
    plot_hnf_orbit_gallery,
    plot_lattice,
    plot_reduction_sequence,
    plot_sites,
    plot_strain_partition_path,
)

_EXPECTED_VENDOR_ROOT = (_TOOL_ROOT / "latticeplot2d").resolve()
_MODULE_PATH = Path(latticeplot2d.__file__).resolve()
if not _MODULE_PATH.is_relative_to(_EXPECTED_VENDOR_ROOT):
    raise RuntimeError(
        "CALM lattice figure recipes must use the vendored latticeplot2d tool; "
        f"loaded {_MODULE_PATH}"
    )

FloatMatrix = NDArray[np.float64]


@dataclass(frozen=True)
class FigureRecipe:
    """One named documentation figure and its accessibility metadata."""

    name: str
    title: str
    description: str
    build: Callable[[], Figure]
    published: bool = True

    @property
    def filename(self) -> str:
        """Return the committed SVG filename."""

        return f"{self.name}.svg"


def _rotation(theta_deg: float) -> FloatMatrix:
    theta = np.deg2rad(theta_deg)
    return np.array(
        [
            [np.cos(theta), -np.sin(theta)],
            [np.sin(theta), np.cos(theta)],
        ],
        dtype=float,
    )


def _draw_basis_arrows(
    ax: plt.Axes,
    basis: FloatMatrix,
    *,
    color: str,
) -> None:
    labels = (r"$\mathbf{a}_1$", r"$\mathbf{a}_2$")
    offsets = ((0.04, -0.08), (-0.09, 0.04))
    for vector, label, offset in zip(
        basis.T,
        labels,
        offsets,
        strict=True,
    ):
        ax.annotate(
            "",
            xy=vector,
            xytext=(0.0, 0.0),
            arrowprops={
                "arrowstyle": "-|>",
                "color": color,
                "lw": 1.3,
                "shrinkA": 0,
                "shrinkB": 0,
            },
            zorder=7,
        )
        ax.text(
            vector[0] + offset[0],
            vector[1] + offset[1],
            label,
            color=color,
            fontsize=8,
            ha="center",
            va="center",
            zorder=8,
        )


def _configure_panel(ax: plt.Axes) -> None:
    ax.set_aspect("equal", adjustable="box")
    ax.set_axis_off()


def _matrix_power_spd(matrix: FloatMatrix, exponent: float) -> FloatMatrix:
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    return (eigenvectors * (eigenvalues**exponent)) @ eigenvectors.T


def _affine_metric_path(
    cell_a: FloatMatrix,
    cell_b: FloatMatrix,
    alpha: float,
) -> FloatMatrix:
    metric_a = cell_a.T @ cell_a
    metric_b = cell_b.T @ cell_b
    root_a = _matrix_power_spd(metric_a, 0.5)
    inverse_root_a = _matrix_power_spd(metric_a, -0.5)
    relative_metric = inverse_root_a @ metric_b @ inverse_root_a
    metric_alpha = (
        root_a @ _matrix_power_spd(relative_metric, alpha) @ root_a
    )
    lower_cholesky = np.linalg.cholesky(metric_alpha)
    return lower_cholesky.T


def build_cell_map_types() -> Figure:
    """Compare basis changes, rigid gauges, and physical deformation."""

    basis = np.array([[1.0, 0.34], [0.0, 0.90]], dtype=float)
    unimodular = np.array([[1, 1], [0, 1]], dtype=int)
    relabeled_basis = basis @ unimodular
    gauge = _rotation(28.0)
    gauged_basis = gauge @ basis
    deformation = np.array([[1.16, 0.16], [0.02, 0.86]], dtype=float)
    deformed_basis = deformation @ gauged_basis

    with npj_style():
        figure, axes = plt.subplots(
            1,
            4,
            figsize=(11.4, 3.0),
            layout="constrained",
        )
        states = (
            (
                basis,
                basis,
                COLORS["blue"],
                "Original representation",
                "cell and lattice sites",
            ),
            (
                relabeled_basis,
                basis,
                COLORS["orange"],
                "Integer basis change",
                r"$\mathbf{A}'=\mathbf{A}\mathbf{P}$; same lattice",
            ),
            (
                gauged_basis,
                gauged_basis,
                COLORS["bluish_green"],
                "Rigid gauge rotation",
                r"$\mathbf{A}'=\mathbf{G}\mathbf{A}$; no strain",
            ),
            (
                deformed_basis,
                deformed_basis,
                COLORS["vermillion"],
                "Physical deformation",
                r"$\mathbf{A}'=\mathbf{F}\mathbf{A}$; metric changes",
            ),
        )
        for index, (cell_basis, site_basis, color, title, subtitle) in enumerate(
            states
        ):
            axis = axes[index]
            plot_lattice(
                axis,
                grid_basis=cell_basis,
                site_basis=site_basis,
                cell_basis=cell_basis,
                grid_i_range=(-3, 3),
                grid_j_range=(-3, 3),
                site_i_range=(-5, 5),
                site_j_range=(-5, 5),
                color=color,
                grid_linewidth=0.75,
                grid_alpha=0.30,
                site_size=13,
                site_edgecolor="white",
                site_linewidth=0.35,
                fill_alpha=0.12,
                cell_linewidth=1.7,
            )
            _draw_basis_arrows(axis, cell_basis, color=color)
            center_on_cell(axis, cell_basis, half_width=1.75)
            _configure_panel(axis)
            axis.set_title(title, fontweight="bold", pad=8)
            axis.text(
                0.5,
                -0.02,
                subtitle,
                transform=axis.transAxes,
                ha="center",
                va="top",
                fontsize=7.3,
            )
            add_panel_label(
                axis,
                chr(ord("a") + index),
                x=-0.03,
                y=1.03,
            )
        figure.suptitle(
            "Cell matrices can change for different mathematical reasons",
            fontsize=10,
            fontweight="bold",
        )
        return figure


def build_gauss_reduction_sequence() -> Figure:
    """Show equivalent generators before and after Gauss reduction."""

    primitive = np.array([[1.0, 0.28], [0.0, 0.90]], dtype=float)
    integer_transform = np.array([[4, -3], [1, 1]], dtype=int)
    enumerated_basis = primitive @ integer_transform

    with npj_style():
        result = plot_reduction_sequence(
            enumerated_basis,
            primitive,
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-8, 8),
            site_j_range=(-8, 8),
            titles=(
                "Enumerated basis",
                "Equivalent reduced basis",
                "Right-handed common gauge",
            ),
            figsize=(10.5, 3.2),
        )
        for index, axis in enumerate(result.axes):
            add_panel_label(
                axis,
                chr(ord("a") + index),
                x=-0.04,
                y=1.03,
            )
        result.figure.suptitle(
            "Gauss reduction changes the generators, not the lattice",
            fontsize=10,
            fontweight="bold",
        )
        return result.figure


def build_hnf_orbit_reduction() -> Figure:
    """Group index-two HNF embeddings by square-net symmetry."""

    primitive = np.eye(2, dtype=float)
    members = (
        np.array([[2, 0], [0, 1]], dtype=int),
        np.array([[1, 0], [0, 2]], dtype=int),
        np.array([[2, 1], [0, 1]], dtype=int),
    )
    orbit_labels = ("rectangular", "rectangular", "diagonal")
    member_labels = (r"$H_x$", r"$H_y$", r"$H_d$")
    orbit_colors = {
        "rectangular": COLORS["blue"],
        "diagonal": COLORS["orange"],
    }

    with npj_style():
        result = plot_hnf_orbit_gallery(
            primitive,
            members,
            orbit_labels,
            member_labels=member_labels,
            ncols=3,
            orbit_colors=orbit_colors,
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-6, 6),
            site_j_range=(-6, 6),
            figsize=(10.5, 6.0),
        )
        for axis, artist, member, orbit in zip(
            result.member_axes,
            result.member_artists,
            members,
            orbit_labels,
            strict=True,
        ):
            if artist.sites is None:
                raise RuntimeError("HNF member panel did not create lattice sites")
            artist.sites.set_facecolor(COLORS["light_gray"])
            artist.sites.set_edgecolor("white")
            artist.sites.set_alpha(0.65)
            plot_sites(
                axis,
                primitive @ member,
                i_range=(-4, 4),
                j_range=(-4, 4),
                color=orbit_colors[orbit],
                size=30,
                edgecolor="white",
                linewidth=0.55,
                zorder=6,
            )
        for axis, orbit in zip(
            result.representative_axes,
            result.orbit_order,
            strict=True,
        ):
            plot_sites(
                axis,
                result.reductions[orbit].gauged_basis,
                i_range=(-4, 4),
                j_range=(-4, 4),
                color=orbit_colors[orbit],
                size=30,
                edgecolor="white",
                linewidth=0.55,
                zorder=6,
            )
        result.figure.text(
            0.012,
            0.74,
            "Exact HNF embeddings",
            rotation=90,
            va="center",
            ha="left",
            fontsize=8,
            fontweight="bold",
        )
        result.figure.text(
            0.012,
            0.27,
            "One gauged representative per orbit",
            rotation=90,
            va="center",
            ha="left",
            fontsize=8,
            fontweight="bold",
        )
        result.figure.suptitle(
            "HNF enumerates sublattices; symmetry groups equivalent members",
            fontsize=10,
            fontweight="bold",
        )
        return result.figure


def build_coupled_common_cell() -> Figure:
    """Show two surface candidates mapped into one coupled common cell."""

    primitive_a = np.array([[1.0, 0.22], [0.0, 0.94]], dtype=float)
    primitive_b = _rotation(7.0) @ np.array(
        [[1.03, 0.16], [0.0, 0.91]],
        dtype=float,
    )
    transform_a = np.array([[2, -1], [1, 2]], dtype=int)
    transform_b = np.array([[1, -2], [2, 1]], dtype=int)
    supercell_a = primitive_a @ transform_a
    supercell_b = primitive_b @ transform_b

    with npj_style():
        figure, axes = plt.subplots(
            1,
            3,
            figsize=(10.5, 3.3),
            layout="constrained",
        )
        plot_lattice(
            axes[0],
            grid_basis=supercell_a,
            site_basis=primitive_a,
            cell_basis=supercell_a,
            color=COLORS["blue"],
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-8, 8),
            site_j_range=(-8, 8),
            grid_alpha=0.35,
            site_size=15,
            site_edgecolor="white",
            site_linewidth=0.4,
            fill_alpha=0.10,
            cell_linewidth=1.6,
        )
        plot_lattice(
            axes[1],
            grid_basis=supercell_b,
            site_basis=primitive_b,
            cell_basis=supercell_b,
            color=COLORS["vermillion"],
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-8, 8),
            site_j_range=(-8, 8),
            grid_alpha=0.35,
            site_size=15,
            site_marker="s",
            site_edgecolor="white",
            site_linewidth=0.4,
            fill_alpha=0.10,
            cell_linewidth=1.6,
        )
        result = plot_coupled_match(
            axes[2],
            primitive_a,
            primitive_b,
            supercell_a,
            supercell_b,
            reference="A",
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-8, 8),
            site_j_range=(-8, 8),
            common_color=COLORS["black"],
            color_a=COLORS["blue"],
            color_b=COLORS["vermillion"],
            site_size_a=16,
            site_size_b=14,
        )
        cells = (supercell_a, supercell_b, result.common_basis)
        titles = (
            "Surface A candidate",
            "Surface B candidate",
            "Coupled common cell",
        )
        subtitles = (
            "primitive A sites and A supercell",
            "primitive B sites and B supercell",
            "one right relabeling; two Cartesian maps",
        )
        for index, (axis, cell, title, subtitle) in enumerate(
            zip(axes, cells, titles, subtitles, strict=True)
        ):
            center_on_cell(axis, cell, half_width=2.35)
            _configure_panel(axis)
            axis.set_title(title, fontweight="bold", pad=8)
            axis.text(
                0.5,
                -0.02,
                subtitle,
                transform=axis.transAxes,
                ha="center",
                va="top",
                fontsize=7.3,
            )
            add_panel_label(
                axis,
                chr(ord("a") + index),
                x=-0.03,
                y=1.03,
            )
        axes[2].legend(
            handles=(
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markerfacecolor=COLORS["blue"],
                    markeredgecolor="white",
                    label="A net",
                ),
                Line2D(
                    [0],
                    [0],
                    marker="s",
                    linestyle="none",
                    markerfacecolor=COLORS["vermillion"],
                    markeredgecolor="white",
                    label="B net",
                ),
            ),
            loc="upper right",
            fontsize=7,
        )
        figure.suptitle(
            "A coherent match is one coupled object in a shared cell",
            fontsize=10,
            fontweight="bold",
        )
        return figure


def build_strain_partition_path() -> Figure:
    """Show the common metric moving between two candidate cells."""

    cell_a = np.array([[2.00, 0.42], [0.00, 1.82]], dtype=float)
    cell_b = np.array([[1.86, 0.12], [0.00, 2.06]], dtype=float)
    transform_a = np.array([[2, -1], [1, 2]], dtype=int)
    transform_b = np.array([[1, -2], [2, 1]], dtype=int)
    primitive_a = cell_a @ np.linalg.inv(transform_a)
    primitive_b = cell_b @ np.linalg.inv(transform_b)

    frames: list[StrainPartitionFrame] = []
    frame_specs = (
        (0.0, r"$\alpha=0$; A unstrained"),
        (0.5, r"$\alpha=0.5$; shared strain"),
        (1.0, r"$\alpha=1$; B unstrained"),
    )
    for alpha, label in frame_specs:
        common = _affine_metric_path(cell_a, cell_b, alpha)
        frames.append(
            StrainPartitionFrame(
                alpha=alpha,
                common_basis=common,
                deformation_a=common @ np.linalg.inv(cell_a),
                deformation_b=common @ np.linalg.inv(cell_b),
                label=label,
            )
        )

    with npj_style():
        result = plot_strain_partition_path(
            primitive_a,
            primitive_b,
            frames,
            ncols=3,
            gauge="none",
            grid_i_range=(-2, 2),
            grid_j_range=(-2, 2),
            site_i_range=(-8, 8),
            site_j_range=(-8, 8),
            common_color=COLORS["black"],
            color_a=COLORS["blue"],
            color_b=COLORS["vermillion"],
            figsize=(10.5, 3.3),
        )
        for index, axis in enumerate(result.axes):
            add_panel_label(
                axis,
                chr(ord("a") + index),
                x=-0.03,
                y=1.03,
            )
        result.axes[1].legend(
            handles=(
                Line2D(
                    [0],
                    [0],
                    marker="o",
                    linestyle="none",
                    markerfacecolor=COLORS["blue"],
                    markeredgecolor="white",
                    label="deformed A net",
                ),
                Line2D(
                    [0],
                    [0],
                    marker="s",
                    linestyle="none",
                    markerfacecolor=COLORS["vermillion"],
                    markeredgecolor="white",
                    label="deformed B net",
                ),
                Line2D(
                    [0],
                    [0],
                    color=COLORS["black"],
                    linewidth=1.4,
                    label="target common cell",
                ),
            ),
            loc="upper center",
            bbox_to_anchor=(0.5, -0.03),
            ncol=3,
            fontsize=7,
        )
        result.figure.suptitle(
            "The partition coordinate moves the common metric between candidates",
            fontsize=10,
            fontweight="bold",
        )
        return result.figure


RECIPES: tuple[FigureRecipe, ...] = (
    FigureRecipe(
        name="cell-map-types",
        title="Basis changes, gauge rotations, and physical deformation",
        description=(
            "Four lattice panels compare an original two-dimensional cell, an "
            "integer basis relabeling that preserves the lattice sites, a rigid "
            "Cartesian gauge rotation that preserves the metric, and a physical "
            "deformation that changes the metric and lattice sites."
        ),
        build=build_cell_map_types,
    ),
    FigureRecipe(
        name="gauss-reduction-sequence",
        title="Gauss reduction of equivalent lattice generators",
        description=(
            "Three panels show an awkward enumerated supercell basis, a shorter "
            "Gauss-reduced basis of the same lattice sites, and the final "
            "right-handed common gauge used for deterministic comparison."
        ),
        build=build_gauss_reduction_sequence,
        published=False,
    ),
    FigureRecipe(
        name="hnf-orbit-reduction",
        title="HNF embeddings and square-net symmetry orbits",
        description=(
            "The upper row shows three exact index-two HNF embeddings in a square "
            "surface net. The lower row retains one right-handed representative "
            "for the rectangular symmetry orbit and one for the diagonal parity "
            "orbit."
        ),
        build=build_hnf_orbit_reduction,
        published=False,
    ),
    FigureRecipe(
        name="coupled-common-cell",
        title="Two surface candidates mapped into one coupled common cell",
        description=(
            "The first two panels show distinct primitive surface nets and their "
            "candidate supercells. The final panel overlays both nets after one "
            "shared integer basis relabeling and separate orientation-preserving "
            "Cartesian maps place them in the same periodic cell."
        ),
        build=build_coupled_common_cell,
    ),
    FigureRecipe(
        name="strain-partition-path",
        title="Affine-invariant strain partition between two surface cells",
        description=(
            "Three panels show the common interface cell at alpha zero, one half, "
            "and one. Side A is unstrained at alpha zero, logarithmic deformation "
            "is shared at one half, and side B is unstrained at alpha one."
        ),
        build=build_strain_partition_path,
    ),
)


def recipe_map() -> dict[str, FigureRecipe]:
    """Return every maintained recipe keyed by stable figure name."""

    return {recipe.name: recipe for recipe in RECIPES}


def published_recipe_map() -> dict[str, FigureRecipe]:
    """Return the recipes committed to the public MkDocs asset tree."""

    return {recipe.name: recipe for recipe in RECIPES if recipe.published}
