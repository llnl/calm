"""Application services for slabs.

This module is part of the "application" layer.

The slab vertical slice in Milestone 3 is intentionally minimal: it persists
slab records keyed by a deterministic UID derived from the bulk UID, Miller
index, and build parameters.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from calm.project.domain.contracts.slab_record import (
    SLAB_RECORD_SCHEMA,
    SLAB_RECORD_VERSION,
    canonical_miller,
    canonical_slab_record_payload,
)
from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    slab_identity_payload,
)

from ..domain.models import Slab, SlabSummary
from ._uow import fresh_uow, require_uow_factory


def _build_selected_slab_atoms(
    *,
    bulk_obj: Any,
    miller: tuple[int, int, int],
    layers: int,
    vacuum: float,
    reduce_inplane: bool,
    center_slab: bool,
    termination_shift: int,
    termination_metadata: dict[str, Any] | None,
    target_width: float | None,
    width_tolerance: float,
    max_n_layers: int,
) -> tuple[Any, str, int]:
    """Build one slab under the authoritative target-width contract."""

    from calm.slab.oriented._thickness import (
        SlabThicknessLimitError,
        plan_target_width_layers,
        target_width_is_satisfied,
    )

    layer_count = int(layers)
    if target_width is not None:
        plan = plan_target_width_layers(
            bulk_obj.conv.cell.array,
            miller,
            target_width_A=target_width,
            width_tolerance_A=width_tolerance,
            max_n_layers=max_n_layers,
        )
        layer_count = plan.required_layers

    metadata = termination_metadata or {}
    surface_symmetry = metadata.get("surface_symmetry")
    if surface_symmetry is None:
        symmetry_mode = "discover"
        symmetry_symprec = None
        symmetry_angle_tolerance = 1e-8
        symmetry_metric_tolerance = 1e-5
    elif isinstance(surface_symmetry, dict):
        from calm.symmetry.surface_group import SurfaceSymmetryProvenance

        symmetry_provenance = SurfaceSymmetryProvenance(**surface_symmetry)
        if symmetry_provenance.status == "failed":
            raise ValueError(
                "Persisted termination symmetry provenance cannot be failed."
            )
        symmetry_mode = symmetry_provenance.mode
        symmetry_symprec = symmetry_provenance.symprec
        symmetry_angle_tolerance = symmetry_provenance.angle_tolerance
        symmetry_metric_tolerance = symmetry_provenance.metric_tolerance
    else:
        raise TypeError(
            "Persisted termination surface_symmetry provenance must be a "
            "mapping or null."
        )

    def build(candidate_layers: int) -> tuple[Any, str]:
        if termination_metadata is None and termination_shift == 0:
            from calm.slab.oriented.model import build_oriented_slab

            result = build_oriented_slab(
                bulk_obj,
                hkl=miller,
                layers=candidate_layers,
                vacuum=vacuum,
                reduce_inplane=reduce_inplane,
                center_slab=center_slab,
            )
            return result.slab, "default"

        from calm.slab.oriented.terminations import build_slab_with_termination

        slab_atoms, actual_label = build_slab_with_termination(
            bulk_obj,
            hkl=miller,
            layers=candidate_layers,
            termination_shift=termination_shift,
            termination_label=metadata.get("label"),
            vacuum=vacuum,
            reduce_inplane=reduce_inplane,
            center_slab=center_slab,
            tolerance=float(metadata.get("layer_tolerance_A", 0.3)),
            position_tolerance_frac=float(
                metadata.get("position_tolerance_frac", 1e-6)
            ),
            stacking_tolerance_frac=float(
                metadata.get("stacking_tolerance_frac", 1e-8)
            ),
            surface_symmetry_mode=symmetry_mode,
            surface_symprec=symmetry_symprec,
            surface_angle_tolerance=symmetry_angle_tolerance,
            surface_metric_tolerance=symmetry_metric_tolerance,
        )
        return slab_atoms, str(actual_label)

    while True:
        slab_atoms, termination_label = build(layer_count)
        if target_width is None:
            return slab_atoms, termination_label, layer_count
        positions = slab_atoms.get_positions()
        actual_span = float(positions[:, 2].max() - positions[:, 2].min())
        if target_width_is_satisfied(
            actual_span,
            target_width_A=target_width,
            width_tolerance_A=width_tolerance,
        ):
            return slab_atoms, termination_label, layer_count
        if layer_count >= max_n_layers:
            raise SlabThicknessLimitError(
                "The selected slab termination did not satisfy target_width "
                f"within max_n_layers={max_n_layers}: measured atom span="
                f"{actual_span:.12g} angstrom, requested target_width="
                f"{target_width:.12g} angstrom with width_tol="
                f"{width_tolerance:.12g} angstrom."
            )
        layer_count += 1


def _build_slab_atoms_if_available(
    *,
    bulk_payload: dict[str, Any],
    miller: tuple[int, int, int],
    vacuum: float,
    termination_shift: int = 0,
    termination_metadata: dict[str, Any] | None = None,
    material: str | None = None,
) -> dict[str, Any] | None:
    """Build one atomistic slab when the parent bulk carries atoms.

    A missing parent ``atoms`` payload is the only condition that produces a
    spec-only slab. Once atomistic construction is possible, every parsing,
    construction, provenance, and characterization failure propagates to the
    caller. CALM never converts a failed scientific build into a spec-only
    result.
    """

    atoms_dict = bulk_payload.get("atoms")
    if atoms_dict is None:
        return None
    if not isinstance(atoms_dict, dict):
        raise TypeError("Current bulk atoms payload must be a mapping.")

    import numpy as np

    from calm.bulk.bulk import Bulk
    from calm.structure.payloads import atoms_from_dict

    bulk_atoms = atoms_from_dict(atoms_dict)
    bulk_obj = Bulk(bulk_atoms)

    params_raw = bulk_payload.get("params")
    if params_raw is None:
        params: dict[str, Any] = {}
    elif isinstance(params_raw, dict):
        params = params_raw
    else:
        raise TypeError("Slab build parameters must be a mapping.")

    layers = int(params.get("layers", 4))
    reduce_inplane = params.get("reduce_inplane", True)
    center_slab = params.get("center_slab", True)
    target_width_raw = params.get("target_width")
    target_width = None if target_width_raw is None else float(target_width_raw)
    width_tolerance = float(params.get("width_tol", 1e-4))
    max_n_layers = int(params.get("max_n_layers", max(10, layers)))

    slab_atoms, termination_label, actual_layers = _build_selected_slab_atoms(
        bulk_obj=bulk_obj,
        miller=miller,
        layers=layers,
        vacuum=vacuum,
        reduce_inplane=reduce_inplane,
        center_slab=center_slab,
        termination_shift=termination_shift,
        termination_metadata=termination_metadata,
        target_width=target_width,
        width_tolerance=width_tolerance,
        max_n_layers=max_n_layers,
    )

    from calm.slab.oriented.terminations import _cluster_atoms_by_z

    layer_list = _cluster_atoms_by_z(slab_atoms, tolerance=0.3)
    if layer_list:
        termination_bottom = layer_list[0].composition
        termination_top = layer_list[-1].composition
        if termination_metadata is None and termination_shift == 0:
            termination_label = termination_top
    else:
        termination_top = str(termination_label)
        termination_bottom = str(termination_label)

    cell = slab_atoms.get_cell()
    area = float(np.linalg.norm(np.cross(cell[0], cell[1])))
    natoms = len(slab_atoms)

    from calm.slab.oriented.tilt import compute_slab_tilt_metadata
    from calm.slab.oriented.transforms import (
        ORIENTED_SLAB_TRANSFORMS_INFO_KEY,
        from_transforms_payload,
    )
    from calm.structure.payloads import atoms_to_dict

    if "calm:tilt" not in slab_atoms.info:
        transforms_payload = slab_atoms.info.get(
            ORIENTED_SLAB_TRANSFORMS_INFO_KEY
        )
        transforms = (
            None
            if transforms_payload is None
            else from_transforms_payload(transforms_payload)
        )
        slab_atoms.info["calm:tilt"] = compute_slab_tilt_metadata(
            slab_atoms,
            transforms=transforms,
        )
    atoms_payload = atoms_to_dict(slab_atoms)

    result_dict = {
        **atoms_payload,
        "area_A2": float(area),
        "n_atoms": natoms,
    }

    if termination_label is not None:
        result_dict["termination"] = termination_label
        result_dict["termination_shift"] = termination_shift
        result_dict["termination_top"] = termination_top
        result_dict["termination_bottom"] = termination_bottom
        if termination_metadata is not None:
            for key in (
                "termination_identity_version",
                "termination_identity_scheme",
                "termination_identity",
                "termination_top_identity",
                "termination_bottom_identity",
                "termination_pair_identity",
                "decorated_stacking_period_layers",
                "stacking_translation_order",
                "stacking_translation_frac",
                "cut_fractional",
                "layer_tolerance_A",
                "position_tolerance_frac",
                "stacking_tolerance_frac",
                "surface_symmetry",
            ):
                if key in termination_metadata:
                    result_dict[key] = termination_metadata[key]

    from calm.structure.characterization import (
        material_characterization_data,
        surface_characterization_data,
    )

    parent_characterization = bulk_payload.get("characterization")
    if not isinstance(parent_characterization, dict):
        parent_characterization = material_characterization_data(
            bulk_atoms,
            material=material,
            derived=(
                bulk_payload.get("derived")
                if isinstance(bulk_payload.get("derived"), dict)
                else None
            ),
        )
    result_dict["characterization"] = surface_characterization_data(
        slab_atoms,
        parent_characterization=parent_characterization,
        material=material,
        miller=miller,
        termination=result_dict.get("termination"),
        termination_top=result_dict.get("termination_top"),
        termination_bottom=result_dict.get("termination_bottom"),
        termination_shift=termination_shift,
        layers=actual_layers,
        area_A2=area,
        vacuum_A=vacuum,
    )

    return result_dict


def _normalized_slab_build_params(
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return build parameters with identity-affecting policy provenance."""

    normalized = dict(params or {})
    if normalized.get("target_width") is not None:
        from calm.slab.oriented._thickness import target_width_policy_metadata

        normalized.update(target_width_policy_metadata())
    return normalized


