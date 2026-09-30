"""Public exceptions for the CALM facade."""

from __future__ import annotations

from calm.project.domain.contracts.campaign import (
    CampaignIdentityConflictError as CampaignIdentityConflictError,
)
from calm.project.domain.contracts.dataset import (
    DatasetIdentityConflictError as DatasetIdentityConflictError,
)
from calm.interface.energy.contract import (
    UnsupportedReferenceWorkflowError as UnsupportedReferenceWorkflowError,
)


class CalmPublicAPIError(Exception):
    """Base class for public-facade errors."""


class CalmDependencyError(ImportError, CalmPublicAPIError):
    """Raised when an optional dependency is required for a requested operation."""


class CalmNoCandidatesError(CalmPublicAPIError):
    """Raised when a workflow explicitly requires at least one candidate."""


class AmbiguousProjectQueryError(CalmPublicAPIError):
    """Raised when a project query has multiple matches and needs disambiguation."""


class SearchIdentityConflictError(CalmPublicAPIError, ValueError):
    """Raised when a persisted search name is reused for different science inputs."""


class SearchEnumerationAuditUnavailableError(CalmPublicAPIError, LookupError):
    """Raised when an older persisted search has no enumeration accounting."""


class ProjectPersistenceError(CalmPublicAPIError):
    """Raised when a directory-backed project cannot be opened safely."""


class ProjectReproducibilityError(CalmPublicAPIError):
    """Raised when a project reproducibility manifest cannot be created or verified."""
