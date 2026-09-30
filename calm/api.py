"""Declarative owner of CALM's single supported public API.

All supported user imports originate from :mod:`calm`.  Implementation
packages such as :mod:`calm.project`, :mod:`calm.interface`, and
:mod:`calm.slab` are internal and may change without compatibility guarantees.
The public workflow is project-centered: open a :class:`Project`, provide typed
workflow settings, and operate on project records returned by that project.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - static-analysis imports only
    pass

_OPTIONAL_DEP_INSTALL_HINTS: dict[str, str] = {
    "ase": 'python -m pip install "calm[science]"',
    "scipy": 'python -m pip install "calm[science]"',
    "spglib": 'python -m pip install "calm[science]"',
    "matplotlib": 'python -m pip install "calm[plot]"',
    "sqlalchemy": 'python -m pip install "SQLAlchemy>=2,<3"',
}

# Name -> (module path, attribute name). This is the sole runtime registry for
# supported ``calm.<name>`` attributes.  The order below is the teaching order
# used by ``from calm import *`` and the generated reference.
_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "__version__": ("calm._version", "__version__"),
    # Project entry point.
    "Project": ("calm.public.project", "Project"),
    "open_project": ("calm.public.project", "open_project"),
    # User-authored workflow inputs.
    "Material": ("calm.public.inputs.materials", "Material"),
    "Potential": ("calm.public.inputs.potentials", "Potential"),
    "SearchSettings": ("calm.public.inputs.settings", "SearchSettings"),
    "StrainPartitionSettings": (
        "calm.public.inputs.settings",
        "StrainPartitionSettings",
    ),
    "BuildSettings": ("calm.public.inputs.settings", "BuildSettings"),
    "RegistrySettings": ("calm.public.inputs.settings", "RegistrySettings"),
    "RelaxSettings": ("calm.public.inputs.settings", "RelaxSettings"),
    "EnergySettings": ("calm.public.inputs.settings", "EnergySettings"),
    "EnergyConvention": ("calm.public.inputs.settings", "EnergyConvention"),
    "ReferenceEnergySettings": (
        "calm.public.inputs.settings",
        "ReferenceEnergySettings",
    ),
    "DatasetFeature": ("calm.public.inputs.settings", "DatasetFeature"),
    "DatasetTarget": ("calm.public.inputs.settings", "DatasetTarget"),
    "DatasetSplitSettings": (
        "calm.public.inputs.settings",
        "DatasetSplitSettings",
    ),
    "DatasetSettings": ("calm.public.inputs.settings", "DatasetSettings"),
    "CampaignCase": ("calm.public.inputs.campaigns", "CampaignCase"),
    "CampaignSettings": ("calm.public.inputs.campaigns", "CampaignSettings"),
    # Catchable public workflow failures.
    "CalmPublicAPIError": ("calm.public.errors", "CalmPublicAPIError"),
    "CalmDependencyError": ("calm.public.errors", "CalmDependencyError"),
    "CalmNoCandidatesError": (
        "calm.public.errors",
        "CalmNoCandidatesError",
    ),
    "AmbiguousProjectQueryError": (
        "calm.public.errors",
        "AmbiguousProjectQueryError",
    ),
    "SearchIdentityConflictError": (
        "calm.public.errors",
        "SearchIdentityConflictError",
    ),
    "DatasetIdentityConflictError": (
        "calm.public.errors",
        "DatasetIdentityConflictError",
    ),
    "CampaignIdentityConflictError": (
        "calm.public.errors",
        "CampaignIdentityConflictError",
    ),
    "ProjectPersistenceError": (
        "calm.public.errors",
        "ProjectPersistenceError",
    ),
    "ProjectReproducibilityError": (
        "calm.public.errors",
        "ProjectReproducibilityError",
    ),
    "DatasetValidationError": (
        "calm.public.records.datasets",
        "DatasetValidationError",
    ),
    "UnsupportedReferenceWorkflowError": (
        "calm.public.errors",
        "UnsupportedReferenceWorkflowError",
    ),
    # Packaged tutorial data.
    "tutorial_structure": ("calm.structure.tutorials", "tutorial_structure"),
    # File utilities used by the public workflow.
    "load_structure": ("calm.structure.io", "load_structure"),
    "write_structure": ("calm.structure.io", "write_structure"),
    "write_json": ("calm.structure.io", "write_json"),
}

PUBLIC_EXPORTS = tuple(_EXPORT_MAP)
__all__ = [name for name in PUBLIC_EXPORTS if name != "__version__"]


def _validate_contract() -> None:
    """Validate the import-light public registry."""

    if len(PUBLIC_EXPORTS) != len(set(PUBLIC_EXPORTS)):
        raise ValueError("calm.api public export registry contains duplicates")
    if set(__all__) != set(PUBLIC_EXPORTS) - {"__version__"}:
        raise ValueError("calm.api.__all__ must match the public export registry")


_validate_contract()


def _raise_optional_dependency_error(
    *,
    missing: str,
    symbol: str,
    module_path: str,
    err: BaseException,
) -> None:
    hint = _OPTIONAL_DEP_INSTALL_HINTS.get(missing, f"pip install {missing}")
    raise ImportError(
        f"Optional dependency {missing!r} is required to use calm.{symbol} "
        f"(needed to import {module_path!r}).\nInstall it with: {hint}"
    ) from err


def resolve(name: str) -> Any:
    """Resolve and cache one declared public symbol."""

    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attribute = target
    try:
        module = import_module(module_path)
    except ModuleNotFoundError as exc:
        missing_name = exc.name or ""
        missing_root = missing_name.split(".", maxsplit=1)[0]
        if missing_root in _OPTIONAL_DEP_INSTALL_HINTS:
            _raise_optional_dependency_error(
                missing=missing_root,
                symbol=name,
                module_path=module_path,
                err=exc,
            )
        raise

    value = getattr(module, attribute)
    globals()[name] = value
    return value


def __getattr__(name: str) -> Any:
    return resolve(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(PUBLIC_EXPORTS))
