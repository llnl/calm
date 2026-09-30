"""Decorated ideal-bulk surface termination enumeration.

The automatic path classifies ideal truncations of the periodic bulk motif. A
termination identity includes the complete species-labelled layer sequence,
relative layer heights, in-plane fractional coordinates, and admitted surface
point-group operations. Stoichiometry alone is not a scientific identity.

This is not a reconstruction, stability, surface-energy, dipole, or polarity
calculation. CALM does not infer polarity without an explicit electrostatic
model.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, NamedTuple

import numpy as np

from calm.slab.oriented.termination_identity import (
    DecoratedLayerAtom,
    DecoratedPeriodicLayer,
    DecoratedTerminationClass,
    TERMINATION_IDENTITY_SCHEME,
    TERMINATION_IDENTITY_VERSION,
    enumerate_decorated_termination_classes,
    stacking_translation_order,
)

if TYPE_CHECKING:
    from ase import Atoms
    from calm.bulk.bulk import Bulk


class LayerInfo(NamedTuple):
    """One finite-slab atomic layer, ordered from bottom to top."""

    z_position: float
    atom_indices: list[int]
    composition: str
    stoichiometry: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class EnumeratedTermination:
    """One built slab plus versioned termination metadata."""

    slab: Any
    label: str
    shift: int
    metadata: dict[str, Any]

    def __iter__(self):
        yield self.slab
        yield self.label
        yield self.shift

    def __len__(self) -> int:
        return 3

    def __getitem__(self, index: int):
        return (self.slab, self.label, self.shift)[index]


def _to_subscript(formula: str) -> str:
    subscript_map = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    return formula.translate(subscript_map)


def _format_layer_composition(composition_counter: Counter) -> str:
    """Format a layer composition deterministically for display."""

    symbols: list[str] = []
    for element, count in sorted(composition_counter.items()):
        symbols.extend([element] * int(count))
    if not symbols:
        return ""
    try:
        from ase import Atoms
    except ImportError:
        formula = "".join(
            f"{element}{count if count > 1 else ''}"
            for element, count in sorted(composition_counter.items())
        )
    else:
        formula = Atoms(symbols=symbols).get_chemical_formula(
            mode="metal",
            empirical=False,
        )
    return _to_subscript(formula)


def _layer_info(
    *,
    z_position: float,
    atom_indices: Iterable[int],
    symbols: list[str],
) -> LayerInfo:
    indices = [int(index) for index in atom_indices]
    counts = Counter(symbols[index] for index in indices)
    return LayerInfo(
        z_position=float(z_position),
        atom_indices=indices,
        composition=_format_layer_composition(counts),
        stoichiometry=tuple(sorted(counts.items())),
    )


def _cluster_atoms_by_z(
    atoms: Atoms,
    tolerance: float = 0.3,
) -> list[LayerInfo]:
    """Cluster a finite slab into Cartesian-z layers, bottom to top."""

    tol = float(tolerance)
    if not np.isfinite(tol) or tol <= 0.0:
        raise ValueError("tolerance must be a positive finite length")
    positions = np.asarray(atoms.get_positions(), dtype=float)
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("atoms positions must have shape (N, 3)")
    if positions.shape[0] == 0:
        return []
    symbols = list(atoms.get_chemical_symbols())
    z_coords = positions[:, 2]
    order = np.argsort(z_coords, kind="mergesort")
    groups: list[list[int]] = []
    current = [int(order[0])]
    start = float(z_coords[order[0]])
    for index in order[1:]:
        idx = int(index)
        if float(z_coords[idx]) - start < tol:
            current.append(idx)
        else:
            groups.append(current)
            current = [idx]
            start = float(z_coords[idx])
    groups.append(current)
    return [
        _layer_info(
            z_position=float(np.mean(z_coords[group])),
            atom_indices=group,
            symbols=symbols,
        )
        for group in groups
    ]


def _surface_frame(cell: np.ndarray) -> tuple[np.ndarray, float, np.ndarray]:
    cell_array = np.asarray(cell, dtype=float)
    if cell_array.shape != (3, 3) or not np.all(np.isfinite(cell_array)):
        raise ValueError("periodic block cell must be a finite 3x3 matrix")
    a, b, c = cell_array
    normal = np.cross(a, b)
    norm = float(np.linalg.norm(normal))
    if norm <= np.finfo(float).tiny:
        raise ValueError("surface cell vectors must be linearly independent")
    normal /= norm
    normal_period = float(np.dot(c, normal))
    if abs(normal_period) <= np.finfo(float).tiny:
        raise ValueError("stacking vector must advance along the surface normal")
    if normal_period < 0.0:
        normal = -normal
        normal_period = -normal_period
    surface_columns = np.column_stack([a, b])
    c_parallel = c - normal_period * normal
    translation, _residuals, rank, _singular = np.linalg.lstsq(
        surface_columns,
        c_parallel,
        rcond=None,
    )
    if rank != 2:
        raise ValueError("surface basis is rank deficient")
    reconstruction = surface_columns @ translation
    scale = max(1.0, float(np.linalg.norm(c_parallel)))
    if float(np.linalg.norm(reconstruction - c_parallel)) > 1e-10 * scale:
        raise ValueError("unable to resolve stacking translation in surface basis")
    return normal, normal_period, np.asarray(translation, dtype=float)


def _periodic_phase_groups(
    phases: np.ndarray,
    *,
    tolerance_fractional: float,
) -> list[list[int]]:
    if phases.size == 0:
        return []
    order = np.argsort(phases, kind="mergesort")
    groups: list[list[int]] = []
    current = [int(order[0])]
    start = float(phases[order[0]])
    for index in order[1:]:
        idx = int(index)
        if float(phases[idx]) - start <= tolerance_fractional:
            current.append(idx)
        else:
            groups.append(current)
            current = [idx]
            start = float(phases[idx])
    groups.append(current)
    if len(groups) > 1:
        first = groups[0]
        last = groups[-1]
        wrap_span = float(phases[first[-1]]) + 1.0 - float(phases[last[0]])
        if wrap_span <= tolerance_fractional:
            groups[0] = last + first
            groups.pop()
    return groups


def _periodic_layer_phase(phases: np.ndarray, indices: list[int]) -> float:
    values = np.asarray([phases[index] for index in indices], dtype=float)
    reference = float(values[0])
    unwrapped = values.copy()
    unwrapped[unwrapped - reference > 0.5] -= 1.0
    unwrapped[reference - unwrapped > 0.5] += 1.0
    return float(np.mean(unwrapped) % 1.0)


def _extract_decorated_periodic_layers(
    block: Atoms,
    *,
    layer_tolerance_A: float,
) -> tuple[tuple[DecoratedPeriodicLayer, ...], float, np.ndarray]:
    """Extract decorated layers from one exact periodic stacking repeat."""

    tolerance = float(layer_tolerance_A)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("layer_tolerance_A must be a positive finite length")
    cell = np.asarray(block.get_cell(), dtype=float)
    positions = np.asarray(block.get_positions(), dtype=float)
    symbols = list(block.get_chemical_symbols())
    if positions.ndim != 2 or positions.shape[1] != 3:
        raise ValueError("periodic block positions must have shape (N, 3)")
    if len(symbols) != positions.shape[0] or not symbols:
        raise ValueError("periodic block must contain labelled atoms")
    normal, normal_period, stacking_translation = _surface_frame(cell)
    phases = np.mod((positions @ normal) / normal_period, 1.0)
    groups = _periodic_phase_groups(
        phases,
        tolerance_fractional=tolerance / normal_period,
    )
    surface_columns = np.column_stack([cell[0], cell[1]])
    decorated: list[DecoratedPeriodicLayer] = []
    for group in groups:
        phase = _periodic_layer_phase(phases, group)
        counts = Counter(symbols[index] for index in group)
        atoms: list[DecoratedLayerAtom] = []
        for index in group:
            position = positions[index]
            parallel = position - float(np.dot(position, normal)) * normal
            uv, _residuals, rank, _singular = np.linalg.lstsq(
                surface_columns,
                parallel,
                rcond=None,
            )
            if rank != 2:
                raise ValueError("surface basis is rank deficient")
            atoms.append(
                DecoratedLayerAtom(
                    symbol=str(symbols[index]),
                    uv=(float(uv[0] % 1.0), float(uv[1] % 1.0)),
                )
            )
        decorated.append(
            DecoratedPeriodicLayer(
                phase=phase,
                height_A=phase * normal_period,
                atom_indices=tuple(sorted(int(index) for index in group)),
                composition=_format_layer_composition(counts),
                stoichiometry=tuple(sorted(counts.items())),
                atoms=tuple(
                    sorted(
                        atoms,
                        key=lambda atom: (atom.symbol, atom.uv[0], atom.uv[1]),
                    )
                ),
            )
        )
    decorated.sort(
        key=lambda layer: (
            layer.phase,
            layer.stoichiometry,
            tuple((atom.symbol, atom.uv) for atom in layer.atoms),
        )
    )
    return tuple(decorated), normal_period, stacking_translation


def _surface_symmetry_operations(
    block: Atoms,
    *,
    symprec: float,
    mode: str,
    angle_tolerance: float,
    metric_tolerance: float,
):
    from calm.symmetry.surface_resolver import resolve_surface_pointgroup_2d

    return resolve_surface_pointgroup_2d(
        block,
        mode=mode,
        symprec=symprec,
        angle_tolerance=angle_tolerance,
        metric_tolerance=metric_tolerance,
    )


def _identity_metadata(
    termination_class: DecoratedTerminationClass,
    *,
    layers: tuple[DecoratedPeriodicLayer, ...],
    normal_period_A: float,
    stacking_translation: np.ndarray,
    stacking_order: int,
    layer_tolerance_A: float,
    position_tolerance_frac: float,
    stacking_tolerance_frac: float,
    surface_symmetry_provenance: dict[str, Any],
) -> dict[str, Any]:
    top_index = termination_class.representative_layer_index
    bottom_index = (top_index - (len(layers) - 1)) % len(layers)
    top_layer = layers[top_index]
    bottom_layer = layers[bottom_index]
    return {
        "shift": int(top_index),
        "label": top_layer.composition,
        "top_composition": top_layer.composition,
        "bottom_composition": bottom_layer.composition,
        "top_stoichiometry": top_layer.stoichiometry,
        "bottom_stoichiometry": bottom_layer.stoichiometry,
        "termination_identity_version": TERMINATION_IDENTITY_VERSION,
        "termination_identity_scheme": TERMINATION_IDENTITY_SCHEME,
        "termination_identity": termination_class.top_identity,
        "termination_top_identity": termination_class.top_identity,
        "termination_bottom_identity": termination_class.bottom_identity,
        "termination_pair_identity": termination_class.pair_identity,
        "equivalent_layer_indices": list(termination_class.equivalent_layer_indices),
        "cut_fractional": float(termination_class.cut_fractional),
        "layers_per_stacking_translation": len(layers),
        "decorated_stacking_period_layers": len(layers) * stacking_order,
        "stacking_translation_order": int(stacking_order),
        "stacking_translation_frac": [float(value) for value in stacking_translation],
        "normal_period_A": float(normal_period_A),
        "layer_tolerance_A": float(layer_tolerance_A),
        "position_tolerance_frac": float(position_tolerance_frac),
        "stacking_tolerance_frac": float(stacking_tolerance_frac),
        "surface_symmetry": dict(surface_symmetry_provenance),
        "top_signature": termination_class.top_signature,
        "bottom_signature": termination_class.bottom_signature,
    }


def identify_unique_terminations(
    bulk: Bulk,
    hkl: tuple[int, int, int],
    layers: int = 10,
    tolerance: float = 0.3,
    *,
    position_tolerance_frac: float = 1e-6,
    stacking_tolerance_frac: float = 1e-8,
    max_stacking_order: int = 96,
    surface_symmetry_mode: str = "discover",
    surface_symprec: float | None = None,
    surface_angle_tolerance: float = 1e-8,
    surface_metric_tolerance: float = 1e-5,
) -> list[dict[str, Any]]:
    """Identify version-2 decorated termination classes."""

    from calm.slab.oriented.model import build_oriented_slab

    repeat_count = int(layers)
    if repeat_count <= 0:
        raise ValueError("layers must be a positive integer")
    result = build_oriented_slab(
        bulk,
        hkl=hkl,
        layers=1,
        vacuum=None,
        reduce_inplane=True,
        center_slab=False,
        wrap=True,
    )
    periodic_layers, normal_period, stacking_translation = (
        _extract_decorated_periodic_layers(
            result.block,
            layer_tolerance_A=tolerance,
        )
    )
    resolved_symprec = (
        getattr(bulk, "symprec", 1e-5) if surface_symprec is None else surface_symprec
    )
    symmetry_resolution = _surface_symmetry_operations(
        result.block,
        symprec=resolved_symprec,
        mode=surface_symmetry_mode,
        angle_tolerance=surface_angle_tolerance,
        metric_tolerance=surface_metric_tolerance,
    )
    symmetry_operations = symmetry_resolution.operations
    stacking_order = stacking_translation_order(
        stacking_translation,
        tolerance=stacking_tolerance_frac,
        max_order=max_stacking_order,
    )
    classes = enumerate_decorated_termination_classes(
        periodic_layers,
        stacking_translation_frac=stacking_translation,
        normal_period_A=normal_period,
        slab_repeat_count=repeat_count,
        symmetry_operations=symmetry_operations,
        layer_tolerance_A=tolerance,
        position_tolerance_frac=position_tolerance_frac,
        stacking_tolerance_frac=stacking_tolerance_frac,
        max_stacking_order=max_stacking_order,
    )
    return [
        _identity_metadata(
            item,
            layers=periodic_layers,
            normal_period_A=normal_period,
            stacking_translation=stacking_translation,
            stacking_order=stacking_order,
            layer_tolerance_A=tolerance,
            position_tolerance_frac=position_tolerance_frac,
            stacking_tolerance_frac=stacking_tolerance_frac,
            surface_symmetry_provenance=(symmetry_resolution.provenance.to_dict()),
        )
        for item in classes
    ]


def _candidate_for_shift(
    candidates: Iterable[dict[str, Any]],
    shift: int,
) -> dict[str, Any]:
    for candidate in candidates:
        if int(candidate.get("shift", -1)) == int(shift):
            return candidate
    available = sorted(int(item.get("shift", -1)) for item in candidates)
    raise ValueError(
        f"termination_shift={shift} is not a canonical termination "
        f"representative; available shifts are {available}."
    )


def _shift_periodic_cut(
    block: Atoms,
    cut_fractional: float,
    *,
    repeat_count: int,
) -> Atoms:
    """Move a one-repeat cleavage phase to the finite-block boundary."""

    repeats = int(repeat_count)
    if repeats <= 0 or repeats != repeat_count:
        raise ValueError("repeat_count must be a positive integer")
    cut = float(cut_fractional)
    if not np.isfinite(cut):
        raise ValueError("cut_fractional must be finite")
    shifted = block.copy()
    scaled = np.asarray(shifted.get_scaled_positions(wrap=False), dtype=float)
    block_fractional_cut = cut / repeats
    scaled[:, 2] = np.mod(scaled[:, 2] - block_fractional_cut, 1.0)
    shifted.set_scaled_positions(scaled)
    shifted.wrap(eps=1e-5)
    return shifted


def _add_boundary_vacuum(
    block: Atoms,
    *,
    vacuum: float,
    center_slab: bool,
) -> Atoms:
    padding = float(vacuum)
    if not np.isfinite(padding) or padding < 0.0:
        raise ValueError("vacuum must be a nonnegative finite length")
    if padding == 0.0:
        return block.copy()
    from calm.slab.oriented.builder import _add_vacuum_along_cartesian_z

    slab, provenance = _add_vacuum_along_cartesian_z(
        block,
        padding,
        center=bool(center_slab),
        # The selected cleavage phase is already at the periodic boundary.
        # Re-unwrapping by the largest gap can silently select another cut.
        unwrap_first=False,
        z_axis=2,
        z_tol=1e-10,
    )

    info = getattr(slab, "info", None)
    if isinstance(info, dict):
        from calm.slab.oriented.transforms import (
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
            OrientedSlabTransforms as CompactOrientedSlabTransforms,
            from_transforms_payload,
            put_transforms_payload_in_atoms_info,
        )

        payload = info.get(ORIENTED_SLAB_TRANSFORMS_INFO_KEY)
        if payload is not None:
            current = from_transforms_payload(payload)
            extra = dict(current.extra)
            extra["vacuum_info"] = provenance
            updated = CompactOrientedSlabTransforms(
                version=current.version,
                U=current.U,
                hkl=current.hkl,
                extra=extra,
            )
            put_transforms_payload_in_atoms_info(slab, updated.payload)
    return slab


def build_slab_with_termination(
    bulk: Bulk,
    hkl: tuple[int, int, int],
    layers: int,
    termination_shift: int = 0,
    *,
    termination_label: str | None = None,
    vacuum: float = 10.0,
    reduce_inplane: bool = True,
    center_slab: bool = True,
    tolerance: float = 0.3,
    position_tolerance_frac: float = 1e-6,
    stacking_tolerance_frac: float = 1e-8,
    max_stacking_order: int = 96,
    surface_symmetry_mode: str = "discover",
    surface_symprec: float | None = None,
    surface_angle_tolerance: float = 1e-8,
    surface_metric_tolerance: float = 1e-5,
) -> tuple[Atoms, str]:
    """Build a finite slab by selecting a canonical cleavage phase."""

    from calm.slab.oriented.model import build_oriented_slab

    candidates = identify_unique_terminations(
        bulk,
        hkl,
        layers=layers,
        tolerance=tolerance,
        position_tolerance_frac=position_tolerance_frac,
        stacking_tolerance_frac=stacking_tolerance_frac,
        max_stacking_order=max_stacking_order,
        surface_symmetry_mode=surface_symmetry_mode,
        surface_symprec=surface_symprec,
        surface_angle_tolerance=surface_angle_tolerance,
        surface_metric_tolerance=surface_metric_tolerance,
    )
    candidate = _candidate_for_shift(candidates, termination_shift)
    result = build_oriented_slab(
        bulk,
        hkl=hkl,
        layers=int(layers),
        vacuum=None,
        reduce_inplane=reduce_inplane,
        center_slab=False,
        wrap=True,
    )
    shifted = _shift_periodic_cut(
        result.block,
        float(candidate["cut_fractional"]),
        repeat_count=int(layers),
    )
    slab = _add_boundary_vacuum(
        shifted,
        vacuum=vacuum,
        center_slab=center_slab,
    )
    return slab, str(termination_label or candidate["label"])


def enumerate_all_terminations(
    bulk: Bulk,
    hkl: tuple[int, int, int],
    layers: int,
    *,
    vacuum: float = 10.0,
    reduce_inplane: bool = True,
    center_slab: bool = True,
    tolerance: float = 0.3,
    position_tolerance_frac: float = 1e-6,
    stacking_tolerance_frac: float = 1e-8,
    max_stacking_order: int = 96,
    surface_symmetry_mode: str = "discover",
    surface_symprec: float | None = None,
    surface_angle_tolerance: float = 1e-8,
    surface_metric_tolerance: float = 1e-5,
) -> list[EnumeratedTermination]:
    """Build every canonical decorated termination class."""

    candidates = identify_unique_terminations(
        bulk,
        hkl,
        layers=layers,
        tolerance=tolerance,
        position_tolerance_frac=position_tolerance_frac,
        stacking_tolerance_frac=stacking_tolerance_frac,
        max_stacking_order=max_stacking_order,
        surface_symmetry_mode=surface_symmetry_mode,
        surface_symprec=surface_symprec,
        surface_angle_tolerance=surface_angle_tolerance,
        surface_metric_tolerance=surface_metric_tolerance,
    )
    results: list[EnumeratedTermination] = []
    for candidate in candidates:
        shift = int(candidate["shift"])
        label = str(candidate["label"])
        slab, actual_label = build_slab_with_termination(
            bulk,
            hkl,
            layers,
            termination_shift=shift,
            termination_label=label,
            vacuum=vacuum,
            reduce_inplane=reduce_inplane,
            center_slab=center_slab,
            tolerance=tolerance,
            position_tolerance_frac=position_tolerance_frac,
            stacking_tolerance_frac=stacking_tolerance_frac,
            max_stacking_order=max_stacking_order,
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=surface_symprec,
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=surface_metric_tolerance,
        )
        results.append(
            EnumeratedTermination(
                slab=slab,
                label=actual_label,
                shift=shift,
                metadata=dict(candidate),
            )
        )
    return results


def has_multiple_enumerated_terminations(
    bulk: Bulk,
    hkl: tuple[int, int, int],
    tolerance: float = 0.3,
    *,
    surface_symmetry_mode: str = "discover",
    surface_symprec: float | None = None,
    surface_angle_tolerance: float = 1e-8,
    surface_metric_tolerance: float = 1e-5,
) -> bool:
    """Return whether decorated ideal-truncation enumeration finds many classes."""

    return (
        len(
            identify_unique_terminations(
                bulk,
                hkl,
                layers=10,
                tolerance=tolerance,
                surface_symmetry_mode=surface_symmetry_mode,
                surface_symprec=surface_symprec,
                surface_angle_tolerance=surface_angle_tolerance,
                surface_metric_tolerance=surface_metric_tolerance,
            )
        )
        > 1
    )
