"""Authoritative interface building from persisted prototypes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from calm.project.domain.contracts.derived_interface import (
    DERIVED_INTERFACE_SPEC_SCHEMA,
    DERIVED_INTERFACE_SPEC_VERSION,
    canonical_derived_interface_spec,
)

from ..ports.uow import UnitOfWork


@dataclass(frozen=True)
class BuiltInterfaceFromPrototype:
    """Live atomistic interface and its exact construction specification."""

    prototype_uid_full: str
    atoms: Any
    spec: dict[str, Any]


def build_interface_model_from_prototype(
    uow: UnitOfWork,
    prototype: str,
    *,
    alpha: float = 0.5,
    translation_frac: tuple[float, float] = (0.0, 0.0),
    z_padding: float = 1.5,
    vacuum: float | None = None,
) -> BuiltInterfaceFromPrototype:
    """Build one live interface from current authoritative project records.

    The caller owns the entered Unit-of-Work scope. Identifier-resolution and
    repository errors propagate; no supplied value is treated as a canonical
    UID merely because resolution failed.
    """

    if int(getattr(uow, "_depth", 0) or 0) <= 0:
        raise ValueError(
            "build_interface_model_from_prototype requires an entered UnitOfWork."
        )
    prototype_uid_full = uow.ids.resolve_prototype(prototype)

    # Keep the ASE-backed implementation outside this module's import boundary
    # so dependency-light orchestration and ownership checks can import it.
    from .followups.interface_energy import (
        build_interface_from_prototype_with_strain,
    )

    atoms = build_interface_from_prototype_with_strain(
        uow,
        prototype_uid_full,
        alpha=alpha,
        translation_frac=translation_frac,
        z_padding=z_padding,
        vacuum_padding=vacuum,
    )

    spec = canonical_derived_interface_spec(
        {
            "schema": DERIVED_INTERFACE_SPEC_SCHEMA,
            "version": DERIVED_INTERFACE_SPEC_VERSION,
            "prototype": prototype_uid_full,
            "stage": "built",
            "strain_alpha": float(alpha),
            "registry_shift_frac_a": [
                float(translation_frac[0]),
                float(translation_frac[1]),
            ],
            "z_padding": float(z_padding),
            "vacuum": None if vacuum is None else float(vacuum),
            "params": {},
        },
        prototype_uid_full=prototype_uid_full,
    )

    return BuiltInterfaceFromPrototype(
        prototype_uid_full=prototype_uid_full,
        atoms=atoms,
        spec=spec,
    )
