"""Current prototype strain-analysis application service."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import TYPE_CHECKING, Any

import numpy as np

from ._uow import fresh_uow, require_uow_factory
from .interface_prototype_payload import load_interface_prototype

if TYPE_CHECKING:
    from calm.interface.model import InterfacePrototype
    from calm.interface.refinement.analysis import StrainDecomposition

    from ..domain.models import Bulk, Slab


_ALPHA_CONVENTION = (
    "alpha=0 leaves A unstrained and deforms B to A; "
    "alpha=1 leaves B unstrained and deforms A to B"
)


@dataclass(frozen=True)
class _PrototypeAnalysisContext:
    prototype: InterfacePrototype
    slab_a: "Slab"
    slab_b: "Slab"
    bulk_a: "Bulk"
    bulk_b: "Bulk"


def _finite_real(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a finite real value.")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _alpha(value: Any) -> float:
    result = _finite_real("alpha", value)
    if not 0.0 <= result <= 1.0:
        raise ValueError("alpha must lie in [0, 1].")
    return result


def _positive_integer(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a positive integer.")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _to_subscript(text: str) -> str:
    return text.translate(str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉"))


def _decomposition_payload(
    decomposition: "StrainDecomposition",
) -> dict[str, Any]:
    directions = decomposition.principal_directions
    projector = decomposition.principal_eigenspace_projector
    return {
        "principal_strains": decomposition.principal_strains.tolist(),
        "principal_directions_cart": (
            None if directions is None else directions.tolist()
        ),
        "principal_direction_status": decomposition.direction_status,
        "principal_eigengap": decomposition.principal_eigengap,
        "principal_eigengap_threshold": (decomposition.principal_eigengap_threshold),
        "principal_eigenspace_projector": (
            None if projector is None else projector.tolist()
        ),
        "norm_E": decomposition.norm_E,
        "norm_E_area": decomposition.norm_E_area,
        "norm_E_shape": decomposition.norm_E_shape,
        "trace_E": decomposition.trace_E,
        "log_area_ratio": decomposition.log_area_ratio,
        "area_ratio": decomposition.area_ratio,
        "max_principal_strain": decomposition.max_principal_strain,
        "E": decomposition.E.tolist(),
        "E_area": decomposition.E_area.tolist(),
        "E_shape": decomposition.E_shape.tolist(),
    }


class PrototypeAnalysisService:
    """Analyze current persisted prototypes through one fresh Unit of Work."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="PrototypeAnalysisService",
        )

    def analyze_prototype_strain(
        self,
        prototype_id: str,
        *,
        alpha: float = 0.5,
        eigengap_atol: float = 1.0e-12,
        eigengap_rtol: float = 1.0e-3,
    ) -> dict[str, Any]:
        alpha_value = _alpha(alpha)
        atol = _finite_real("eigengap_atol", eigengap_atol)
        rtol = _finite_real("eigengap_rtol", eigengap_rtol)
        if atol < 0.0 or rtol < 0.0:
            raise ValueError("Eigenspace tolerances must be non-negative.")

        with fresh_uow(
            self._uow_factory,
            owner="PrototypeAnalysisService",
        ) as uow:
            context = self._load_context(uow, prototype_id)
            return self._strain_payload(
                context,
                alpha=alpha_value,
                eigengap_atol=atol,
                eigengap_rtol=rtol,
            )

    def get_principal_strain_directions_crystallographic(
        self,
        prototype_id: str,
        *,
        alpha: float = 0.5,
        eigengap_atol: float = 1.0e-12,
        eigengap_rtol: float = 1.0e-3,
        max_index: int = 6,
        max_angular_error_deg: float = 1.0,
    ) -> dict[str, Any]:
        alpha_value = _alpha(alpha)
        atol = _finite_real("eigengap_atol", eigengap_atol)
        rtol = _finite_real("eigengap_rtol", eigengap_rtol)
        angular_error = _finite_real(
            "max_angular_error_deg",
            max_angular_error_deg,
        )
        index = _positive_integer("max_index", max_index)
        if atol < 0.0 or rtol < 0.0 or angular_error < 0.0:
            raise ValueError("Analysis tolerances must be non-negative.")

        with fresh_uow(
            self._uow_factory,
            owner="PrototypeAnalysisService",
        ) as uow:
            context = self._load_context(uow, prototype_id)
            strain_info = self._strain_payload(
                context,
                alpha=alpha_value,
                eigengap_atol=atol,
                eigengap_rtol=rtol,
            )
            return {
                "direction_analysis_version": 2,
                "alpha": strain_info["alpha"],
                "alpha_convention": strain_info["alpha_convention"],
                "max_index": index,
                "max_angular_error_deg": angular_error,
                "slab_A": self._map_side(
                    strain_info["slab_A"],
                    slab_atoms=context.slab_a.atoms,
                    conventional_atoms=context.bulk_a.atoms_conventional,
                    max_index=index,
                    max_angular_error_deg=angular_error,
                ),
                "slab_B": self._map_side(
                    strain_info["slab_B"],
                    slab_atoms=context.slab_b.atoms,
                    conventional_atoms=context.bulk_b.atoms_conventional,
                    max_index=index,
                    max_angular_error_deg=angular_error,
                ),
            }

    @staticmethod
    def _load_context(uow: Any, prototype_id: str) -> _PrototypeAnalysisContext:
        identifier = str(prototype_id).strip()
        if not identifier:
            raise ValueError("prototype_id must be a non-empty identifier.")
        prototype_uid = uow.ids.resolve_prototype(identifier)
        prototype = load_interface_prototype(uow, prototype_uid)
        slab_a = prototype.slab_a
        slab_b = prototype.slab_b

        bulk_a = uow.bulks.get_by_uid_full(slab_a.bulk_uid_full)
        bulk_b = uow.bulks.get_by_uid_full(slab_b.bulk_uid_full)
        if bulk_a is None or bulk_b is None:
            raise RuntimeError("Prototype parent bulks are missing.")
        return _PrototypeAnalysisContext(
            prototype=prototype,
            slab_a=slab_a,
            slab_b=slab_b,
            bulk_a=bulk_a,
            bulk_b=bulk_b,
        )

    @staticmethod
    def _strain_payload(
        context: _PrototypeAnalysisContext,
        *,
        alpha: float,
        eigengap_atol: float,
        eigengap_rtol: float,
    ) -> dict[str, Any]:
        from calm.structure.ase_adapter import make_supercell_col
        from calm.interface.refinement.strain import compute_strain_2d
        from calm.interface.refinement.analysis import compute_strain_decomposition

        atoms_a = context.slab_a.atoms
        atoms_b = context.slab_b.atoms
        if atoms_a is None or atoms_b is None:
            raise RuntimeError("Prototype parent slab atoms are unavailable.")

        transform_a = np.asarray(
            context.prototype.supercell_a.N_tot,
            dtype=int,
        )
        transform_b = np.asarray(
            context.prototype.supercell_b.N_tot,
            dtype=int,
        )
        supercell_a = np.eye(3, dtype=int)
        supercell_b = np.eye(3, dtype=int)
        supercell_a[:2, :2] = transform_a
        supercell_b[:2, :2] = transform_b

        realized_a = make_supercell_col(atoms_a, supercell_a)
        realized_b = make_supercell_col(atoms_b, supercell_b)
        strain_state = compute_strain_2d(
            realized_a.get_cell().array.T,
            realized_b.get_cell().array.T,
            alpha=alpha,
        )
        decomposition_a = compute_strain_decomposition(
            strain_state.E_A[:2, :2],
            eigengap_atol=eigengap_atol,
            eigengap_rtol=eigengap_rtol,
        )
        decomposition_b = compute_strain_decomposition(
            strain_state.E_B[:2, :2],
            eigengap_atol=eigengap_atol,
            eigengap_rtol=eigengap_rtol,
        )
        return {
            "alpha": float(strain_state.alpha),
            "alpha_convention": _ALPHA_CONVENTION,
            "eigengap_atol": eigengap_atol,
            "eigengap_rtol": eigengap_rtol,
            "slab_A": _decomposition_payload(decomposition_a),
            "slab_B": _decomposition_payload(decomposition_b),
        }

    @staticmethod
    def _map_side(
        side: Mapping[str, Any],
        *,
        slab_atoms: Any,
        conventional_atoms: Any,
        max_index: int,
        max_angular_error_deg: float,
    ) -> dict[str, Any]:
        from calm.interface.refinement.analysis import (
            analyze_principal_directions_in_conventional_cell,
            slab_to_conventional_cartesian_map_from_payload,
        )
        from calm.slab.slab import get_oriented_slab_transforms_payload

        if slab_atoms is None or conventional_atoms is None:
            raise RuntimeError(
                "Principal-direction analysis requires slab and conventional atoms."
            )
        status = str(side["principal_direction_status"])
        common = {
            "principal_strains": side["principal_strains"],
            "principal_direction_status": status,
            "principal_eigengap": side["principal_eigengap"],
            "principal_eigengap_threshold": side["principal_eigengap_threshold"],
            "principal_eigenspace_projector": side["principal_eigenspace_projector"],
            "conventional_cell_formula": _to_subscript(
                conventional_atoms.get_chemical_formula(
                    mode="metal",
                    empirical=True,
                )
            ),
        }
        directions_raw = side["principal_directions_cart"]
        if status != "defined" or directions_raw is None:
            return {
                **common,
                "directions_cart": None,
                "directions_slab_cart": None,
                "directions_conventional_cart": None,
                "directions_conventional": None,
                "low_index_directions": None,
                "angular_errors_deg": None,
                "formatted": None,
            }

        transforms = get_oriented_slab_transforms_payload(
            slab_atoms,
            strict=True,
        )
        mapping = slab_to_conventional_cartesian_map_from_payload(transforms)
        result = analyze_principal_directions_in_conventional_cell(
            np.asarray(directions_raw, dtype=float),
            conventional_atoms.get_cell().array.T,
            mapping,
            max_index=max_index,
            max_angular_error_deg=max_angular_error_deg,
        )
        return {
            **common,
            "directions_cart": result.directions_slab_cart.tolist(),
            "directions_slab_cart": result.directions_slab_cart.tolist(),
            "directions_conventional_cart": (
                result.directions_conventional_cart.tolist()
            ),
            "directions_conventional": result.directions_conventional.tolist(),
            "low_index_directions": [
                None if item.integer_indices is None else list(item.integer_indices)
                for item in result.approximations
            ],
            "angular_errors_deg": [
                item.angular_error_deg for item in result.approximations
            ],
            "formatted": [item.formatted for item in result.approximations],
        }


__all__ = ["PrototypeAnalysisService"]
