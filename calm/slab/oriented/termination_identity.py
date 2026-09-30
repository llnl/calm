"""Canonical decorated termination identities for ideal bulk truncations."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable, Sequence

import numpy as np

from calm.symmetry.surface_group import validate_surface_symmetry_group_2d

TERMINATION_IDENTITY_VERSION = 2
TERMINATION_IDENTITY_SCHEME = "decorated_periodic_halfspace_v2"


@dataclass(frozen=True)
class DecoratedLayerAtom:
    """One species-labelled point in surface fractional coordinates."""

    symbol: str
    uv: tuple[float, float]


@dataclass(frozen=True)
class DecoratedPeriodicLayer:
    """One atomic layer inside a stacking-translation repeat."""

    phase: float
    height_A: float
    atom_indices: tuple[int, ...]
    composition: str
    stoichiometry: tuple[tuple[str, int], ...]
    atoms: tuple[DecoratedLayerAtom, ...]


@dataclass(frozen=True)
class DecoratedTerminationClass:
    """Canonical termination class and finite-slab top/bottom pairing."""

    representative_layer_index: int
    equivalent_layer_indices: tuple[int, ...]
    cut_fractional: float
    top_identity: dict[str, object]
    bottom_identity: dict[str, object]
    pair_identity: dict[str, object]
    top_signature: tuple
    bottom_signature: tuple


def _positive_finite(name: str, value: float) -> float:
    result = float(value)
    if not isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


def _positive_integer(name: str, value: int) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    result = int(value)
    if result != value or result <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return result


def _wrap_unit(value: float) -> float:
    wrapped = float(value) % 1.0
    return 0.0 if wrapped == 1.0 else wrapped


def _quantize_unit(value: float, tolerance: float) -> int:
    tol = _positive_finite("position_tolerance_frac", tolerance)
    wrapped = _wrap_unit(value)
    if wrapped <= tol or 1.0 - wrapped <= tol:
        return 0
    return int(np.rint(wrapped / tol))


def _quantize_length(value: float, tolerance: float) -> int:
    tol = _positive_finite("height_tolerance_A", tolerance)
    if not isfinite(float(value)) or value < -tol:
        raise ValueError("relative layer depth must be finite and nonnegative")
    return int(np.rint(max(0.0, float(value)) / tol))


def normalize_surface_operations(
    operations: Iterable[np.ndarray] | None,
) -> tuple[np.ndarray, ...]:
    """Validate and deterministically order a finite 2D symmetry group."""

    candidates: Iterable[np.ndarray]
    if operations is None:
        candidates = (np.eye(2, dtype=int),)
    else:
        candidates = operations
    return validate_surface_symmetry_group_2d(candidates)


def stacking_translation_order(
    translation_frac: Sequence[float],
    *,
    tolerance: float = 1e-8,
    max_order: int = 96,
) -> int:
    """Return the finite order of a translation on the surface torus."""

    tol = _positive_finite("stacking_tolerance_frac", tolerance)
    bound = _positive_integer("max_stacking_order", max_order)
    translation = np.asarray(translation_frac, dtype=float)
    if translation.shape != (2,) or not np.all(np.isfinite(translation)):
        raise ValueError("translation_frac must be a finite length-2 vector")
    for order in range(1, bound + 1):
        residual = order * translation - np.rint(order * translation)
        if float(np.max(np.abs(residual))) <= tol:
            return order
    raise ValueError(
        "Unable to establish a finite stacking-translation order within "
        f"max_order={bound} and tolerance={tol:.3e}."
    )


def _expanded_period(
    layers: Sequence[DecoratedPeriodicLayer],
    *,
    translation_frac: np.ndarray,
    translation_order: int,
    normal_period_A: float,
) -> tuple[tuple[float, DecoratedPeriodicLayer], ...]:
    period = _positive_finite("normal_period_A", normal_period_A)
    if not layers:
        raise ValueError("at least one decorated layer is required")
    expanded: list[tuple[float, DecoratedPeriodicLayer]] = []
    for repeat in range(translation_order):
        translation = repeat * translation_frac
        for layer in layers:
            atoms = tuple(
                DecoratedLayerAtom(
                    symbol=str(atom.symbol),
                    uv=(
                        _wrap_unit(atom.uv[0] + translation[0]),
                        _wrap_unit(atom.uv[1] + translation[1]),
                    ),
                )
                for atom in layer.atoms
            )
            expanded.append(
                (
                    repeat + _wrap_unit(layer.phase),
                    DecoratedPeriodicLayer(
                        phase=_wrap_unit(layer.phase),
                        height_A=_wrap_unit(layer.phase) * period,
                        atom_indices=tuple(layer.atom_indices),
                        composition=str(layer.composition),
                        stoichiometry=tuple(layer.stoichiometry),
                        atoms=atoms,
                    ),
                )
            )
    expanded.sort(
        key=lambda item: (
            item[0],
            item[1].stoichiometry,
            tuple((atom.symbol, atom.uv) for atom in item[1].atoms),
        )
    )
    return tuple(expanded)


def _transformed_layer_key(
    layer: DecoratedPeriodicLayer,
    *,
    anchor: np.ndarray,
    operation: np.ndarray,
    position_tolerance_frac: float,
) -> tuple:
    points: list[tuple[str, int, int]] = []
    for atom in layer.atoms:
        transformed = operation @ (np.asarray(atom.uv) - anchor)
        points.append(
            (
                str(atom.symbol),
                _quantize_unit(float(transformed[0]), position_tolerance_frac),
                _quantize_unit(float(transformed[1]), position_tolerance_frac),
            )
        )
    return tuple(sorted(points))


def canonical_halfspace_signature(
    expanded_layers: Sequence[tuple[float, DecoratedPeriodicLayer]],
    *,
    root_index: int,
    direction: int,
    normal_period_A: float,
    translation_order: int,
    symmetry_operations: Iterable[np.ndarray] | None = None,
    height_tolerance_A: float = 1e-6,
    position_tolerance_frac: float = 1e-6,
) -> tuple:
    """Canonicalize one rooted decorated half-space sequence."""

    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or +1")
    if not expanded_layers:
        raise ValueError("expanded_layers cannot be empty")
    if not 0 <= int(root_index) < len(expanded_layers):
        raise IndexError("root_index is outside expanded_layers")
    height_tol = _positive_finite("height_tolerance_A", height_tolerance_A)
    position_tol = _positive_finite(
        "position_tolerance_frac",
        position_tolerance_frac,
    )
    period_A = _positive_finite("normal_period_A", normal_period_A)
    order = _positive_integer("translation_order", translation_order)
    operations = normalize_surface_operations(symmetry_operations)
    root_height, root_layer = expanded_layers[int(root_index)]
    if not root_layer.atoms:
        raise ValueError("the root layer must contain at least one atom")
    candidates: list[tuple] = []
    for operation in operations:
        for root_atom in root_layer.atoms:
            anchor = np.asarray(root_atom.uv, dtype=float)
            sequence: list[tuple] = []
            for step in range(len(expanded_layers)):
                index = (int(root_index) + direction * step) % len(expanded_layers)
                height, layer = expanded_layers[index]
                depth_periods = (
                    (root_height - height) % order
                    if direction < 0
                    else (height - root_height) % order
                )
                sequence.append(
                    (
                        _quantize_length(depth_periods * period_A, height_tol),
                        _transformed_layer_key(
                            layer,
                            anchor=anchor,
                            operation=operation,
                            position_tolerance_frac=position_tol,
                        ),
                    )
                )
            candidates.append(tuple(sequence))
    return min(candidates)


def _identity_payload(
    signature: tuple,
    *,
    orientation: str,
    layer_tolerance_A: float,
    position_tolerance_frac: float,
    stacking_tolerance_frac: float,
    translation_order: int,
) -> dict[str, object]:
    canonical = {
        "scheme": TERMINATION_IDENTITY_SCHEME,
        "version": TERMINATION_IDENTITY_VERSION,
        "orientation": str(orientation),
        "layer_tolerance_A": format(float(layer_tolerance_A), ".17g"),
        "position_tolerance_frac": format(
            float(position_tolerance_frac),
            ".17g",
        ),
        "stacking_tolerance_frac": format(
            float(stacking_tolerance_frac),
            ".17g",
        ),
        "translation_order": int(translation_order),
        "signature": signature,
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return {
        "version": TERMINATION_IDENTITY_VERSION,
        "scheme": TERMINATION_IDENTITY_SCHEME,
        "orientation": str(orientation),
        "digest": f"sha256:{sha256(encoded).hexdigest()}",
    }


def _pair_identity(
    top_identity: dict[str, object],
    bottom_identity: dict[str, object],
) -> dict[str, object]:
    payload = {
        "version": TERMINATION_IDENTITY_VERSION,
        "scheme": "ordered_termination_pair_v2",
        "top": top_identity,
        "bottom": bottom_identity,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return {
        "version": TERMINATION_IDENTITY_VERSION,
        "scheme": "ordered_termination_pair_v2",
        "digest": f"sha256:{sha256(encoded).hexdigest()}",
    }


def _cut_above_layer(
    layers: Sequence[DecoratedPeriodicLayer],
    root_index: int,
) -> float:
    current = _wrap_unit(layers[root_index].phase)
    following = _wrap_unit(layers[(root_index + 1) % len(layers)].phase)
    gap = (following - current) % 1.0
    return _wrap_unit(current + 0.5 * (gap if gap > 0.0 else 1.0))


def enumerate_decorated_termination_classes(
    layers: Sequence[DecoratedPeriodicLayer],
    *,
    stacking_translation_frac: Sequence[float],
    normal_period_A: float,
    slab_repeat_count: int,
    symmetry_operations: Iterable[np.ndarray] | None = None,
    layer_tolerance_A: float = 0.3,
    position_tolerance_frac: float = 1e-6,
    stacking_tolerance_frac: float = 1e-8,
    max_stacking_order: int = 96,
) -> tuple[DecoratedTerminationClass, ...]:
    """Enumerate unique ideal bulk-truncation classes."""

    if not layers:
        raise ValueError("at least one decorated layer is required")
    repeats = _positive_integer("slab_repeat_count", slab_repeat_count)
    layer_tol = _positive_finite("layer_tolerance_A", layer_tolerance_A)
    position_tol = _positive_finite(
        "position_tolerance_frac",
        position_tolerance_frac,
    )
    stacking_tol = _positive_finite(
        "stacking_tolerance_frac",
        stacking_tolerance_frac,
    )
    period_A = _positive_finite("normal_period_A", normal_period_A)
    ordered_layers = tuple(
        sorted(
            layers,
            key=lambda layer: (
                _wrap_unit(layer.phase),
                layer.stoichiometry,
                tuple((atom.symbol, atom.uv) for atom in layer.atoms),
            ),
        )
    )
    translation = np.asarray(stacking_translation_frac, dtype=float)
    order = stacking_translation_order(
        translation,
        tolerance=stacking_tol,
        max_order=max_stacking_order,
    )
    operations = normalize_surface_operations(symmetry_operations)
    expanded = _expanded_period(
        ordered_layers,
        translation_frac=translation,
        translation_order=order,
        normal_period_A=period_A,
    )
    grouped: dict[tuple, list[int]] = {}
    for root_index in range(len(ordered_layers)):
        signature = canonical_halfspace_signature(
            expanded,
            root_index=root_index,
            direction=-1,
            normal_period_A=period_A,
            translation_order=order,
            symmetry_operations=operations,
            height_tolerance_A=layer_tol,
            position_tolerance_frac=position_tol,
        )
        grouped.setdefault(signature, []).append(root_index)
    results: list[DecoratedTerminationClass] = []
    for top_signature, equivalent_indices in sorted(
        grouped.items(),
        key=lambda item: min(item[1]),
    ):
        representative = min(equivalent_indices)
        bottom_root = (representative - (repeats * len(ordered_layers) - 1)) % len(
            ordered_layers
        )
        bottom_signature = canonical_halfspace_signature(
            expanded,
            root_index=bottom_root,
            direction=+1,
            normal_period_A=period_A,
            translation_order=order,
            symmetry_operations=operations,
            height_tolerance_A=layer_tol,
            position_tolerance_frac=position_tol,
        )
        top_identity = _identity_payload(
            top_signature,
            orientation="plus_surface_normal",
            layer_tolerance_A=layer_tol,
            position_tolerance_frac=position_tol,
            stacking_tolerance_frac=stacking_tol,
            translation_order=order,
        )
        bottom_identity = _identity_payload(
            bottom_signature,
            orientation="minus_surface_normal",
            layer_tolerance_A=layer_tol,
            position_tolerance_frac=position_tol,
            stacking_tolerance_frac=stacking_tol,
            translation_order=order,
        )
        results.append(
            DecoratedTerminationClass(
                representative_layer_index=representative,
                equivalent_layer_indices=tuple(equivalent_indices),
                cut_fractional=_cut_above_layer(
                    ordered_layers,
                    representative,
                ),
                top_identity=top_identity,
                bottom_identity=bottom_identity,
                pair_identity=_pair_identity(top_identity, bottom_identity),
                top_signature=top_signature,
                bottom_signature=bottom_signature,
            )
        )
    return tuple(results)
