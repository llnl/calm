"""Unit-of-work protocol used by the workspace application layer.

Defines the UnitOfWork interface expected by the project's bootstrap and
UX layers. Concrete implementations include SQLAlchemy-backed unit-of-work
and lightweight test fakes.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from .ids import IdResolver
from .repos import (
    ArtifactRepository,
    BulkRepository,
    CalculatorRepository,
    CampaignRepository,
    DatasetRepository,
    DerivedInterfaceRepository,
    EdgeRepository,
    FollowupResultRepository,
    InterfaceSearchRepository,
    ProjectConfigurationRepository,
    PrototypeRepository,
    RunRepository,
    SlabRepository,
)


class UnitOfWork(Protocol):
    """Unit of Work boundary for application services.

    Concrete implementations live in infrastructure.
    """

    bulks: BulkRepository
    calculators: CalculatorRepository
    slabs: SlabRepository
    prototypes: PrototypeRepository
    derived_interfaces: DerivedInterfaceRepository
    followups: FollowupResultRepository
    runs: RunRepository
    interface_searches: InterfaceSearchRepository
    artifacts: ArtifactRepository
    edges: EdgeRepository
    campaigns: CampaignRepository
    datasets: DatasetRepository
    project_configuration: ProjectConfigurationRepository
    ids: IdResolver

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
