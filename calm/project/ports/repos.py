"""Repository interface definitions for project persistence.

These protocols define the minimal repository surface expected by the
application services. Concrete SQLAlchemy-backed implementations live under
calm.project.infrastructure.db.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from ..domain.models import (
    ArtifactRef,
    Bulk,
    BulkReferenceRecord,
    BulkSummary,
    Calculator,
    CalculatorSummary,
    Campaign,
    CampaignRun,
    Dataset,
    DatasetItem,
    DerivedInterface,
    Edge,
    FollowupResult,
    InterfaceSearch,
    Prototype,
    PrototypeSummary,
    Run,
    Slab,
    SlabReferenceRecord,
    SlabSummary,
)


class BulkRepository(Protocol):
    def upsert(self, bulk: Bulk) -> Bulk: ...
    def get_by_uid_full(self, uid_full: str) -> Bulk | None: ...
    def list(self, *, limit: int | None = None) -> list[BulkSummary]: ...
    def list_reference_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[BulkReferenceRecord]: ...


class CalculatorRepository(Protocol):
    def upsert(self, calc: Calculator) -> Calculator: ...
    def get_by_uid_full(self, uid_full: str) -> Calculator | None: ...
    def list(self, *, limit: int | None = None) -> list[CalculatorSummary]: ...


class ProjectConfigurationRepository(Protocol):
    def get(self) -> dict | None: ...
    def upsert(
        self,
        *,
        default_mlip: str | None = None,
        default_calculator_uid_full: str | None = None,
        workflow_defaults: dict | None = None,
    ) -> dict: ...


class SlabRepository(Protocol):
    def create_many(self, slabs: Sequence[Slab]) -> list[Slab]: ...
    def get_by_uid_full(self, uid_full: str) -> Slab | None: ...
    def get_many_by_uid_full(self, uid_fulls: Sequence[str]) -> list[Slab]: ...
    def list(
        self,
        *,
        bulk_uid_full: str | None = None,
        limit: int | None = None,
    ) -> list[SlabSummary]: ...
    def list_reference_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[SlabReferenceRecord]: ...


class PrototypeRepository(Protocol):
    def upsert_many(self, prototypes: Sequence[Prototype]) -> list[Prototype]: ...
    def get_by_uid_full(self, uid_full: str) -> Prototype | None: ...
    def get_many_by_uid_full(self, uid_fulls: Sequence[str]) -> list[Prototype]: ...

    def query(
        self,
        *,
        run_uid_full: str | None = None,
        pareto_only: bool | None = None,
        max_hencky_norm: float | None = None,
        min_match_score: float | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[PrototypeSummary]: ...


class DerivedInterfaceRepository(Protocol):
    def upsert(self, iface: DerivedInterface) -> DerivedInterface: ...
    def get_by_uid_full(self, uid_full: str) -> DerivedInterface | None: ...
    def list(
        self,
        *,
        prototype_uid_full: str | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[DerivedInterface]: ...


class RunRepository(Protocol):
    def upsert(self, run: Run) -> Run: ...
    def get_by_uid_full(self, uid_full: str) -> Run | None: ...
    def list(
        self,
        *,
        limit: int | None = None,
        run_type: str | None = None,
        status: str | None = None,
    ) -> list[Run]: ...


class InterfaceSearchRepository(Protocol):
    def create(
        self,
        *,
        name: str,
        search_identity: str,
        run_uid_full: str,
    ) -> InterfaceSearch: ...
    def get_by_name(self, name: str) -> InterfaceSearch | None: ...
    def get_by_search_identity(
        self,
        search_identity: str,
    ) -> InterfaceSearch | None: ...
    def get_by_run_uid_full(
        self,
        run_uid_full: str,
    ) -> InterfaceSearch | None: ...
    def get_by_run_id_short(
        self,
        run_id_short: str,
    ) -> InterfaceSearch | None: ...
    def list(self, *, limit: int | None = None) -> list[InterfaceSearch]: ...


class ArtifactRepository(Protocol):
    def add(self, artifact: ArtifactRef) -> ArtifactRef: ...
    def get_by_uid_full(self, uid_full: str) -> ArtifactRef | None: ...
    def list_for_run(self, run_uid_full: str) -> list[ArtifactRef]: ...


class EdgeRepository(Protocol):
    """Persistence port for provenance edges."""

    def add(
        self,
        *,
        src_uid_full: str,
        dst_uid_full: str,
        kind: str,
        payload: dict | None = None,
    ) -> None: ...

    def list(
        self,
        *,
        src_uid_full: str | None = None,
        dst_uid_full: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[Edge]: ...


class DatasetRepository(Protocol):
    def create_dataset(
        self,
        *,
        uid_full: str,
        name: str | None = None,
        project_id: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> Dataset: ...
    def get_dataset(self, uid_full: str) -> Dataset | None: ...
    def list_datasets(self, *, limit: int | None = None) -> list[Dataset]: ...
    def add_dataset_item(
        self,
        *,
        uid_full: str,
        dataset_uid_full: str,
        index: int | None = None,
        metadata: dict | None = None,
        artifact_refs: list | None = None,
    ) -> DatasetItem: ...
    def list_dataset_items(self, dataset_uid_full: str) -> list[DatasetItem]: ...


class FollowupResultRepository(Protocol):
    """Persistence port for follow-up analysis result summaries."""

    def upsert_many(
        self, results: Sequence[FollowupResult]
    ) -> list[FollowupResult]: ...

    def get_by_uid_full(self, uid_full: str) -> FollowupResult | None: ...

    def list(
        self,
        *,
        run_uid_full: str | None = None,
        prototype_uid_full: str | None = None,
        target_uid_full: str | None = None,
        target_kind: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[FollowupResult]: ...


# (archived) queued-job repo: queued job persistence is intentionally omitted
# from the active public API. Historical implementation moved to archive.


class CampaignRepository(Protocol):
    def create_campaign(
        self,
        *,
        uid_full: str,
        name: str | None = None,
        project_id: str | None = None,
        spec: dict | None = None,
    ) -> Campaign: ...

    def get_campaign(self, uid_full: str) -> Campaign | None: ...
    def list_campaigns(self, *, limit: int | None = None) -> list[Campaign]: ...

    def create_or_get_campaign_run(
        self,
        *,
        campaign_uid_full: str,
        run_spec: dict,
        backend_id: str | None = None,
        status: str | None = None,
    ) -> CampaignRun: ...

    def get_campaign_run(self, uid_full: str) -> CampaignRun | None: ...
    def list_campaign_runs(
        self,
        *,
        campaign_uid_full: str | None = None,
        limit: int | None = None,
    ) -> list[CampaignRun]: ...
    def mark_campaign_run(
        self,
        uid_full: str,
        *,
        status: str,
    ) -> CampaignRun | None: ...
