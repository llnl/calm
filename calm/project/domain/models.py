"""Domain model dataclasses used by the project layer.

This module defines simple dataclasses representing persisted entities such as
Bulks, Slabs, Prototypes, Runs, and related lightweight DTOs used by the
repository and application layers. These are intentionally small, serializable
structures meant for in-process data passing and persistence hydration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Sequence

if TYPE_CHECKING:  # pragma: no cover
    # ASE is an optional/heavy dependency. We only import it for typing.
    from ase import Atoms  # type: ignore


def _dict_to_atoms(payload: Any) -> "Atoms | None":
    """Decode one exact current atoms payload, preserving explicit absence."""

    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise TypeError("Persisted atoms payload must be a mapping or None.")

    from calm.structure.payloads import dict_to_atoms  # type: ignore

    return dict_to_atoms(payload)


@dataclass(frozen=True)
class Bulk:
    uid_full: str
    id_short: str
    label: str
    kind: str = "reference"  # reference | optimized | ...

    # If this Bulk was created from an ASE relaxation, we persist the calculator
    # used to produce it.
    optimized_with_calculator_uid_full: Optional[str] = None
    calculator: Optional[str] = None

    # Arbitrary JSON payload. When structures are provided, CALM stores
    # a JSON-serializable atoms dict under payload["atoms"].
    payload: Optional[dict[str, Any]] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def _atoms_payload(self, key: str) -> dict[str, Any] | None:
        if not self.payload:
            return None
        value = self.payload.get(key)
        if value is None:
            return None
        if not isinstance(value, dict):
            raise TypeError(
                f"Persisted bulk field {key!r} must be an atoms mapping or None."
            )
        return value

    @property
    def atoms_conventional(self) -> "Atoms | None":
        """Conventional-cell structure as ASE ``Atoms`` (if available)."""

        atoms_dict = self._atoms_payload("atoms_conventional")
        return _dict_to_atoms(atoms_dict)

    @property
    def atoms_primitive(self) -> "Atoms | None":
        """Primitive-cell structure as ASE ``Atoms`` (if persisted)."""

        atoms_dict = self._atoms_payload("atoms_primitive")
        return _dict_to_atoms(atoms_dict)

    @property
    def atoms(self) -> "Atoms | None":
        """Alias for :pyattr:`atoms_conventional`."""

        return self.atoms_conventional

    def to_ase(self) -> "Atoms | None":
        """Convenience alias for ``atoms_conventional``."""

        return self.atoms_conventional

    @property
    def derived(self) -> dict[str, Any]:
        if not self.payload:
            return {}
        d = self.payload.get("derived")
        return d if isinstance(d, dict) else {}

    @property
    def formula(self) -> str:
        return str(self.derived.get("formula") or "")

    @property
    def natoms(self) -> Optional[int]:
        n = self.derived.get("natoms")
        return int(n) if isinstance(n, (int, float)) else None


@dataclass(frozen=True)
class BulkSummary:
    uid_full: str
    id_short: str
    label: str
    kind: str
    calculator: Optional[str] = None
    formula: str = ""
    natoms: Optional[int] = None
    spacegroup: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class BulkReferenceRecord:
    """Raw bulk identity used only for bounded integrity diagnostics."""

    uid_full: str
    id_short: str
    label: Optional[str]


@dataclass(frozen=True)
class Slab:
    uid_full: str
    id_short: str

    bulk_uid_full: str
    bulk_id_short: str

    miller: Sequence[int]

    # Optional (depends on how the slab was generated).
    size: Optional[Sequence[int]] = None
    vacuum: Optional[float] = None
    thickness: Optional[float] = None
    params: Optional[dict[str, Any]] = None

    payload: Optional[dict[str, Any]] = None

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def atoms(self) -> "Atoms | None":
        if not self.payload:
            return None
        structure = self.payload.get("structure")
        if not isinstance(structure, dict):
            return None
        return _dict_to_atoms(structure.get("atoms"))

    def to_ase(self) -> "Atoms | None":
        return self.atoms

    @property
    def n_atoms(self) -> int:
        """Number of atoms in the slab.

        Returns
        -------
        int
            Number of atoms, or 0 if atoms data not available.
        """
        if not self.payload:
            return 0
        structure = self.payload.get("structure")
        if not isinstance(structure, dict):
            return 0
        value = structure.get("n_atoms")
        return int(value) if isinstance(value, int) else 0

    @property
    def derived(self) -> dict[str, Any]:
        if not self.payload:
            return {}
        structure = self.payload.get("structure")
        if not isinstance(structure, dict):
            return {}
        characterization = structure.get("characterization")
        return characterization if isinstance(characterization, dict) else {}


@dataclass(frozen=True)
class SlabSummary:
    uid_full: str
    id_short: str
    bulk_uid_full: str
    bulk_id_short: str
    miller: Sequence[int]
    created_at: Optional[str] = None


@dataclass(frozen=True)
class SlabReferenceRecord:
    """Raw slab-to-bulk relationship used only for integrity diagnostics."""

    uid_full: str
    id_short: str
    bulk_pk: int
    bulk_uid_full: Optional[str]
    bulk_id_short: Optional[str]


@dataclass(frozen=True)
class Prototype:
    uid_full: str
    id_short: str

    run_uid_full: str
    run_id_short: str

    slab_a_uid_full: str
    slab_b_uid_full: str

    match_score: float
    hencky_norm: float
    interface_area: float
    natoms: int

    is_pareto: bool
    pareto_rank: Optional[int]

    payload: Optional[dict[str, Any]] = None

    created_at: Optional[str] = None


@dataclass(frozen=True)
class PrototypeSummary:
    uid_full: str
    id_short: str
    run_uid_full: str
    run_id_short: str
    slab_a_uid_full: str
    slab_a_id_short: str
    slab_b_uid_full: str
    slab_b_id_short: str
    match_score: float
    hencky_norm: float
    interface_area: float
    natoms: int
    d_cell: Optional[float]
    is_pareto: bool
    pareto_rank: Optional[int]
    pareto_policy: Optional[str] = None
    pareto_policy_version: Optional[int] = None
    pareto_population_scope: Optional[str] = None
    pareto_population_size: Optional[int] = None
    pareto_d_cell_key: Optional[int] = None
    pareto_status: str = "authoritative"
    payload: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None


@dataclass(frozen=True)
class Calculator:
    uid_full: str
    id_short: str
    family: str
    model: str
    device: str
    spec: dict[str, Any] = field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class CalculatorSummary:
    uid_full: str
    id_short: str
    family: str
    model: str
    device: str
    created_at: Optional[str] = None


@dataclass(frozen=True)
class Run:
    uid_full: str
    id_short: str
    run_type: str
    spec: dict[str, Any] = field(default_factory=dict)
    status: str = ""
    # Error payloads are JSON objects (may contain structured diagnostics).
    error: Optional[dict[str, Any]] = None
    progress: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class InterfaceSearch:
    """Authoritative named descriptor for one interface-search run.

    ``name`` is the unique user-facing project alias. ``search_identity`` is
    the unique scientific identity derived from the exact persisted surfaces,
    settings, and search implementation. Mutable execution state remains on
    the referenced :class:`Run`.
    """

    name: str
    search_identity: str
    run_uid_full: str
    run_id_short: str
    status: str
    spec: dict[str, Any] = field(default_factory=dict)
    error: Optional[dict[str, Any]] = None
    progress: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class ArtifactRef:
    """Pointer to an on-disk artifact associated with a run.

    Artifacts are stored by the ArtifactStore and referenced from the database
    by a stable UID, a short id, and a URI.
    """

    uid_full: str
    id_short: str
    run_uid_full: str

    # High-level artifact type (e.g. "log", "plot", "structure").
    kind: str

    # Location in the artifact store.
    uri: str

    # Arbitrary JSON-serializable metadata.
    metadata: Optional[dict[str, Any]] = None

    # Convenience for UX; not guaranteed to be populated when loaded from DB.
    run_id_short: Optional[str] = None

    created_at: Optional[str] = None


@dataclass(frozen=True)
class DerivedInterface:
    """A realized interface governed by one exact-current persisted spec."""

    uid_full: str
    id_short: str
    prototype_uid_full: str
    spec: dict[str, Any]
    label: str | None = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self) -> None:
        from calm.project.domain.contracts.derived_interface import (
            canonical_derived_interface_spec,
        )

        canonical = canonical_derived_interface_spec(
            self.spec,
            prototype_uid_full=self.prototype_uid_full,
        )
        object.__setattr__(self, "spec", canonical)

    @property
    def stage(self) -> str:
        return str(self.spec["stage"])

    @property
    def params(self) -> dict[str, Any]:
        return dict(self.spec["params"])

    @property
    def atoms_artifact_uid(self) -> str | None:
        value = self.spec.get("atoms_artifact_uid")
        return str(value) if value is not None else None

    @property
    def artifact_refs(self) -> list[dict[str, Any]]:
        return [dict(ref) for ref in self.spec.get("artifact_refs", [])]

    @property
    def strain_state(self) -> dict[str, Any] | None:
        value = self.spec.get("strain_state")
        return dict(value) if value is not None else None

    @property
    def strain_alpha(self) -> float:
        """Partition parameter: 0 leaves A unstrained; 1 leaves B unstrained."""
        return float(self.spec["strain_alpha"])

    @property
    def registry_shift_frac_a(self) -> tuple[float, float]:
        """Canonical fractional registry coordinate on the interface torus."""
        shift = self.spec["registry_shift_frac_a"]
        return float(shift[0]), float(shift[1])

    @property
    def z_padding(self) -> float:
        """Internal separation between lower and upper slabs in Angstroms."""
        return float(self.spec["z_padding"])

    @property
    def vacuum(self) -> float | None:
        """Periodic-boundary vacuum spacing in Angstroms."""
        value = self.spec["vacuum"]
        return None if value is None else float(value)


@dataclass(frozen=True)
class FollowupResult:
    uid_full: str
    id_short: str

    run_uid_full: str | None = None
    run_id_short: str | None = None

    prototype_uid_full: str | None = None
    prototype_id_short: str | None = None

    target_kind: str | None = None
    target_uid_full: str | None = None
    target_id_short: str | None = None

    kind: str = ""
    status: str = "done"

    # Scalar summary metrics persisted in followup_results.
    best_energy: float | None = None
    param1: float | None = None
    param2: float | None = None
    n_points: int | None = None

    payload: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class Edge:
    uid_full: str
    src_uid_full: str
    dst_uid_full: str
    kind: str
    payload: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class Dataset:
    uid_full: str
    id_short: str
    project_id: str | None = None
    name: str | None = None
    description: str | None = None
    metadata: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass(frozen=True)
class DatasetItem:
    uid_full: str
    dataset_uid_full: str
    id_short: str
    index: int | None = None
    metadata: Optional[dict[str, Any]] = None
    artifact_refs: Optional[list[dict[str, Any]]] = None
    created_at: Optional[str] = None

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass(frozen=True)
class Campaign:
    uid_full: str
    id_short: str
    project_id: str | None = None
    name: str | None = None
    spec: Optional[dict[str, Any]] = None
    created_at: Optional[str] = None

    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass(frozen=True)
class CampaignRun:
    uid_full: str
    id_short: str
    campaign_uid_full: str
    run_spec_hash: str | None = None
    backend_id: str | None = None
    status: str | None = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def __getitem__(self, key: str):
        return getattr(self, key)
