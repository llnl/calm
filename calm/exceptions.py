"""calm.exceptions

Central exception hierarchy for calm.

This module defines the canonical exception types for the package.

Stage A note
------------
Historically exceptions lived in ``calm.errors``. As part of the v2
refactor, exceptions are consolidated here.
"""

from __future__ import annotations


class CALMError(Exception):
    """Base class for all calm exceptions."""


class SymmetryError(CALMError):
    """Raised when symmetry detection or symmetry-reduction fails."""


class InvalidStructureError(CALMError):
    """Raised when input structures are inconsistent or invalid."""


class SlabError(CALMError):
    """Raised when slab construction fails."""

    def __init__(self, message: str):
        super().__init__(message)


class PrototypeSearchError(CALMError):
    """Raised when prototype search fails."""


class InterfaceBuilderError(CALMError):
    """Raised when interface building or matching logic fails."""

    def __init__(self, message: str):
        super().__init__(message)


class BuildError(CALMError):
    """Raised when building an atomistic interface realization fails."""


class EnergyError(CALMError):
    """Raised when interfacial energy computation fails."""


class ProjectError(CALMError):
    """Raised when project/provenance operations fail."""


class OptionalDependencyError(CALMError, ImportError):
    """Raised when an optional dependency is required but not installed."""


class CALMWarning(UserWarning):
    """Base class for calm warnings."""


class ReferenceFrameFallbackWarning(CALMWarning):
    """Emitted when calm must fall back to a less certain reference-frame mapping."""


class ReferenceFrameError(EnergyError):
    """Raised when reference-frame construction fails or is disallowed (strict mode)."""


class SurfaceSymmetryDiscoveryError(SymmetryError):
    """Raised when authoritative surface-symmetry resolution fails closed."""

    def __init__(self, message: str, *, provenance: object | None = None):
        super().__init__(message)
        self.provenance = provenance


class SurfaceCellHandednessWarning(CALMWarning):
    """Emitted when a 2D surface-cell basis is left-handed and is auto-repaired.

    A left-handed 2D basis has negative signed area (negative determinant). This can
    lead to subtle downstream issues if not handled consistently.

    calm attempts to auto-repair left-handed bases by applying a det=-1 unimodular
    transform (e.g., flipping one basis vector), while preserving the underlying
    lattice.
    """


class SurfaceCellHandednessError(SymmetryError):
    """Raised when a left-handed 2D surface-cell basis is encountered in strict mode."""


class CanonicalGaussReductionError(SymmetryError):
    """Base class for verified canonical 2D Gauss reduction failures."""


class CanonicalGaussReductionCycleError(CanonicalGaussReductionError):
    """Raised when canonical 2D Gauss reduction repeats an integer basis state."""


class CanonicalGaussReductionIterationError(CanonicalGaussReductionError):
    """Raised when canonical 2D Gauss reduction exhausts its finite iteration bound."""


class CanonicalGaussReductionInvariantError(CanonicalGaussReductionError):
    """Raised when a canonical 2D Gauss result fails executable postconditions."""


class PrimitiveSlabError(SymmetryError):
    """Raised when primitive-slab reduction fails in strict mode."""


class BoundedGaugeSearchError(SymmetryError):
    """Raised when a finite gauge search cannot certify its representative.

    The selected candidate lies on the declared search boundary, the finite
    iteration budget is exhausted, or another explicit bound prevents CALM
    from verifying the advertised bounded canonicalization contract.
    """


class FileIOError(CALMError):
    """Raised when file I/O operations fail.

    This includes failures in reading, writing, or validating structure files.
    """


def optional_dependency_error(
    *,
    missing: str | tuple[str, ...] | list[str],
    extra: str | None = None,
    symbol: str | None = None,
) -> OptionalDependencyError:
    """Create a standardized error for missing optional dependencies."""

    missing_values = [missing] if isinstance(missing, str) else list(missing)
    modules: list[str] = []
    for value in missing_values:
        module = str(value).strip()
        if module and module not in modules:
            modules.append(module)

    if (extra or "").strip().lower() == "science":
        for module in ("ase", "spglib"):
            if module not in modules:
                modules.append(module)

    missing_pretty = ", ".join(f"`{module}`" for module in modules) or "(unknown)"
    symbol_note = f" for {symbol}" if symbol else ""
    if extra:
        message = (
            f"Optional dependencies are missing{symbol_note}. "
            f"Install CALM with `pip install calm[{extra}]`, or install "
            f"{missing_pretty} directly."
        )
    else:
        targets = " ".join(modules) or "<missing-dependency>"
        message = (
            f"Optional dependencies are missing{symbol_note}. "
            f"Install {missing_pretty} (for example, `pip install {targets}`) "
            "and retry."
        )
    return OptionalDependencyError(message)
