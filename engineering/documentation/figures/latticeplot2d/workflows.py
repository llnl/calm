"""High-level plotting workflows for coupled two-dimensional lattices.

The functions in this module build publication-oriented lattice schematics from
:mod:`latticeplot2d`'s low-level geometry and plotting primitives.  They keep
three operations distinct:

* integer basis relabeling of a cell lattice;
* Cartesian deformation or rotation of a physical surface net; and
* viewport placement.

That separation is essential when a common supercell is displayed together
with the primitive sites from two coupled surface nets.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from math import ceil
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import PathCollection
from matplotlib.figure import Figure
from matplotlib.lines import AxLine
from matplotlib.patches import Polygon
from numpy.typing import ArrayLike

from .geometry import (
    FloatArray,
    GaussReductionResult,
    IntArray,
    as_basis,
    as_index_range,
    as_point,
    cell_vertices,
    gauss_reduce,
)
from .plotting import (
    LatticeArtists,
    center_on_cell,
    plot_cell,
    plot_grid,
    plot_lattice,
    plot_sites,
)
from .style import COLORS


@dataclass(frozen=True)
class CoupledMatchArtists:
    """Matplotlib artists produced by :func:`plot_coupled_match`."""

    grid_lines: tuple[AxLine, ...]
    common_cell: Polygon | None
    sites_a: PathCollection | None
    sites_b: PathCollection | None


@dataclass(frozen=True)
class CoupledMatchResult:
    """Geometry and artists for a coupled A/B lattice match.

    ``transform_a`` and ``transform_b`` are Cartesian affine-gradient parts
    satisfying

    ``transform_x @ (supercell_basis_x @ integer_transform) == common_basis``.

    The same Cartesian maps are applied to the primitive bases.  The shared
    integer transform is *not* applied to the primitive bases.
    """

    common_basis: FloatArray
    reduction: GaussReductionResult
    integer_transform: IntArray
    transform_a: FloatArray
    transform_b: FloatArray
    primitive_basis_a: FloatArray
    primitive_basis_b: FloatArray
    supercell_basis_a: FloatArray
    supercell_basis_b: FloatArray
    artists: CoupledMatchArtists


@dataclass(frozen=True)
class ReductionSequenceResult:
    """Result returned by :func:`plot_reduction_sequence`."""

    figure: Figure
    axes: tuple[Axes, Axes, Axes]
    reduction: GaussReductionResult
    artists: tuple[LatticeArtists, LatticeArtists, LatticeArtists]


@dataclass(frozen=True)
class HNFOrbitGalleryResult:
    """Result returned by :func:`plot_hnf_orbit_gallery`."""

    figure: Figure
    member_axes: tuple[Axes, ...]
    representative_axes: tuple[Axes, ...]
    member_artists: tuple[LatticeArtists, ...]
    representative_artists: tuple[LatticeArtists, ...]
    orbit_order: tuple[Hashable, ...]
    representative_indices: Mapping[Hashable, int]
    reductions: Mapping[Hashable, GaussReductionResult]


@dataclass(frozen=True)
class StrainPartitionFrame:
    """One frame in a strain-partition path.

    Parameters
    ----------
    alpha
        Strain-partition coordinate.
    common_basis
        Common 2D cell at this value of ``alpha``.
    deformation_a, deformation_b
        Cartesian linear maps applied to the A and B primitive surface nets.
    label
        Optional panel label.  The default panel title is ``alpha = ...``.
    """

    alpha: float
    common_basis: ArrayLike
    deformation_a: ArrayLike
    deformation_b: ArrayLike
    label: str | None = None


@dataclass(frozen=True)
class StrainPartitionPathResult:
    """Result returned by :func:`plot_strain_partition_path`."""

    figure: Figure
    axes: tuple[Axes, ...]
    frames: tuple[StrainPartitionFrame, ...]
    reductions: tuple[GaussReductionResult | None, ...]
    common_bases: tuple[FloatArray, ...]
    primitive_bases_a: tuple[FloatArray, ...]
    primitive_bases_b: tuple[FloatArray, ...]
    artists: tuple[CoupledMatchArtists, ...]


def plot_coupled_match(
    ax: Axes,
    primitive_basis_a: ArrayLike,
    primitive_basis_b: ArrayLike,
    supercell_basis_a: ArrayLike,
    supercell_basis_b: ArrayLike,
    *,
    reference: Literal["A", "B", "a", "b"] = "A",
    common_basis: ArrayLike | None = None,
    origin: ArrayLike = (0.0, 0.0),
    grid_i_range: Sequence[int] = (-3, 3),
    grid_j_range: Sequence[int] = (-3, 3),
    site_i_range: Sequence[int] = (-8, 8),
    site_j_range: Sequence[int] = (-8, 8),
    show_grid: bool = True,
    show_cell: bool = True,
    show_sites_a: bool = True,
    show_sites_b: bool = True,
    common_color: Any = COLORS["black"],
    grid_linewidth: float = 1.0,
    grid_alpha: float = 0.45,
    grid_linestyle: Any = "-",
    fill_color: Any = COLORS["light_gray"],
    fill_alpha: float = 0.10,
    cell_linewidth: float = 1.5,
    cell_linestyle: Any = "-",
    color_a: Any = COLORS["blue"],
    color_b: Any = COLORS["vermillion"],
    marker_a: Any = "o",
    marker_b: Any = "s",
    site_size_a: float = 20.0,
    site_size_b: float = 18.0,
    site_edgecolor_a: Any = "white",
    site_edgecolor_b: Any = "white",
    site_linewidth_a: float = 0.5,
    site_linewidth_b: float = 0.5,
    site_alpha_a: float = 0.95,
    site_alpha_b: float = 0.80,
    require_orientation_preserving: bool = True,
    rtol: float = 1.0e-12,
    atol: float = 1.0e-14,
) -> CoupledMatchResult:
    """Plot two primitive nets in one common supercell gauge.

    One shared integer basis relabeling is obtained by Gauss-reducing the
    selected reference supercell.  Both A and B supercell bases receive that
    same right multiplication before separate Cartesian maps place them in the
    common cell.  This preserves the coupled A/B relationship and avoids the
    loss of information caused by independently gauging the two supercells.

    If ``common_basis`` is omitted, the gauged reference supercell is used.
    If it is supplied, it is interpreted as the desired common cell in the
    plotting frame.  The Cartesian maps may include strain as well as rotation,
    which allows already-partitioned or otherwise noncongruent cells to be
    displayed in a common periodic cell.
    """
    primitive_a = as_basis(primitive_basis_a, name="primitive_basis_a")
    primitive_b = as_basis(primitive_basis_b, name="primitive_basis_b")
    supercell_a = as_basis(supercell_basis_a, name="supercell_basis_a")
    supercell_b = as_basis(supercell_basis_b, name="supercell_basis_b")
    common_origin = as_point(origin, name="origin")

    reference_normalized = reference.upper()
    if reference_normalized not in {"A", "B"}:
        raise ValueError("reference must be either 'A' or 'B'.")

    reference_supercell = (
        supercell_a if reference_normalized == "A" else supercell_b
    )
    reduction = gauss_reduce(reference_supercell, rtol=rtol, atol=atol)
    integer_transform = reduction.integer_transform.copy()

    if common_basis is None:
        common = reduction.gauged_basis.copy()
    else:
        common = as_basis(common_basis, name="common_basis").copy()
        if np.linalg.det(common) <= 0.0:
            raise ValueError("common_basis must be right handed.")

    relabeled_a = supercell_a @ integer_transform
    relabeled_b = supercell_b @ integer_transform
    transform_a = common @ np.linalg.inv(relabeled_a)
    transform_b = common @ np.linalg.inv(relabeled_b)

    if require_orientation_preserving:
        if np.linalg.det(transform_a) <= 0.0:
            raise ValueError(
                "The A supercell requires an orientation-reversing map to "
                "reach the common cell. Check the basis-column correspondence."
            )
        if np.linalg.det(transform_b) <= 0.0:
            raise ValueError(
                "The B supercell requires an orientation-reversing map to "
                "reach the common cell. Check the basis-column correspondence."
            )

    mapped_primitive_a = transform_a @ primitive_a
    mapped_primitive_b = transform_b @ primitive_b
    mapped_supercell_a = transform_a @ relabeled_a
    mapped_supercell_b = transform_b @ relabeled_b

    if not np.allclose(mapped_supercell_a, common, rtol=rtol, atol=atol):
        raise RuntimeError("Internal error while mapping the A supercell.")
    if not np.allclose(mapped_supercell_b, common, rtol=rtol, atol=atol):
        raise RuntimeError("Internal error while mapping the B supercell.")

    grid_lines: tuple[AxLine, ...] = ()
    cell_artist: Polygon | None = None
    sites_a: PathCollection | None = None
    sites_b: PathCollection | None = None

    if show_grid:
        grid_lines = plot_grid(
            ax,
            common,
            i_range=grid_i_range,
            j_range=grid_j_range,
            origin=common_origin,
            color=common_color,
            linewidth=grid_linewidth,
            alpha=grid_alpha,
            linestyle=grid_linestyle,
            zorder=1.0,
        )

    if show_cell:
        cell_artist = plot_cell(
            ax,
            common,
            origin=common_origin,
            color=fill_color,
            fill_alpha=fill_alpha,
            linewidth=cell_linewidth,
            linestyle=cell_linestyle,
            zorder=2.0,
        )
        cell_artist.set_edgecolor(common_color)

    if show_sites_a:
        sites_a = plot_sites(
            ax,
            mapped_primitive_a,
            i_range=site_i_range,
            j_range=site_j_range,
            origin=common_origin,
            color=color_a,
            size=site_size_a,
            marker=marker_a,
            edgecolor=site_edgecolor_a,
            linewidth=site_linewidth_a,
            alpha=site_alpha_a,
            zorder=4.0,
        )

    if show_sites_b:
        sites_b = plot_sites(
            ax,
            mapped_primitive_b,
            i_range=site_i_range,
            j_range=site_j_range,
            origin=common_origin,
            color=color_b,
            size=site_size_b,
            marker=marker_b,
            edgecolor=site_edgecolor_b,
            linewidth=site_linewidth_b,
            alpha=site_alpha_b,
            zorder=5.0,
        )

    return CoupledMatchResult(
        common_basis=common,
        reduction=reduction,
        integer_transform=integer_transform,
        transform_a=transform_a,
        transform_b=transform_b,
        primitive_basis_a=mapped_primitive_a,
        primitive_basis_b=mapped_primitive_b,
        supercell_basis_a=mapped_supercell_a,
        supercell_basis_b=mapped_supercell_b,
        artists=CoupledMatchArtists(
            grid_lines=grid_lines,
            common_cell=cell_artist,
            sites_a=sites_a,
            sites_b=sites_b,
        ),
    )


def plot_reduction_sequence(
    source_basis: ArrayLike,
    primitive_basis: ArrayLike | None = None,
    *,
    axes: Sequence[Axes] | None = None,
    origin: ArrayLike = (0.0, 0.0),
    grid_i_range: Sequence[int] = (-2, 2),
    grid_j_range: Sequence[int] = (-2, 2),
    site_i_range: Sequence[int] = (-8, 8),
    site_j_range: Sequence[int] = (-8, 8),
    half_width: float | None = None,
    padding: float = 1.25,
    titles: Sequence[str] = ("Enumerated basis", "Gauss-reduced basis", "Common gauge"),
    colors: Sequence[Any] = (
        COLORS["blue"],
        COLORS["orange"],
        COLORS["bluish_green"],
    ),
    site_color: Any = COLORS["black"],
    show_axes: bool = False,
    figsize: tuple[float, float] = (9.0, 3.0),
) -> ReductionSequenceResult:
    """Plot an enumerated basis, its Gauss reduction, and its common gauge."""
    source = as_basis(source_basis, name="source_basis")
    primitive = source if primitive_basis is None else as_basis(
        primitive_basis,
        name="primitive_basis",
    )
    as_point(origin, name="origin")
    as_index_range(grid_i_range, name="grid_i_range")
    as_index_range(grid_j_range, name="grid_j_range")
    as_index_range(site_i_range, name="site_i_range")
    as_index_range(site_j_range, name="site_j_range")

    if len(titles) != 3:
        raise ValueError("titles must contain exactly three strings.")
    if len(colors) != 3:
        raise ValueError("colors must contain exactly three values.")

    reduction = gauss_reduce(source)
    cell_bases = (
        source,
        reduction.reduced_basis,
        reduction.gauged_basis,
    )
    site_bases = (
        primitive,
        primitive,
        reduction.rotate_basis(primitive),
    )

    fig, axes_tuple = _prepare_axes(
        axes,
        count=3,
        ncols=3,
        figsize=figsize,
    )

    if half_width is None:
        selected_half_width = _shared_cell_half_width(
            cell_bases,
            padding=padding,
        )
    else:
        selected_half_width = _positive_scalar(half_width, name="half_width")

    artists: list[LatticeArtists] = []

    for ax, cell_basis, sites_basis, color, title in zip(
        axes_tuple,
        cell_bases,
        site_bases,
        colors,
        titles,
        strict=True,
    ):
        lattice_artists = plot_lattice(
            ax,
            grid_basis=cell_basis,
            site_basis=sites_basis,
            cell_basis=cell_basis,
            grid_i_range=grid_i_range,
            grid_j_range=grid_j_range,
            site_i_range=site_i_range,
            site_j_range=site_j_range,
            origin=origin,
            color=color,
            show_sites=False,
            grid_linewidth=1.0,
            grid_alpha=0.45,
            fill_alpha=0.10,
            cell_linewidth=1.5,
        )
        sites = plot_sites(
            ax,
            sites_basis,
            i_range=site_i_range,
            j_range=site_j_range,
            origin=origin,
            color=site_color,
            size=14.0,
            marker="o",
            edgecolor="white",
            linewidth=0.4,
            alpha=0.9,
            zorder=4.0,
        )
        artists.append(
            LatticeArtists(
                grid_lines=lattice_artists.grid_lines,
                sites=sites,
                cell=lattice_artists.cell,
            )
        )
        center_on_cell(ax, cell_basis, origin=origin, half_width=selected_half_width)
        ax.set_title(title)
        _configure_schematic_axis(ax, show_axes=show_axes)

    return ReductionSequenceResult(
        figure=fig,
        axes=(axes_tuple[0], axes_tuple[1], axes_tuple[2]),
        reduction=reduction,
        artists=(artists[0], artists[1], artists[2]),
    )


def plot_hnf_orbit_gallery(
    primitive_basis: ArrayLike,
    hnf_members: Sequence[ArrayLike],
    orbit_labels: Sequence[Hashable],
    *,
    member_labels: Sequence[str] | None = None,
    representative_indices: Mapping[Hashable, int] | None = None,
    ncols: int = 3,
    show_representatives: bool = True,
    grid_i_range: Sequence[int] = (-2, 2),
    grid_j_range: Sequence[int] = (-2, 2),
    site_i_range: Sequence[int] = (-8, 8),
    site_j_range: Sequence[int] = (-8, 8),
    orbit_colors: Mapping[Hashable, Any] | None = None,
    half_width: float | None = None,
    padding: float = 1.25,
    show_axes: bool = False,
    figsize: tuple[float, float] | None = None,
) -> HNFOrbitGalleryResult:
    """Plot exact HNF members and optional Gauss-gauged orbit representatives.

    ``hnf_members`` are integer 2x2 right transformations satisfying
    ``supercell_basis = primitive_basis @ H``.  The exact members are retained
    in the upper gallery.  The lower gallery contains one Gauss-gauged member
    per orbit and is therefore explicitly representative-level rather than a
    destructive replacement of the exact member set.
    """
    primitive = as_basis(primitive_basis, name="primitive_basis")
    members = tuple(
        _as_integer_transform(member, name=f"hnf_members[{index}]")
        for index, member in enumerate(hnf_members)
    )

    if not members:
        raise ValueError("hnf_members must contain at least one matrix.")
    if len(orbit_labels) != len(members):
        raise ValueError("orbit_labels must have the same length as hnf_members.")
    if not isinstance(ncols, int) or ncols <= 0:
        raise ValueError("ncols must be a positive integer.")

    labels = tuple(orbit_labels)
    orbit_order = tuple(dict.fromkeys(labels))

    if member_labels is None:
        exact_labels = tuple(f"H{index}" for index in range(len(members)))
    else:
        if len(member_labels) != len(members):
            raise ValueError(
                "member_labels must have the same length as hnf_members."
            )
        exact_labels = tuple(str(label) for label in member_labels)

    selected_representatives = _resolve_representative_indices(
        labels,
        orbit_order,
        representative_indices,
    )
    colors = _resolve_orbit_colors(orbit_order, orbit_colors)
    supercells = tuple(primitive @ member for member in members)
    reductions = {
        orbit: gauss_reduce(supercells[index])
        for orbit, index in selected_representatives.items()
    }

    member_rows = ceil(len(members) / ncols)
    representative_rows = ceil(len(orbit_order) / ncols) if show_representatives else 0
    total_rows = member_rows + representative_rows

    if figsize is None:
        figsize = (3.0 * ncols, 3.0 * total_rows)

    fig, axes_array = plt.subplots(
        total_rows,
        ncols,
        figsize=figsize,
        squeeze=False,
        layout="constrained",
    )
    all_axes = tuple(axes_array.ravel())
    member_axes = all_axes[: len(members)]
    representative_start = member_rows * ncols
    representative_axes = (
        all_axes[representative_start : representative_start + len(orbit_order)]
        if show_representatives
        else ()
    )

    representative_bases = tuple(
        reductions[orbit].gauged_basis for orbit in orbit_order
    )
    if half_width is None:
        selected_half_width = _shared_cell_half_width(
            (*supercells, *representative_bases),
            padding=padding,
        )
    else:
        selected_half_width = _positive_scalar(half_width, name="half_width")

    member_artists: list[LatticeArtists] = []
    for index, (ax, supercell, orbit, label) in enumerate(
        zip(member_axes, supercells, labels, exact_labels, strict=True)
    ):
        artist = plot_lattice(
            ax,
            grid_basis=supercell,
            site_basis=primitive,
            cell_basis=supercell,
            grid_i_range=grid_i_range,
            grid_j_range=grid_j_range,
            site_i_range=site_i_range,
            site_j_range=site_j_range,
            color=colors[orbit],
            grid_alpha=0.40,
            site_size=12.0,
            site_edgecolor="white",
            site_linewidth=0.35,
            fill_alpha=0.09,
            cell_linewidth=1.5,
        )
        center_on_cell(ax, supercell, half_width=selected_half_width)
        ax.set_title(f"{label}  |  orbit {orbit}")
        _configure_schematic_axis(ax, show_axes=show_axes)
        member_artists.append(artist)

    representative_artists: list[LatticeArtists] = []
    if show_representatives:
        for ax, orbit in zip(representative_axes, orbit_order, strict=True):
            reduction = reductions[orbit]
            primitive_gauged = reduction.rotate_basis(primitive)
            artist = plot_lattice(
                ax,
                grid_basis=reduction.gauged_basis,
                site_basis=primitive_gauged,
                cell_basis=reduction.gauged_basis,
                grid_i_range=grid_i_range,
                grid_j_range=grid_j_range,
                site_i_range=site_i_range,
                site_j_range=site_j_range,
                color=colors[orbit],
                grid_alpha=0.40,
                site_size=12.0,
                site_edgecolor="white",
                site_linewidth=0.35,
                fill_alpha=0.09,
                cell_linewidth=1.5,
            )
            center_on_cell(
                ax,
                reduction.gauged_basis,
                half_width=selected_half_width,
            )
            ax.set_title(f"orbit {orbit} representative")
            _configure_schematic_axis(ax, show_axes=show_axes)
            representative_artists.append(artist)

    used_axes = set(member_axes) | set(representative_axes)
    for ax in all_axes:
        if ax not in used_axes:
            ax.set_visible(False)

    return HNFOrbitGalleryResult(
        figure=fig,
        member_axes=tuple(member_axes),
        representative_axes=tuple(representative_axes),
        member_artists=tuple(member_artists),
        representative_artists=tuple(representative_artists),
        orbit_order=orbit_order,
        representative_indices=dict(selected_representatives),
        reductions=dict(reductions),
    )


def plot_strain_partition_path(
    primitive_basis_a: ArrayLike,
    primitive_basis_b: ArrayLike,
    frames: Sequence[StrainPartitionFrame | Mapping[str, Any]],
    *,
    ncols: int | None = None,
    gauge: Literal["gauss", "none"] = "gauss",
    grid_i_range: Sequence[int] = (-2, 2),
    grid_j_range: Sequence[int] = (-2, 2),
    site_i_range: Sequence[int] = (-8, 8),
    site_j_range: Sequence[int] = (-8, 8),
    half_width: float | None = None,
    padding: float = 1.25,
    show_axes: bool = False,
    figsize: tuple[float, float] | None = None,
    common_color: Any = COLORS["black"],
    color_a: Any = COLORS["blue"],
    color_b: Any = COLORS["vermillion"],
) -> StrainPartitionPathResult:
    """Plot common cells and transformed primitive nets along a strain path.

    Each frame supplies the common cell and the Cartesian maps acting on the A
    and B primitive nets.  With ``gauge='gauss'`` (the default), each common
    cell is Gauss-reduced and rotated into the package's standard gauge before
    plotting; only that Cartesian rotation is propagated to the transformed
    primitive nets.
    """
    primitive_a = as_basis(primitive_basis_a, name="primitive_basis_a")
    primitive_b = as_basis(primitive_basis_b, name="primitive_basis_b")
    normalized_frames = tuple(_coerce_strain_frame(frame) for frame in frames)

    if not normalized_frames:
        raise ValueError("frames must contain at least one strain-partition frame.")
    if gauge not in {"gauss", "none"}:
        raise ValueError("gauge must be either 'gauss' or 'none'.")

    if ncols is None:
        ncols = len(normalized_frames)
    if not isinstance(ncols, int) or ncols <= 0:
        raise ValueError("ncols must be a positive integer.")

    plot_common_bases: list[FloatArray] = []
    plot_primitive_a: list[FloatArray] = []
    plot_primitive_b: list[FloatArray] = []
    reductions: list[GaussReductionResult | None] = []

    for index, frame in enumerate(normalized_frames):
        if not np.isfinite(frame.alpha):
            raise ValueError(f"frames[{index}].alpha must be finite.")
        common = as_basis(frame.common_basis, name=f"frames[{index}].common_basis")
        deformation_a = _as_linear_map(
            frame.deformation_a,
            name=f"frames[{index}].deformation_a",
        )
        deformation_b = _as_linear_map(
            frame.deformation_b,
            name=f"frames[{index}].deformation_b",
        )
        transformed_a = deformation_a @ primitive_a
        transformed_b = deformation_b @ primitive_b

        if gauge == "gauss":
            reduction = gauss_reduce(common)
            plot_common_bases.append(reduction.gauged_basis)
            plot_primitive_a.append(reduction.rotate_basis(transformed_a))
            plot_primitive_b.append(reduction.rotate_basis(transformed_b))
            reductions.append(reduction)
        else:
            plot_common_bases.append(common)
            plot_primitive_a.append(transformed_a)
            plot_primitive_b.append(transformed_b)
            reductions.append(None)

    rows = ceil(len(normalized_frames) / ncols)
    if figsize is None:
        figsize = (3.0 * ncols, 3.0 * rows)

    fig, axes_array = plt.subplots(
        rows,
        ncols,
        figsize=figsize,
        squeeze=False,
        layout="constrained",
    )
    all_axes = tuple(axes_array.ravel())
    used_axes = all_axes[: len(normalized_frames)]

    if half_width is None:
        selected_half_width = _shared_cell_half_width(
            plot_common_bases,
            padding=padding,
        )
    else:
        selected_half_width = _positive_scalar(half_width, name="half_width")

    artist_results: list[CoupledMatchArtists] = []
    for ax, frame, common, sites_a_basis, sites_b_basis in zip(
        used_axes,
        normalized_frames,
        plot_common_bases,
        plot_primitive_a,
        plot_primitive_b,
        strict=True,
    ):
        grid_lines = plot_grid(
            ax,
            common,
            i_range=grid_i_range,
            j_range=grid_j_range,
            color=common_color,
            linewidth=1.0,
            alpha=0.40,
            zorder=1.0,
        )
        cell = plot_cell(
            ax,
            common,
            color=COLORS["light_gray"],
            fill_alpha=0.10,
            linewidth=1.5,
            zorder=2.0,
        )
        cell.set_edgecolor(common_color)
        sites_a = plot_sites(
            ax,
            sites_a_basis,
            i_range=site_i_range,
            j_range=site_j_range,
            color=color_a,
            size=18.0,
            marker="o",
            edgecolor="white",
            linewidth=0.45,
            alpha=0.9,
            zorder=4.0,
        )
        sites_b = plot_sites(
            ax,
            sites_b_basis,
            i_range=site_i_range,
            j_range=site_j_range,
            color=color_b,
            size=16.0,
            marker="s",
            edgecolor="white",
            linewidth=0.45,
            alpha=0.75,
            zorder=5.0,
        )
        center_on_cell(ax, common, half_width=selected_half_width)
        ax.set_title(frame.label or rf"$\alpha={frame.alpha:g}$")
        _configure_schematic_axis(ax, show_axes=show_axes)
        artist_results.append(
            CoupledMatchArtists(
                grid_lines=grid_lines,
                common_cell=cell,
                sites_a=sites_a,
                sites_b=sites_b,
            )
        )

    for ax in all_axes[len(normalized_frames) :]:
        ax.set_visible(False)

    return StrainPartitionPathResult(
        figure=fig,
        axes=tuple(used_axes),
        frames=normalized_frames,
        reductions=tuple(reductions),
        common_bases=tuple(plot_common_bases),
        primitive_bases_a=tuple(plot_primitive_a),
        primitive_bases_b=tuple(plot_primitive_b),
        artists=tuple(artist_results),
    )


def _prepare_axes(
    axes: Sequence[Axes] | None,
    *,
    count: int,
    ncols: int,
    figsize: tuple[float, float],
) -> tuple[Figure, tuple[Axes, ...]]:
    if axes is None:
        rows = ceil(count / ncols)
        fig, array = plt.subplots(
            rows,
            ncols,
            figsize=figsize,
            squeeze=False,
            layout="constrained",
        )
        axes_tuple = tuple(array.ravel()[:count])
        for unused in array.ravel()[count:]:
            unused.set_visible(False)
        return fig, axes_tuple

    axes_tuple = tuple(axes)
    if len(axes_tuple) != count:
        raise ValueError(f"axes must contain exactly {count} Matplotlib axes.")
    figure = axes_tuple[0].figure
    if any(ax.figure is not figure for ax in axes_tuple):
        raise ValueError("All supplied axes must belong to the same figure.")
    return figure, axes_tuple


def _shared_cell_half_width(
    bases: Sequence[ArrayLike],
    *,
    padding: float,
) -> float:
    padding_value = _positive_scalar(padding, name="padding")
    maximum = 0.0
    for basis in bases:
        array = as_basis(basis)
        vertices = cell_vertices(array)
        center = 0.5 * array.sum(axis=1)
        maximum = max(maximum, float(np.max(np.abs(vertices - center))))
    return max(maximum * padding_value, 1.0e-12)


def _positive_scalar(value: float, *, name: str) -> float:
    scalar = float(value)
    if not np.isfinite(scalar) or scalar <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return scalar


def _configure_schematic_axis(ax: Axes, *, show_axes: bool) -> None:
    ax.set_aspect("equal", adjustable="box")
    if not show_axes:
        ax.set_axis_off()


def _as_integer_transform(value: ArrayLike, *, name: str) -> IntArray:
    raw = np.asarray(value)
    if raw.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2); received {raw.shape}.")
    if not np.all(np.isfinite(raw.astype(float))):
        raise ValueError(f"{name} must contain only finite values.")
    if not np.all(np.equal(raw, np.round(raw))):
        raise ValueError(f"{name} must contain integer values.")
    integer = raw.astype(np.int64)
    determinant = (
        int(integer[0, 0]) * int(integer[1, 1])
        - int(integer[0, 1]) * int(integer[1, 0])
    )
    if determinant == 0:
        raise ValueError(f"{name} must be nonsingular.")
    return integer


def _as_linear_map(value: ArrayLike, *, name: str) -> FloatArray:
    array = np.asarray(value, dtype=float)
    if array.shape != (2, 2):
        raise ValueError(f"{name} must have shape (2, 2); received {array.shape}.")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    if np.isclose(np.linalg.det(array), 0.0):
        raise ValueError(f"{name} must be nonsingular.")
    return array


def _resolve_representative_indices(
    labels: Sequence[Hashable],
    orbit_order: Sequence[Hashable],
    requested: Mapping[Hashable, int] | None,
) -> dict[Hashable, int]:
    if requested is None:
        result: dict[Hashable, int] = {}
        for index, orbit in enumerate(labels):
            result.setdefault(orbit, index)
        return result

    result = dict(requested)
    if set(result) != set(orbit_order):
        raise ValueError(
            "representative_indices must provide exactly one index for every orbit."
        )
    for orbit, index in result.items():
        if not isinstance(index, int) or not 0 <= index < len(labels):
            raise ValueError(
                f"Invalid representative index {index!r} for orbit {orbit!r}."
            )
        if labels[index] != orbit:
            raise ValueError(
                f"Index {index} belongs to orbit {labels[index]!r}, not {orbit!r}."
            )
    return result


def _resolve_orbit_colors(
    orbit_order: Sequence[Hashable],
    requested: Mapping[Hashable, Any] | None,
) -> dict[Hashable, Any]:
    if requested is not None:
        missing = set(orbit_order) - set(requested)
        if missing:
            formatted = ", ".join(repr(value) for value in missing)
            raise ValueError(f"orbit_colors is missing colors for: {formatted}.")
        return {orbit: requested[orbit] for orbit in orbit_order}

    palette = (
        COLORS["blue"],
        COLORS["vermillion"],
        COLORS["bluish_green"],
        COLORS["orange"],
        COLORS["reddish_purple"],
        COLORS["sky_blue"],
    )
    return {
        orbit: palette[index % len(palette)]
        for index, orbit in enumerate(orbit_order)
    }


def _coerce_strain_frame(
    frame: StrainPartitionFrame | Mapping[str, Any],
) -> StrainPartitionFrame:
    if isinstance(frame, StrainPartitionFrame):
        return frame
    if isinstance(frame, Mapping):
        required = {"alpha", "common_basis", "deformation_a", "deformation_b"}
        missing = required - set(frame)
        if missing:
            raise ValueError(
                "A strain-frame mapping is missing required keys: "
                + ", ".join(sorted(missing))
            )
        return StrainPartitionFrame(
            alpha=float(frame["alpha"]),
            common_basis=frame["common_basis"],
            deformation_a=frame["deformation_a"],
            deformation_b=frame["deformation_b"],
            label=None if frame.get("label") is None else str(frame["label"]),
        )
    raise TypeError(
        "Each frame must be a StrainPartitionFrame or a mapping with alpha, "
        "common_basis, deformation_a, and deformation_b."
    )
