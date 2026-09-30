"""Exact persistence service for derived interface specifications."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from calm.project.domain.contracts.derived_interface import (
    DERIVED_INTERFACE_SPEC_SCHEMA,
    DERIVED_INTERFACE_SPEC_VERSION,
    canonical_derived_interface_spec,
    canonical_interface_stage,
    canonical_registry_shift,
)
from calm.project.domain.identity_v2 import (
    derived_interface_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.contracts.strain_state import strain_state_from_current_object

from ..domain.models import DerivedInterface
from ._json import json_native
from ._uow import fresh_uow, require_entered_uow, require_uow_factory


def _require_exact_mapping_keys(name: str, value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or not key or key != key.strip():
                raise TypeError(
                    f"{name} keys must be non-empty, whitespace-trimmed strings."
                )
            _require_exact_mapping_keys(f"{name}.{key}", item)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_exact_mapping_keys(f"{name}[{index}]", item)


class DerivedInterfaceService:
    """Own derived-interface identity, artifacts, rows, and lineage."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        artifacts: Any | None = None,
    ) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="DerivedInterfaceService",
        )
        self._artifacts = artifacts

    def create(
        self,
        *,
        prototype: str,
        label: str | None = None,
        stage: str | None = None,
        strain_alpha: float | None = None,
        registry_shift_frac_a: Sequence[float] | None = None,
        z_padding: float | None = None,
        vacuum: float | None = None,
        inherit_seed_vacuum: bool = True,
        params: Mapping[str, Any] | None = None,
        atoms: Any | None = None,
        strain_state: Any | None = None,
        artifact_run: str | None = None,
    ) -> DerivedInterface:
        with fresh_uow(
            self._uow_factory,
            owner="DerivedInterfaceService",
        ) as uow:
            return self.create_in(
                uow,
                prototype=prototype,
                label=label,
                stage=stage,
                strain_alpha=strain_alpha,
                registry_shift_frac_a=registry_shift_frac_a,
                z_padding=z_padding,
                vacuum=vacuum,
                inherit_seed_vacuum=inherit_seed_vacuum,
                params=params,
                atoms=atoms,
                strain_state=strain_state,
                artifact_run=artifact_run,
            )

    def create_in(  # noqa: C901
        self,
        uow: Any,
        *,
        prototype: str,
        label: str | None = None,
        stage: str | None = None,
        strain_alpha: float | None = None,
        registry_shift_frac_a: Sequence[float] | None = None,
        z_padding: float | None = None,
        vacuum: float | None = None,
        inherit_seed_vacuum: bool = True,
        params: Mapping[str, Any] | None = None,
        atoms: Any | None = None,
        strain_state: Any | None = None,
        inherit_seed_strain_state: bool = True,
        artifact_run: str | None = None,
    ) -> DerivedInterface:
        """Persist one current derived-interface record in an active transaction."""

        require_entered_uow(uow, owner="DerivedInterfaceService.create_in")
        if not isinstance(inherit_seed_vacuum, bool):
            raise TypeError("inherit_seed_vacuum must be a bool.")
        if not isinstance(inherit_seed_strain_state, bool):
            raise TypeError("inherit_seed_strain_state must be a bool.")
        if (
            not isinstance(prototype, str)
            or not prototype
            or prototype != prototype.strip()
        ):
            raise TypeError(
                "prototype must be a non-empty, whitespace-trimmed identifier."
            )
        identifier = prototype

        seed_iface_uid_full: str | None = None
        if identifier.startswith("i_") or identifier.startswith("iface:"):
            seed_iface_uid_full = uow.ids.resolve(identifier, expected_tag="i")
            seed_iface = uow.derived_interfaces.get_by_uid_full(seed_iface_uid_full)
            if seed_iface is None:
                raise KeyError(
                    f"No derived interface found for identifier {prototype!r}"
                )
            prototype_uid_full = seed_iface.prototype_uid_full
            if stage is None:
                stage = seed_iface.stage
            seed_strain_alpha = seed_iface.strain_alpha
            if strain_alpha is None:
                strain_alpha = seed_strain_alpha
            if registry_shift_frac_a is None:
                registry_shift_frac_a = seed_iface.registry_shift_frac_a
            if z_padding is None:
                z_padding = seed_iface.z_padding
            if vacuum is None and inherit_seed_vacuum:
                vacuum = seed_iface.vacuum
            if (
                strain_state is None
                and inherit_seed_strain_state
                and float(strain_alpha) == float(seed_strain_alpha)
            ):
                strain_state = seed_iface.strain_state
            merged_params = seed_iface.params
            if params is not None:
                merged_params.update(dict(params))
            params = merged_params
        else:
            prototype_uid_full = uow.ids.resolve_prototype(identifier)
            if stage is None:
                stage = "built"
            if strain_alpha is None:
                strain_alpha = 0.5
            if registry_shift_frac_a is None:
                registry_shift_frac_a = (0.0, 0.0)
            if z_padding is None:
                z_padding = 1.5
            if uow.prototypes.get_by_uid_full(prototype_uid_full) is None:
                raise KeyError(f"Prototype not found: {prototype!r}")

        if (
            stage is None
            or strain_alpha is None
            or registry_shift_frac_a is None
            or z_padding is None
        ):
            raise RuntimeError("Derived-interface defaults were not resolved.")
        raw_params = dict(params or {})
        _require_exact_mapping_keys("Derived-interface params", raw_params)
        spec: dict[str, Any] = {
            "schema": DERIVED_INTERFACE_SPEC_SCHEMA,
            "version": DERIVED_INTERFACE_SPEC_VERSION,
            "prototype": prototype_uid_full,
            "stage": canonical_interface_stage(stage),
            "strain_alpha": strain_alpha,
            "registry_shift_frac_a": canonical_registry_shift(registry_shift_frac_a),
            "z_padding": z_padding,
            "vacuum": vacuum,
            "params": json_native(raw_params),
        }
        if strain_state is not None:
            spec["strain_state"] = strain_state_from_current_object(
                strain_state,
                prototype_uid_full=prototype_uid_full,
                strain_alpha=float(strain_alpha),
            )

        spec = canonical_derived_interface_spec(
            spec,
            prototype_uid_full=prototype_uid_full,
        )

        canonical_uid = persisted_entity_uid_v2(
            "derived_interface",
            derived_interface_identity_payload(
                prototype_uid_full=prototype_uid_full,
                spec=spec,
            ),
        )

        if atoms is not None:
            if self._artifacts is None:
                raise RuntimeError(
                    "Artifact service required to persist derived-interface atoms."
                )
            atoms_dict = self._serialize_atoms(atoms)
            run_uid = self._artifact_run_uid(
                uow,
                prototype_uid_full=prototype_uid_full,
                artifact_run=artifact_run,
            )
            artifact = self._artifacts.put_interface_atoms_in(
                uow,
                run_uid,
                interface_uid_full=canonical_uid,
                obj=atoms_dict,
                filename=(
                    f"interface_atoms_{canonical_uid.split(':', 1)[-1][:16]}.json"
                ),
                metadata={"prototype_uid_full": prototype_uid_full},
            )
            spec["atoms_artifact_uid"] = artifact.uid_full
            refs = list(spec.get("artifact_refs") or [])
            refs.append(
                {
                    "artifact_uid": artifact.uid_full,
                    "kind": artifact.kind,
                    "role": "derived_interface_atoms",
                    "uri": artifact.uri,
                }
            )
            spec["artifact_refs"] = refs

        spec = canonical_derived_interface_spec(
            spec,
            prototype_uid_full=prototype_uid_full,
        )
        iface = DerivedInterface(
            uid_full=canonical_uid,
            id_short=uow.ids.ensure_short_id(
                tag="i",
                uid_full=canonical_uid,
            ),
            prototype_uid_full=prototype_uid_full,
            label=label,
            spec=spec,
        )
        stored = uow.derived_interfaces.upsert(iface)
        if (
            stored.uid_full != canonical_uid
            or stored.prototype_uid_full != prototype_uid_full
        ):
            raise RuntimeError(
                "Derived-interface repository returned an inconsistent row."
            )
        uow.edges.add(
            src_uid_full=prototype_uid_full,
            dst_uid_full=canonical_uid,
            kind="prototype_to_interface",
            payload=None,
        )
        if seed_iface_uid_full is not None and seed_iface_uid_full != canonical_uid:
            uow.edges.add(
                src_uid_full=seed_iface_uid_full,
                dst_uid_full=canonical_uid,
                kind="interface_to_interface",
                payload=None,
            )
        return stored

    def list(
        self,
        *,
        prototype: str | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[DerivedInterface]:
        with fresh_uow(
            self._uow_factory,
            owner="DerivedInterfaceService",
        ) as uow:
            prototype_uid_full = (
                uow.ids.resolve_prototype(prototype) if prototype else None
            )
            return uow.derived_interfaces.list(
                prototype_uid_full=prototype_uid_full,
                limit=limit,
                order_by=order_by,
                descending=descending,
            )

    @staticmethod
    def _serialize_atoms(atoms: Any) -> dict[str, Any]:
        from calm.slab.oriented.cell_contract import (
            validate_persisted_interface_deformation_payload,
        )
        from calm.structure.payloads import atoms_to_dict, canonical_atoms_payload

        payload = (
            canonical_atoms_payload(atoms)
            if isinstance(atoms, Mapping)
            else atoms_to_dict(atoms)
        )
        return validate_persisted_interface_deformation_payload(payload)

    @staticmethod
    def _artifact_run_uid(
        uow: Any,
        *,
        prototype_uid_full: str,
        artifact_run: str | None,
    ) -> str:
        if artifact_run is not None:
            return uow.ids.resolve_run(artifact_run)
        prototype = uow.prototypes.get_by_uid_full(prototype_uid_full)
        if prototype is None or not prototype.run_uid_full:
            raise RuntimeError(
                "Cannot determine artifact-producing run; supply artifact_run."
            )
        return prototype.run_uid_full