class SlabsService:
    """Slab application service."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="SlabsService",
        )

    def _get_terminations_for_miller(
        self,
        bulk: Any,  # Bulk domain object
        miller: tuple[int, int, int],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return decorated version-2 termination metadata for one surface."""
        # Get bulk atoms from payload
        bulk_payload = bulk.payload or {}
        atoms_dict = bulk_payload.get("atoms")

        if atoms_dict is None:
            raise ValueError(
                "Termination enumeration requires a persisted bulk structure."
            )

        from calm.bulk.bulk import Bulk as CALMBulk
        from calm.slab.oriented.terminations import (
            identify_unique_terminations,
        )
        from calm.structure.payloads import atoms_from_dict

        bulk_atoms = atoms_from_dict(atoms_dict)
        symprec = params.get("symprec", 1e-5)
        bulk_obj = CALMBulk(bulk_atoms, symprec=symprec)

        layers = int(params.get("layers", 4))
        return identify_unique_terminations(
            bulk_obj,
            hkl=miller,
            layers=layers,
            surface_symmetry_mode=params.get(
                "surface_symmetry_mode",
                "discover",
            ),
            surface_symprec=params.get("surface_symprec", symprec),
            surface_angle_tolerance=params.get(
                "surface_angle_tolerance",
                1e-8,
            ),
            surface_metric_tolerance=params.get(
                "surface_metric_tolerance",
                1e-5,
            ),
        )

    def build_slabs(  # noqa: C901
        self,
        bulk_id: str,
        *,
        millers: Sequence[tuple[int, int, int]],
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        enumerate_terminations: bool = False,
    ) -> list[Slab]:
        """Persist slabs for a bulk and a set of Miller indices.

        Parameters
        ----------
        bulk_id
            Bulk identifier (short ID or full UID).
        millers
            Miller indices to build.
        params
            Deterministic build parameters included in the slab UID.
        payload
            Optional user payload. Included in the UID to keep the operation
            idempotent with respect to the full build spec.
        enumerate_terminations
            If True, enumerate the termination candidates identified by the
            current bulk-layer algorithm and create one slab entry per candidate.
            This option does not classify surface polarity.
        """

        # Resolve + persist within a single UnitOfWork context so repositories
        # always reference an open connection.
        with fresh_uow(self._uow_factory, owner="SlabsService") as uow:
            bulk_uid_full = uow.ids.resolve(bulk_id)
            bulk = uow.bulks.get_by_uid_full(bulk_uid_full)
            if bulk is None:
                raise KeyError(f"Bulk not found: {bulk_id}")

            slabs: list[Slab] = []
            normalized_params = _normalized_slab_build_params(params)

            # Determine terminations to build for each Miller index
            for miller_value in millers:
                miller = canonical_miller(miller_value)
                if enumerate_terminations:
                    # Enumerate all unique terminations for this surface
                    terminations_to_build = self._get_terminations_for_miller(
                        bulk, miller, params or {}
                    )
                else:
                    terminations_to_build = [None]

                for termination_meta in terminations_to_build:
                    if termination_meta is None:
                        termination_shift = 0
                        termination_label = None
                    elif isinstance(termination_meta, dict):
                        termination_shift = int(termination_meta.get("shift", 0))
                        termination_label = termination_meta.get("label")
                    else:
                        raise TypeError(
                            "Current termination enumeration must return mappings."
                        )
                    identity_record = None
                    if termination_meta is not None and any(
                        key in termination_meta
                        for key in (
                            "termination_identity",
                            "termination_top_identity",
                            "termination_bottom_identity",
                            "termination_pair_identity",
                        )
                    ):
                        identity_record = {
                            "version": termination_meta.get(
                                "termination_identity_version"
                            ),
                            "scheme": termination_meta.get(
                                "termination_identity_scheme"
                            ),
                            "primary": termination_meta.get("termination_identity"),
                            "top": termination_meta.get("termination_top_identity"),
                            "bottom": termination_meta.get(
                                "termination_bottom_identity"
                            ),
                            "pair": termination_meta.get("termination_pair_identity"),
                            "decorated_stacking_period_layers": termination_meta.get(
                                "decorated_stacking_period_layers"
                            ),
                            "stacking_translation_order": termination_meta.get(
                                "stacking_translation_order"
                            ),
                            "stacking_translation_frac": termination_meta.get(
                                "stacking_translation_frac"
                            ),
                            "cut_fractional": termination_meta.get("cut_fractional"),
                            "layer_tolerance_A": termination_meta.get(
                                "layer_tolerance_A"
                            ),
                            "position_tolerance_frac": termination_meta.get(
                                "position_tolerance_frac"
                            ),
                            "stacking_tolerance_frac": termination_meta.get(
                                "stacking_tolerance_frac"
                            ),
                            "surface_symmetry": termination_meta.get(
                                "surface_symmetry"
                            ),
                        }
                    slab_payload: dict[str, Any] = {
                        "schema": SLAB_RECORD_SCHEMA,
                        "version": SLAB_RECORD_VERSION,
                        "params": normalized_params,
                        "user_payload": dict(payload or {}),
                        "termination": {
                            "label": termination_label,
                            "shift": termination_shift,
                            "top": (
                                termination_meta.get("top_composition")
                                if termination_meta is not None
                                else None
                            ),
                            "bottom": (
                                termination_meta.get("bottom_composition")
                                if termination_meta is not None
                                else None
                            ),
                            "identity": identity_record,
                        },
                        "structure": {
                            "atoms": None,
                            "n_atoms": None,
                            "area_A2": None,
                            "formula": None,
                            "slab_thickness_A": None,
                            "vacuum_A": None,
                            "layers": None,
                            "characterization": None,
                        },
                    }

                    # The authoritative parent bulk is the sole atomistic input.
                    # The optional slab payload is user metadata and never a
                    # competing structure source.
                    vacuum = float(normalized_params.get("vacuum", 10.0))
                    bulk_payload = dict(bulk.payload or {})
                    bulk_payload["params"] = normalized_params
                    built = _build_slab_atoms_if_available(
                        bulk_payload=bulk_payload,
                        miller=miller,
                        vacuum=vacuum,
                        termination_shift=termination_shift,
                        termination_metadata=termination_meta,
                        material=bulk.label,
                    )
                    if built is not None:
                        characterization = built.get("characterization")
                        atoms_dict = {
                            key: built[key]
                            for key in (
                                "numbers",
                                "cell",
                                "scaled_positions",
                                "pbc",
                                "info",
                            )
                            if key in built
                        }
                        slab_payload["structure"] = {
                            "atoms": atoms_dict,
                            "n_atoms": built.get("n_atoms"),
                            "area_A2": built.get("area_A2"),
                            "formula": (
                                characterization.get("formula")
                                if isinstance(characterization, dict)
                                else None
                            ),
                            "slab_thickness_A": (
                                characterization.get("slab_thickness_A")
                                if isinstance(characterization, dict)
                                else None
                            ),
                            "vacuum_A": (
                                characterization.get("vacuum_A")
                                if isinstance(characterization, dict)
                                else None
                            ),
                            "layers": (
                                characterization.get("layers")
                                if isinstance(characterization, dict)
                                else None
                            ),
                            "characterization": characterization,
                        }
                        term = slab_payload["termination"]
                        term_from_build = built.get("termination")
                        if term_from_build is not None:
                            term["label"] = str(term_from_build)
                            term["top"] = str(
                                built.get("termination_top", term_from_build)
                            )
                            term["bottom"] = str(
                                built.get("termination_bottom", term_from_build)
                            )

                    slab_payload = canonical_slab_record_payload(
                        slab_payload,
                        bulk_uid_full=bulk_uid_full,
                        miller=miller,
                    )

                    uid_full = persisted_entity_uid_v2(
                        "slab",
                        slab_identity_payload(
                            bulk_uid_full=bulk_uid_full,
                            miller=miller,
                            payload=slab_payload,
                        ),
                    )
                    id_short = uow.ids.ensure_short_id(tag="s", uid_full=uid_full)

                    slabs.append(
                        Slab(
                            uid_full=uid_full,
                            id_short=id_short,
                            bulk_uid_full=bulk_uid_full,
                            bulk_id_short=bulk.id_short,
                            miller=miller,
                            payload=slab_payload,
                        )
                    )

            out = uow.slabs.create_many(slabs)

            # Provenance edges (bulk -> slab).
            for s in out:
                if not s.uid_full:
                    continue
                edge_payload = (
                    {"miller": list(s.miller)} if s.miller is not None else None
                )
                uow.edges.add(
                    src_uid_full=bulk_uid_full,
                    dst_uid_full=s.uid_full,
                    kind="bulk_to_slab",
                    payload=edge_payload,
                )

            return out

    def list_slabs(
        self,
        *,
        bulk_id: str | None = None,
        limit: int = 50,
    ) -> list[SlabSummary]:
        with fresh_uow(self._uow_factory, owner="SlabsService") as uow:
            bulk_uid_full = uow.ids.resolve(bulk_id) if bulk_id else None
            return uow.slabs.list(bulk_uid_full=bulk_uid_full, limit=limit)
