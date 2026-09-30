"""Authoritative prototype search, persistence, and query services."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from calm.structure.standardization import (
    nonnegative_finite_float,
    positive_finite_float,
)
from calm.symmetry.surface_group import SURFACE_SYMMETRY_MODES
from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    is_authoritative_pareto_metadata,
    strain_size_pareto,
    strain_size_pareto_metadata,
)
from calm.interface.config import (
    CorrespondenceOrientation,
    DEFAULT_CORRESPONDENCE_ORIENTATION,
    DEFAULT_IDENTIFY_MATERIAL_EXCHANGE,
    DEFAULT_PAIR_SYMMETRY_POLICY,
    PairSymmetryPolicy,
    PrototypeSearchConfig,
)
from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    prototype_identity_payload,
    run_identity_payload,
)

from ..domain.models import Prototype, PrototypeSummary, Run
from ._uow import fresh_uow, require_uow_factory
from .runs import RunsService


def _prototype_d_cell(prototype: Prototype) -> float:
    payload = prototype.payload or {}
    metrics = payload.get("metrics") if isinstance(payload, Mapping) else None
    if not isinstance(metrics, Mapping) or metrics.get("d_cell") is None:
        raise ValueError(
            f"Prototype {prototype.uid_full!r} lacks coupled-v2 d_cell metadata."
        )
    return float(metrics["d_cell"])


def _compute_pareto_flags(
    protos: Sequence[Prototype],
    *,
    policy: str = STRAIN_SIZE_PARETO_POLICY,
    population_scope: str = STRAIN_SIZE_PARETO_POPULATION_SCOPE,
) -> list[Prototype]:
    """Apply one explicitly named strain-size policy to a complete population."""

    result = strain_size_pareto(
        protos,
        atom_count="natoms",
        d_cell=_prototype_d_cell,
        ids="uid_full",
        policy=policy,
        population_scope=population_scope,
    )
    rank_by_index = {index: rank for rank, index in enumerate(result.front_idx)}
    out: list[Prototype] = []
    for index, prototype in enumerate(protos):
        payload = dict(prototype.payload or {})
        metadata = strain_size_pareto_metadata(
            policy=result.policy,
            version=result.version,
            population_scope=result.population_scope,
            is_member=bool(result.mask[index]),
            rank=rank_by_index.get(index),
            population_size=result.population_size,
            d_cell_key=result.d_cell_keys[index],
        )
        payload["pareto"] = metadata
        out.append(
            replace(
                prototype,
                is_pareto=bool(result.mask[index]),
                pareto_rank=rank_by_index.get(index),
                payload=payload,
            )
        )
    return out


def _preserve_source_pareto_flags(
    protos: Sequence[Prototype],
) -> list[Prototype]:
    """Validate and preserve authoritative metadata supplied by the core search."""

    out: list[Prototype] = []
    for prototype in protos:
        payload = dict(prototype.payload or {})
        metadata = payload.get("pareto")
        if not is_authoritative_pareto_metadata(metadata):
            raise ValueError(
                "Persisted interface prototypes require authoritative "
                "strain_size_pareto metadata from the core search."
            )
        out.append(
            replace(
                prototype,
                is_pareto=bool(metadata.get("is_member")),
                pareto_rank=metadata.get("rank"),
                payload=payload,
            )
        )
    return out


def _canonical_slab_uid(uow: Any, identifier: str) -> str:
    value = str(identifier).strip()
    if not value:
        raise ValueError("InterfacePrototype requires a persisted slab identity.")
    if value.startswith("slab:"):
        return value
    return uow.ids.resolve_slab(value)


class PrototypesService:
    """Own prototype identity, rows, and mandatory search/slab lineage."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="PrototypesService",
        )

    def persist_interface_prototypes(
        self,
        prototypes: Sequence[Any],
        *,
        run_uid_full: str | None = None,
    ) -> dict[str, dict[str, str]]:
        """Persist current coupled-v2 ``InterfacePrototype`` records exactly."""

        from calm.interface.model import InterfacePrototype
        from .interface_prototype_payload import (
            infer_interface_area_A2,
            serialize_interface_prototype,
        )

        incoming = list(prototypes)
        if not incoming:
            return {}
        for prototype in incoming:
            if not isinstance(prototype, InterfacePrototype):
                raise TypeError(
                    "persist_interface_prototypes requires InterfacePrototype records."
                )

        prepared: list[Prototype] = []
        mapping_keys: list[str] = []

        with fresh_uow(self._uow_factory, owner="PrototypesService") as uow:
            if run_uid_full is None:
                run_spec = {"mode": "direct_persistence"}
                run_uid = persisted_entity_uid_v2(
                    "run",
                    run_identity_payload(
                        run_type="prototype_ingest",
                        spec=run_spec,
                    ),
                )
                stored_run = uow.runs.get_by_uid_full(run_uid)
                if stored_run is None:
                    stored_run = uow.runs.upsert(
                        Run(
                            uid_full=run_uid,
                            id_short=uow.ids.ensure_run_id(run_uid),
                            run_type="prototype_ingest",
                            status="running",
                            spec=run_spec,
                            error={},
                            progress={"stage": "prototype_persistence"},
                        )
                    )
                owns_ingest_run = True
            else:
                run_uid = uow.ids.resolve_run(run_uid_full)
                stored_run = uow.runs.get_by_uid_full(run_uid)
                if stored_run is None:
                    raise KeyError(f"Prototype run not found: {run_uid_full!r}")
                if stored_run.run_type not in {
                    "prototype_search",
                    "prototype_ingest",
                }:
                    raise ValueError(
                        "Prototype persistence requires a prototype_search or "
                        "prototype_ingest run."
                    )
                owns_ingest_run = False
            run = stored_run

            for internal in incoming:
                slab_a_identifier = (
                    getattr(internal.slab_a, "project_slab_uid_full", None)
                    or internal.slab_a_uid
                )
                slab_b_identifier = (
                    getattr(internal.slab_b, "project_slab_uid_full", None)
                    or internal.slab_b_uid
                )
                slab_a_uid = _canonical_slab_uid(uow, slab_a_identifier)
                slab_b_uid = _canonical_slab_uid(uow, slab_b_identifier)
                payload = serialize_interface_prototype(internal)
                if str(payload.get("slab_a_uid")) != slab_a_uid:
                    raise ValueError(
                        "Serialized prototype side-A slab identity is inconsistent."
                    )
                if str(payload.get("slab_b_uid")) != slab_b_uid:
                    raise ValueError(
                        "Serialized prototype side-B slab identity is inconsistent."
                    )

                interface_area = infer_interface_area_A2(internal)
                if interface_area is None:
                    raise ValueError(
                        "InterfacePrototype requires a positive interface area."
                    )
                match_score = float(internal.match_score)
                atom_count = int(internal.n_atoms_interface)
                uid_full = persisted_entity_uid_v2(
                    "prototype",
                    prototype_identity_payload(
                        run_uid_full=run.uid_full,
                        slab_a_uid_full=slab_a_uid,
                        slab_b_uid_full=slab_b_uid,
                        payload=payload,
                        match_score=match_score,
                        hencky_norm=0.5 * float(internal.d_cell),
                        interface_area=interface_area,
                        n_atoms=atom_count,
                    ),
                )
                prepared.append(
                    Prototype(
                        uid_full=uid_full,
                        id_short=uow.ids.ensure_prototype_id(uid_full),
                        run_uid_full=run.uid_full,
                        run_id_short=run.id_short,
                        slab_a_uid_full=slab_a_uid,
                        slab_b_uid_full=slab_b_uid,
                        match_score=match_score,
                        hencky_norm=0.5 * float(internal.d_cell),
                        interface_area=float(interface_area),
                        natoms=atom_count,
                        is_pareto=bool(internal.is_pareto),
                        pareto_rank=internal.pareto_rank,
                        payload=payload,
                    )
                )
                mapping_keys.append(str(internal.prototype_uid))

            if all(
                is_authoritative_pareto_metadata(
                    (prototype.payload or {}).get("pareto")
                )
                for prototype in prepared
            ):
                prepared = _preserve_source_pareto_flags(prepared)
            else:
                prepared = _compute_pareto_flags(
                    prepared,
                    policy="persisted_input_strain_size_pareto",
                    population_scope="persisted_input_population",
                )

            stored = uow.prototypes.upsert_many(prepared)
            if len(stored) != len(prepared):
                raise RuntimeError(
                    "Prototype repository returned an incomplete persisted population."
                )
            stored_by_uid = {prototype.uid_full: prototype for prototype in stored}
            if len(stored_by_uid) != len(stored):
                raise RuntimeError(
                    "Prototype repository returned duplicate authoritative identities."
                )

            mapping: dict[str, dict[str, str]] = {}
            for mapping_key, expected in zip(mapping_keys, prepared, strict=True):
                persisted = stored_by_uid.get(expected.uid_full)
                if persisted is None:
                    raise RuntimeError(
                        "Prototype repository omitted an expected authoritative row."
                    )
                if (
                    persisted.run_uid_full != run.uid_full
                    or persisted.slab_a_uid_full != expected.slab_a_uid_full
                    or persisted.slab_b_uid_full != expected.slab_b_uid_full
                ):
                    raise RuntimeError(
                        "Prototype repository returned inconsistent parent identity."
                    )
                uow.edges.add(
                    src_uid_full=run.uid_full,
                    dst_uid_full=persisted.uid_full,
                    kind="run_to_prototype",
                    payload=None,
                )
                uow.edges.add(
                    src_uid_full=expected.slab_a_uid_full,
                    dst_uid_full=persisted.uid_full,
                    kind="slab_to_prototype",
                    payload={"role": "a"},
                )
                uow.edges.add(
                    src_uid_full=expected.slab_b_uid_full,
                    dst_uid_full=persisted.uid_full,
                    kind="slab_to_prototype",
                    payload={"role": "b"},
                )
                mapping[mapping_key] = {
                    "uid_full": persisted.uid_full,
                    "id_short": persisted.id_short,
                    "run_uid": run.uid_full,
                    "run_id": run.id_short,
                }

            if owns_ingest_run:
                progress = {
                    "mode": "direct_persistence",
                    "n_prototypes": len(stored),
                }
                updated_run = replace(
                    stored_run,
                    status="done",
                    error={},
                    progress=progress,
                )
                persisted_run = uow.runs.upsert(updated_run)
                if persisted_run.status != "done":
                    raise RuntimeError(
                        "Prototype ingest run did not persist its terminal state."
                    )
            return mapping

    def list_prototypes(
        self,
        *,
        run: str | None = None,
        pareto_only: bool | None = None,
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[PrototypeSummary]:
        with fresh_uow(self._uow_factory, owner="PrototypesService") as uow:
            run_uid_full = uow.ids.resolve_run(run) if run is not None else None
            return uow.prototypes.query(
                run_uid_full=run_uid_full,
                pareto_only=pareto_only,
                max_hencky_norm=max_hencky_norm,
                min_match_score=min_match_score,
                order_by=order_by,
                limit=limit,
            )


class PrototypeSearchService:
    """Run and persist the authoritative primitive coupled-pair search."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="PrototypeSearchService",
        )
        self._prototypes = PrototypesService(uow_factory=uow_factory)

    def _runs(self) -> RunsService:
        return RunsService(fresh_uow(self._uow_factory, owner="PrototypeSearchService"))

    def start_search(
        self,
        *,
        slab_a: str,
        slab_b: str,
        params: Mapping[str, Any] | None = None,
        n_candidates: int = 12,
        k_max: int = 10,
        w_match: float = 0.5,
        eps_principal_max: float = 0.15,
        N_at_max: int = 1000,
        surface_symmetry_mode: str = "discover",
        surface_symprec: float = 1e-5,
        surface_angle_tolerance: float = 1e-8,
        surface_metric_tolerance: float = 1e-5,
        pair_symmetry_policy: PairSymmetryPolicy = DEFAULT_PAIR_SYMMETRY_POLICY,
        correspondence_orientation: CorrespondenceOrientation = (
            DEFAULT_CORRESPONDENCE_ORIENTATION
        ),
        identify_material_exchange: bool = DEFAULT_IDENTIFY_MATERIAL_EXCHANGE,
        correspondence_entry_limit: int | None = None,
    ) -> Run:
        if n_candidates <= 0:
            raise ValueError("n_candidates must be > 0")
        if (
            not isinstance(surface_symmetry_mode, str)
            or surface_symmetry_mode not in SURFACE_SYMMETRY_MODES
        ):
            allowed = ", ".join(sorted(SURFACE_SYMMETRY_MODES))
            raise ValueError(f"surface_symmetry_mode must be one of: {allowed}.")
        surface_symprec = positive_finite_float("surface_symprec", surface_symprec)
        surface_angle_tolerance = nonnegative_finite_float(
            "surface_angle_tolerance", surface_angle_tolerance
        )
        surface_metric_tolerance = positive_finite_float(
            "surface_metric_tolerance", surface_metric_tolerance
        )
        search_config = PrototypeSearchConfig(
            k_max=int(k_max),
            w_match=float(w_match),
            eps_principal_max=float(eps_principal_max),
            N_at_max=int(N_at_max),
            max_results=int(n_candidates),
            surface_symmetry_mode=surface_symmetry_mode,
            surface_symprec=surface_symprec,
            surface_angle_tolerance=surface_angle_tolerance,
            surface_metric_tolerance=surface_metric_tolerance,
            pair_symmetry_policy=pair_symmetry_policy,
            correspondence_orientation=correspondence_orientation,
            identify_material_exchange=identify_material_exchange,
            correspondence_entry_limit=correspondence_entry_limit,
        )

        with fresh_uow(self._uow_factory, owner="PrototypeSearchService") as uow:
            slab_a_uid_full = uow.ids.resolve_slab(slab_a)
            slab_b_uid_full = uow.ids.resolve_slab(slab_b)
            slab_a_obj = uow.slabs.get_by_uid_full(slab_a_uid_full)
            slab_b_obj = uow.slabs.get_by_uid_full(slab_b_uid_full)
        if slab_a_obj is None or slab_b_obj is None:
            raise KeyError("Prototype search requires two persisted slabs.")

        from ...interface.matching.search import COUPLED_MATCH_IMPLEMENTATION

        spec: dict[str, Any] = {
            "slab_a_uid_full": slab_a_uid_full,
            "slab_b_uid_full": slab_b_uid_full,
            "n_candidates": int(n_candidates),
            "k_max": int(k_max),
            "w_match": float(w_match),
            "eps_principal_max": float(eps_principal_max),
            "N_at_max": int(N_at_max),
            "surface_symmetry_mode": surface_symmetry_mode,
            "surface_symprec": surface_symprec,
            "surface_angle_tolerance": surface_angle_tolerance,
            "surface_metric_tolerance": surface_metric_tolerance,
            "pair_symmetry_policy": search_config.pair_symmetry_policy,
            "correspondence_orientation": search_config.correspondence_orientation,
            "identify_material_exchange": (search_config.identify_material_exchange),
            "correspondence_entry_limit": (search_config.correspondence_entry_limit),
            "params": dict(params or {}),
            "impl": COUPLED_MATCH_IMPLEMENTATION,
        }
        runs = self._runs()
        run = runs.create(run_type="prototype_search", spec=spec)
        if run.status == "done":
            return run
        runs.mark_running(
            run.uid_full,
            progress={"stage": "prototype_search", "phase": "matching"},
        )

        try:
            from calm.keys.uid import prototype_uid_v3
            from ...interface.pipeline import find_prototypes

            result = find_prototypes(slab_a_obj, slab_b_obj, search_config)
            project_prototypes = []
            for prototype in result.prototypes:
                pair_identity = prototype.pair_identity
                project_uid = prototype_uid_v3(
                    slab_uid_a=slab_a_uid_full,
                    slab_uid_b=slab_b_uid_full,
                    primitive_pair_key=pair_identity.primitive_pair_key,
                    pair_key_version=pair_identity.key_version,
                    pair_symmetry_policy=pair_identity.pair_symmetry_policy,
                    correspondence_orientation=(
                        pair_identity.correspondence_orientation
                    ),
                    material_exchange_identified=(
                        pair_identity.material_exchange_identified
                    ),
                )
                project_prototypes.append(
                    replace(
                        prototype,
                        prototype_uid=project_uid,
                        slab_a_uid=slab_a_uid_full,
                        slab_b_uid=slab_b_uid_full,
                    )
                )

            persisted = self._prototypes.persist_interface_prototypes(
                project_prototypes,
                run_uid_full=run.uid_full,
            )
            if len(persisted) != len(project_prototypes):
                raise RuntimeError(
                    "Prototype persistence did not return the complete population."
                )
            symmetry_provenance = {
                "surface_a": result.surface_symmetry_a.to_dict(),
                "surface_b": result.surface_symmetry_b.to_dict(),
            }
            return runs.mark_done(
                run.uid_full,
                progress={
                    "implementation": COUPLED_MATCH_IMPLEMENTATION,
                    "surface_symmetry": symmetry_provenance,
                    "primitive_pair_keys": [
                        list(prototype.pair_identity.primitive_pair_key)
                        for prototype in project_prototypes
                    ],
                    "pareto_population_size": result.pareto_population_size,
                    "retained_count": len(project_prototypes),
                },
            )
        except Exception as exc:
            runs.mark_failed(
                run.uid_full,
                error={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
            raise
