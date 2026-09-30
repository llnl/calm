"""SQLAlchemy repository implementations grouped by persisted aggregate."""

from __future__ import annotations

from .artifacts import SqlAlchemyArtifactRepository
from .bulk import SqlAlchemyBulkRepository
from .calculators import SqlAlchemyCalculatorRepository
from .campaigns import SqlAlchemyCampaignRepository
from .configuration import ProjectConfigurationRepository
from .datasets import SqlAlchemyDatasetRepository
from .derived_interfaces import SqlAlchemyDerivedInterfaceRepository
from .followups import SqlAlchemyFollowupResultRepository
from .lineage import SqlAlchemyEdgeRepository
from .prototypes import SqlAlchemyPrototypeRepository
from .runs import SqlAlchemyRunRepository
from .searches import SqlAlchemyInterfaceSearchRepository
from .slabs import SqlAlchemySlabRepository

__all__ = [
    "ProjectConfigurationRepository",
    "SqlAlchemyArtifactRepository",
    "SqlAlchemyBulkRepository",
    "SqlAlchemyCalculatorRepository",
    "SqlAlchemyCampaignRepository",
    "SqlAlchemyDatasetRepository",
    "SqlAlchemyDerivedInterfaceRepository",
    "SqlAlchemyEdgeRepository",
    "SqlAlchemyFollowupResultRepository",
    "SqlAlchemyInterfaceSearchRepository",
    "SqlAlchemyPrototypeRepository",
    "SqlAlchemyRunRepository",
    "SqlAlchemySlabRepository",
]
