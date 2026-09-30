"""Exact public translation boundary over the current project workspace.

The adapter exposes only current :class:`Workspace` operations. It never probes
historical facades, reaches into private services, or converts backend failures
into empty collections.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from calm.public.projections.buildability import prototype_identifier_from_candidate_row


class WorkspaceAdapter:
    """Translate public Project calls to one current internal Workspace."""

    def __init__(self, workspace: Any) -> None:
        self._ws = workspace

    def get_calculator(self, identifier: str) -> Any:
        return self._ws.get_calculator(identifier)

    # ---------------- Materials and slabs ----------------
    def add_bulk(self, *args: Any, **kwargs: Any) -> Any:
        return self._ws.add_bulk(*args, **kwargs)

    def get_bulk(self, identifier: str) -> Any:
        return self._ws.get_bulk(identifier)

    def list_bulks(self, *, limit: int | None = None) -> list[Any]:
        return list(self._ws.list_bulks(limit=limit))

    def build_slabs(self, *args: Any, **kwargs: Any) -> Any:
        return self._ws.build_slabs(*args, **kwargs)

    def get_slab(self, identifier: str) -> Any:
        return self._ws.get_slab(identifier)

    def list_slabs(self, *, limit: int | None = None) -> list[Any]:
        return list(self._ws.list_slabs(limit=limit))

    # ---------------- Prototypes and interfaces ----------------
    def persist_interface_prototypes(
        self,
        prototypes: Iterable[Any],
        *,
        run_uid_full: str | None = None,
    ) -> dict[str, Any]:
        return self._ws.persist_interface_prototypes(
            prototypes,
            run_uid_full=run_uid_full,
        )

    def list_prototypes(
        self,
        *,
        run: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return list(self._ws.list_prototypes(run=run, limit=limit))

    def get_prototype(self, identifier: str) -> Any:
        return self._ws.get_prototype(identifier)

    def check_prototype_buildability(self, prototype: str) -> Any:
        return self._ws.check_prototype_buildability(prototype)

    def check_prototypes_buildability(
        self,
        prototypes: list[str],
    ) -> dict[str, Any]:
        return self._ws.check_prototypes_buildability(prototypes)

    def build_interface_from_prototype(self, prototype: str, **kwargs: Any) -> Any:
        return self._ws.build_interface_from_prototype(prototype, **kwargs)

    def list_derived_interfaces(self, *, limit: int | None = None) -> list[Any]:
        return list(self._ws.list_derived_interfaces(limit=limit))

    def get_derived_interface(self, identifier: str) -> Any:
        return self._ws.get_derived_interface(identifier)

    def get_derived_interface_atoms(self, identifier: str) -> Any:
        return self._ws.get_derived_interface_atoms(identifier)

    def materialize_derived_interface_atoms(
        self,
        identifier: str,
        *,
        registry_shift_frac_a: tuple[float, float] | None = None,
    ) -> Any:
        return self._ws.materialize_derived_interface_atoms(
            identifier,
            registry_shift_frac_a=registry_shift_frac_a,
        )

    def start_strain_partition_scan(self, **kwargs: Any) -> Any:
        return self._ws.start_strain_partition_scan(**kwargs)

    def derive_interfaces_from_strain_partition_scan(
        self,
        run: str,
        **kwargs: Any,
    ) -> list[Any]:
        return list(
            self._ws.derive_interfaces_from_strain_partition_scan(
                run,
                **kwargs,
            )
        )

    def start_registry_search(self, **kwargs: Any) -> Any:
        return self._ws.start_registry_search(**kwargs)

    def derive_interfaces_from_registry_search(
        self,
        run: str,
        **kwargs: Any,
    ) -> list[Any]:
        return list(
            self._ws.derive_interfaces_from_registry_search(
                run,
                **kwargs,
            )
        )

    def run_build_stage(
        self,
        prototypes: list[str],
        **kwargs: Any,
    ) -> list[dict]:
        return list(self._ws.run_build_stage(prototypes, **kwargs))

    def run_registry_stage(
        self,
        prototypes: list[str],
        **kwargs: Any,
    ) -> list[dict]:
        return list(self._ws.run_registry_stage(prototypes, **kwargs))

    def persist_derived_interface(
        self,
        interface: Any,
        *,
        name: str | None = None,
    ) -> Any:
        """Persist one built interface through the current Workspace contract."""
        candidate = interface.candidate
        if not isinstance(candidate, Mapping):
            raise TypeError(
                "Interface persistence requires canonical candidate metadata."
            )
        prototype = prototype_identifier_from_candidate_row(dict(candidate))
        if prototype is None:
            raise ValueError(
                "Cannot persist an interface without an authoritative prototype "
                "identifier."
            )

        settings = interface.build_settings
        internal = interface._internal
        return self._ws.create_derived_interface(
            prototype,
            label=name,
            strain_alpha=settings.alpha,
            registry_shift_frac_a=settings.translation,
            z_padding=settings.gap,
            vacuum=settings.vacuum,
            params=None,
            atoms=interface.atoms,
            strain_state=getattr(internal, "strain_state", None),
        )

    # ---------------- Runs and follow-ups ----------------
    def prepare_interface_search(
        self,
        *,
        name: str,
        search_identity: str,
        run_spec: Mapping[str, Any],
        resume: bool,
    ) -> Any:
        return self._ws.prepare_interface_search(
            name=name,
            search_identity=search_identity,
            run_spec=run_spec,
            resume=resume,
        )

    def complete_interface_search(
        self,
        run_uid_full: str,
        *,
        n_candidates: int,
        enumeration_audit: Mapping[str, Any] | None = None,
    ) -> Any:
        return self._ws.complete_interface_search(
            run_uid_full,
            n_candidates=n_candidates,
            enumeration_audit=enumeration_audit,
        )

    def fail_interface_search(
        self,
        run_uid_full: str,
        *,
        error: Mapping[str, Any],
    ) -> Any:
        return self._ws.fail_interface_search(run_uid_full, error=error)

    def list_interface_searches(
        self,
        *,
        limit: int | None = None,
    ) -> list[Any]:
        return list(self._ws.list_interface_searches(limit=limit))

    def get_interface_search(self, identifier: str) -> Any:
        return self._ws.get_interface_search(identifier)

    def create_run(self, *, run_type: str, spec: dict[str, Any]) -> Any:
        return self._ws.create_run(run_type=run_type, spec=spec)

    def mark_run_running(
        self,
        run: str,
        *,
        progress: dict[str, Any] | None = None,
    ) -> Any:
        return self._ws.mark_run_running(run, progress=progress)

    def mark_run_done(
        self,
        run: str,
        *,
        progress: dict[str, Any] | None = None,
    ) -> Any:
        return self._ws.mark_run_done(run, progress=progress)

    def mark_run_failed(self, run: str, *, error: dict[str, Any]) -> Any:
        return self._ws.mark_run_failed(run, error=error)

    def list_runs(
        self,
        *,
        run_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return list(
            self._ws.list_runs(
                run_type=run_type,
                status=status,
                limit=limit,
            )
        )

    def get_run(self, run: str) -> Any:
        return self._ws.get_run(run)

    def list_followup_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        items = list(
            self._ws.list_followup_results(
                run=run,
                prototype=prototype,
                kind=kind,
                limit=limit,
            )
        )
        if status is None:
            return items
        return [item for item in items if item.status == status]

    def get_followup_result(self, identifier: str) -> Any:
        return self._ws.get_followup_result(identifier)

    def list_artifacts(self, run: str) -> list[Any]:
        return list(self._ws.list_artifacts(run))

    def list_edges(
        self,
        *,
        src: str | None = None,
        dst: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return list(
            self._ws.list_edges(
                src=src,
                dst=dst,
                kind=kind,
                limit=limit,
            )
        )

    def resolve_identifier(self, identifier: str) -> str:
        return self._ws.resolve_identifier(identifier)

    # ---------------- Datasets and campaigns ----------------
    def create_or_get_dataset(
        self,
        *,
        name: str,
        settings: dict[str, Any],
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        return self._ws.create_or_get_dataset(
            name=name,
            settings=settings,
            description=description,
            tags=tags,
        )

    def add_dataset_items(
        self,
        dataset: str,
        items: list[dict[str, Any]],
        *,
        duplicate_policy: str,
    ) -> list[Any]:
        return list(
            self._ws.add_dataset_items(
                dataset,
                items,
                duplicate_policy=duplicate_policy,
            )
        )

    def list_datasets(self, *, limit: int | None = None) -> list[Any]:
        return list(self._ws.list_datasets(limit=limit))

    def get_dataset(self, identifier: str) -> Any:
        return self._ws.get_dataset(identifier)

    def list_dataset_items(self, dataset: str) -> list[Any]:
        return list(self._ws.list_dataset_items(dataset))

    def create_campaign(
        self,
        *,
        name: str | None = None,
        spec: dict[str, Any] | None = None,
        uid_full: str | None = None,
    ) -> dict[str, Any]:
        return self._ws.create_campaign(name=name, spec=spec, uid_full=uid_full)

    def create_or_get_campaign_run(
        self,
        campaign_uid_full: str,
        *,
        run_spec: dict[str, Any],
        backend_id: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        return self._ws.create_or_get_campaign_run(
            campaign_uid_full,
            run_spec=run_spec,
            backend_id=backend_id,
            status=status,
        )

    def mark_campaign_run(
        self,
        campaign_run_uid_full: str,
        *,
        status: str,
    ) -> Any:
        return self._ws.mark_campaign_run(
            campaign_run_uid_full,
            status=status,
        )

    def add_provenance_edge(
        self,
        *,
        src_uid_full: str,
        dst_uid_full: str,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return self._ws.add_provenance_edge(
            src_uid_full=src_uid_full,
            dst_uid_full=dst_uid_full,
            kind=kind,
            payload=payload,
        )

    def list_campaigns(self, *, limit: int | None = None) -> list[Any]:
        return list(self._ws.list_campaigns(limit=limit))

    def get_campaign(self, identifier: str) -> Any:
        return self._ws.get_campaign(identifier)

    def get_campaign_run(self, identifier: str) -> Any:
        return self._ws.get_campaign_run(identifier)

    def list_campaign_runs(
        self,
        *,
        campaign: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return list(self._ws.list_campaign_runs(campaign=campaign, limit=limit))

    def get_campaign_run_for_dataset(self, dataset: str) -> Any:
        return self._ws.get_campaign_run_for_dataset(dataset)

    def get_campaign_for_dataset(self, dataset: str) -> Any:
        return self._ws.get_campaign_for_dataset(dataset)
