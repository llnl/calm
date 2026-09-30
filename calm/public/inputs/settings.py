"""Typed settings used by CALM's public workflow facades."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from numbers import Integral, Real
from typing import Any, Mapping

from calm.structure.standardization import (
    nonnegative_finite_float,
    positive_finite_float,
)
from calm.project.domain.contracts.dataset import (
    DATASET_SPLIT_POLICY_VERSION,
    canonical_dataset_schema,
)
from calm.interface.energy.contract import (
    UnsupportedReferenceWorkflowError,
    canonical_energy_formula,
    reference_energy_capability_contract,
)
from calm.interface.refinement.contract import (
    canonical_alpha_grid,
    canonical_strain_metric,
)
from calm.interface.matching.conditioning import DEFAULT_SUPERCELL_CONDITION_LIMIT


_DATASET_SOURCE_ROOTS = {
    "interface",
    "relaxation",
    "raw_energy",
    "thermodynamic",
    "lineage",
}
_DATASET_LINEAGE_ALIASES = {
    "prototype",
    "relaxed_interface",
    "relaxation_result",
    "raw_energy_result",
    "thermodynamic_result",
    "terminal_source",
}


def _validate_dataset_source_path(value: str, *, field_name: str) -> None:
    path = str(value).strip()
    parts = path.split(".")
    if len(parts) < 2 or any(not part for part in parts):
        raise ValueError(f"{field_name} must be a dotted joined-record path.")
    if parts[0] not in _DATASET_SOURCE_ROOTS:
        roots = ", ".join(sorted(_DATASET_SOURCE_ROOTS))
        raise ValueError(f"{field_name} must be rooted at one of: {roots}.")
    if parts[0] == "lineage" and (
        len(parts) != 2 or parts[1] not in _DATASET_LINEAGE_ALIASES
    ):
        aliases = ", ".join(
            f"lineage.{name}" for name in sorted(_DATASET_LINEAGE_ALIASES)
        )
        raise ValueError(f"{field_name} must use a public lineage alias: {aliases}.")


def _require_finite_positive(name: str, value: object) -> None:
    """Validate one finite positive floating-point setting."""
    result = float(value)
    if not isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")


def _require_integer_at_least(
    name: str,
    value: object,
    *,
    minimum: int,
) -> None:
    """Validate one exact integer setting with a lower bound."""
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer.")
    if int(value) < minimum:
        raise ValueError(f"{name} must be >= {minimum}.")


def _require_optional_integer_at_least(
    name: str,
    value: object | None,
    *,
    minimum: int,
) -> None:
    """Validate an optional exact integer setting with a lower bound."""
    if value is not None:
        _require_integer_at_least(name, value, minimum=minimum)


def _require_unit_interval(name: str, value: object) -> None:
    """Validate one finite floating-point setting in [0, 1]."""
    result = float(value)
    if not isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{name} must be finite and between 0 and 1.")


@dataclass(frozen=True, init=False)
class SearchSettings:
    """Operational controls for interface-superlattice search.

    Exact primitive-pair aggregation is mandatory for authoritative searches.
    No alternate matching or deduplication policy is accepted. Every field is
    validated before execution and participates in deterministic search identity.

    Attributes:
        max_principal_strain: Inclusive upper bound on the absolute principal
            Hencky strain admitted for either side. Dimensionless. Default: ``0.10``.
        max_atoms: Inclusive upper bound on the estimated interface atom count.
            ``None`` disables the public atom-count gate. Default: ``1000``.
        max_supercell_index: Largest positive surface-supercell index enumerated
            for each side. Default: ``12``.
        max_candidates: Maximum number of ranked candidates returned after the
            complete admitted population is classified. ``None`` uses the current
            operational result limit. Default: ``25``.
        mismatch_weight: Weight in ``[0, 1]`` assigned to cell mismatch in the
            post-Pareto ranking score. Default: ``0.5``.
        cond_max: Inclusive upper bound on the spectral condition number of
            admitted surface supercells. Default: ``1e6``.
        surface_symmetry_mode: ``"discover"`` validates discovered finite
            surface-symmetry groups; ``"identity_only"`` records the deliberately
            narrower identity equivalence. Default: ``"discover"``.
        surface_symprec: Cartesian tolerance supplied to surface-symmetry
            discovery, in angstrom. Default: ``1e-5``.
        surface_angle_tolerance: Dimensionless normal-direction mismatch tolerance
            used to validate discovered operations. Default: ``1e-8``.
        surface_metric_tolerance: Scale-free Frobenius residual tolerance used to
            validate surface-metric preservation. Default: ``1e-5``.
    """

    max_principal_strain: float = 0.10
    max_atoms: int | None = 1000
    max_supercell_index: int = 12
    max_candidates: int | None = 25
    mismatch_weight: float = 0.5
    cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT
    surface_symmetry_mode: str = "discover"
    surface_symprec: float = 1e-5
    surface_angle_tolerance: float = 1e-8
    surface_metric_tolerance: float = 1e-5

    def __init__(
        self,
        max_principal_strain: float = 0.10,
        max_atoms: int | None = 1000,
        max_supercell_index: int = 12,
        max_candidates: int | None = 25,
        mismatch_weight: float = 0.5,
        cond_max: float = DEFAULT_SUPERCELL_CONDITION_LIMIT,
        surface_symmetry_mode: str = "discover",
        surface_symprec: float = 1e-5,
        surface_angle_tolerance: float = 1e-8,
        surface_metric_tolerance: float = 1e-5,
    ) -> None:
        object.__setattr__(self, "max_principal_strain", max_principal_strain)
        object.__setattr__(self, "max_atoms", max_atoms)
        object.__setattr__(self, "max_supercell_index", max_supercell_index)
        object.__setattr__(self, "max_candidates", max_candidates)
        object.__setattr__(self, "mismatch_weight", mismatch_weight)
        object.__setattr__(self, "cond_max", cond_max)
        object.__setattr__(self, "surface_symmetry_mode", surface_symmetry_mode)
        object.__setattr__(self, "surface_symprec", surface_symprec)
        object.__setattr__(
            self,
            "surface_angle_tolerance",
            surface_angle_tolerance,
        )
        object.__setattr__(
            self,
            "surface_metric_tolerance",
            surface_metric_tolerance,
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SearchSettings":
        """Read one current coupled-search settings mapping."""

        return cls(**dict(value))

    def validate(self) -> None:
        _require_finite_positive(
            "SearchSettings.max_principal_strain",
            self.max_principal_strain,
        )
        _require_integer_at_least(
            "SearchSettings.max_supercell_index",
            self.max_supercell_index,
            minimum=1,
        )
        _require_optional_integer_at_least(
            "SearchSettings.max_atoms",
            self.max_atoms,
            minimum=1,
        )
        _require_optional_integer_at_least(
            "SearchSettings.max_candidates",
            self.max_candidates,
            minimum=0,
        )
        _require_unit_interval(
            "SearchSettings.mismatch_weight",
            self.mismatch_weight,
        )
        positive_finite_float("SearchSettings.cond_max", self.cond_max)
        if self.surface_symmetry_mode not in {"discover", "identity_only"}:
            raise ValueError(
                "SearchSettings.surface_symmetry_mode must be 'discover' "
                "or 'identity_only'."
            )
        positive_finite_float(
            "SearchSettings.surface_symprec",
            self.surface_symprec,
        )
        nonnegative_finite_float(
            "SearchSettings.surface_angle_tolerance",
            self.surface_angle_tolerance,
        )
        positive_finite_float(
            "SearchSettings.surface_metric_tolerance",
            self.surface_metric_tolerance,
        )

    def to_internal_config(self):
        self.validate()
        from calm.interface.config import PrototypeSearchConfig

        return PrototypeSearchConfig(
            k_max=int(self.max_supercell_index),
            cond_max=float(self.cond_max),
            eps_principal_max=float(self.max_principal_strain),
            N_at_max=int(self.max_atoms) if self.max_atoms is not None else 10**12,
            w_match=float(self.mismatch_weight),
            max_results=(
                int(self.max_candidates) if self.max_candidates is not None else 25
            ),
            surface_symmetry_mode=self.surface_symmetry_mode,
            surface_symprec=float(self.surface_symprec),
            surface_angle_tolerance=float(self.surface_angle_tolerance),
            surface_metric_tolerance=float(self.surface_metric_tolerance),
            correspondence_entry_limit=None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BuildSettings:
    """Operational controls for constructing an atomistic interface.

    Construction applies the selected coherent in-plane target metric, preserves
    the ordered contacting faces, translates side B on the periodic in-plane
    torus, and writes a vertical boundary-vacuum vector.

    Attributes:
        strain_partition: Which side receives coherent matching strain. Accepted
            canonical values are ``"both"``, ``"a"``, and ``"b"``; documented
            case aliases normalize to the same policies. Default: ``"both"``.
        alpha: Geodesic interpolation coordinate for ``strain_partition="both"``.
            ``0`` leaves side A unstrained, ``1`` leaves side B unstrained, and
            ``0.5`` selects the geometric midpoint. Default: ``0.5``.
        gap: Initial solid--solid separation along the interface normal, in
            angstrom. Default: ``1.5``.
        vacuum: Periodic boundary-vacuum thickness, in angstrom. Default: ``15.0``.
        translation: Fractional in-plane translation ``(u, v)`` of side B in the
            matched interface lattice. Values are interpreted periodically.
            Default: ``(0.0, 0.0)``.
    """

    strain_partition: str = "both"
    alpha: float = 0.5
    gap: float = 1.5
    vacuum: float = 15.0
    translation: tuple[float, float] = (0.0, 0.0)

    def validate(self) -> None:
        allowed = {"both", "a", "b", "A", "B", "side_a", "side_b"}
        if self.strain_partition not in allowed:
            raise ValueError(
                "BuildSettings.strain_partition must be one of 'both', 'a', or 'b'."
            )
        alpha = float(self.alpha)
        if not isfinite(alpha) or not 0.0 <= alpha <= 1.0:
            raise ValueError("BuildSettings.alpha must be finite and between 0 and 1.")
        gap = float(self.gap)
        if not isfinite(gap) or gap < 0.0:
            raise ValueError("BuildSettings.gap must be finite and non-negative.")
        vacuum = float(self.vacuum)
        if not isfinite(vacuum) or vacuum < 0.0:
            raise ValueError("BuildSettings.vacuum must be finite and non-negative.")
        translation = tuple(float(value) for value in self.translation)
        if len(translation) != 2 or not all(isfinite(value) for value in translation):
            raise ValueError(
                "BuildSettings.translation must contain two finite fractional "
                "coordinates."
            )

    def to_internal(self):
        self.validate()
        from calm.interface.config import InterfaceBuildConfig, StrainModel

        part = self.strain_partition
        if part in {"a", "A", "side_a"}:
            internal_part = "A_only"
        elif part in {"b", "B", "side_b"}:
            internal_part = "B_only"
        else:
            internal_part = "both"
        return (
            StrainModel(partition=internal_part, alpha=float(self.alpha)),
            InterfaceBuildConfig(
                z_padding=float(self.gap),
                vacuum_padding=float(self.vacuum),
                translation_frac=tuple(float(x) for x in self.translation),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RegistrySettings:
    """Controls for persisted translation-only registry refinement.

    The workflow holds strain partition, internal gap, and periodic vacuum fixed.
    It uses the versioned fractional-torus PCG64 protocol and the fixed score
    temperature ``0.03 eV/Å²``. Every field affects execution and authoritative
    run identity; fixed protocol constants are recorded in result provenance.

    Attributes:
        steps: Number of Monte Carlo proposal steps attempted on the periodic
            translation torus. Must be at least one. Default: ``500``.
        translation_step: Positive proposal scale in fractional lattice
            coordinates. ``None`` selects the operational value ``0.08``.
            Default: ``None``.
        seed: Non-negative explicit PCG64 seed. ``None`` derives a stable
            target-specific seed from the run and interface identities.
            Default: ``None``.
    """

    steps: int = 500
    translation_step: float | None = None
    seed: int | None = None

    @property
    def operational_translation_step(self) -> float:
        return 0.08 if self.translation_step is None else float(self.translation_step)

    def validate(self) -> None:
        _require_integer_at_least(
            "RegistrySettings.steps",
            self.steps,
            minimum=1,
        )
        _require_finite_positive(
            "RegistrySettings.translation_step",
            self.operational_translation_step,
        )
        _require_optional_integer_at_least(
            "RegistrySettings.seed",
            self.seed,
            minimum=0,
        )

    def validate_for_persisted_refinement(self) -> None:
        """Validate all settings for the authoritative persisted workflow."""
        self.validate()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "steps": int(self.steps),
            "translation_step": self.operational_translation_step,
            "seed": int(self.seed) if self.seed is not None else None,
        }


@dataclass(frozen=True)
class RelaxSettings:
    """Operational controls for authoritative structural relaxation.

    Every field affects execution, authoritative run identity, and persisted
    provenance. For interfaces, variable-cell relaxation exposes only in-plane
    cell degrees of freedom; the interface-normal boundary vector remains fixed.

    Attributes:
        fmax: Required maximum residual force for convergence, in eV/Å.
            Default: ``0.05``.
        steps: Maximum optimizer steps per target. Default: ``500``.
        relax_cell: ``False`` selects ionic/position-only relaxation. ``True``
            additionally permits the in-plane ``xx``, ``yy``, and ``xy`` cell
            components to relax. Default: ``False``.
    """

    fmax: float = 0.05
    steps: int = 500
    relax_cell: bool = False

    def validate(self) -> None:
        from calm.project.domain.contracts.relaxation import (
            canonical_relaxation_controls,
        )

        canonical_relaxation_controls(
            protocol=self.protocol,
            convergence={"force_tol": self.fmax},
            max_steps=self.steps,
            relax_cell=self.relax_cell,
        )

    @property
    def protocol(self) -> str:
        from calm.project.domain.contracts.relaxation import (
            FIXED_CELL_PROTOCOL,
            INTERFACE_CELL_PROTOCOL,
        )

        return INTERFACE_CELL_PROTOCOL if self.relax_cell else FIXED_CELL_PROTOCOL

    def to_dict(self) -> dict[str, Any]:
        from calm.project.domain.contracts.relaxation import (
            canonical_relaxation_controls,
        )

        controls = canonical_relaxation_controls(
            protocol=self.protocol,
            convergence={"force_tol": self.fmax},
            max_steps=self.steps,
            relax_cell=self.relax_cell,
        )
        return {
            "fmax": controls.force_tolerance_eV_per_A,
            "steps": controls.max_steps,
            "relax_cell": controls.relax_cell,
        }

    def to_stage_kwargs(self) -> dict[str, Any]:
        from calm.project.domain.contracts.relaxation import (
            canonical_relaxation_controls,
        )

        controls = canonical_relaxation_controls(
            protocol=self.protocol,
            convergence={"force_tol": self.fmax},
            max_steps=self.steps,
            relax_cell=self.relax_cell,
        )
        return {
            "protocol": controls.protocol,
            "convergence": {
                "force_tol": controls.force_tolerance_eV_per_A,
            },
            "max_steps": controls.max_steps,
            "payload": {"relax_settings": self.to_dict()},
        }


@dataclass(frozen=True)
class EnergySettings:
    """Operational controls for authoritative raw total-energy evaluation.

    The selected calculator backend is supplied separately to the workflow. The
    calculation mode affects execution, run identity, and persisted provenance.

    Attributes:
        mode: Calculation protocol. The stable public contract supports exactly
            ``"single_point"``. Default: ``"single_point"``.
    """

    mode: str = "single_point"

    def validate(self) -> None:
        if self.mode != "single_point":
            raise ValueError("EnergySettings.mode must be 'single_point'.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {"mode": self.mode}

    def to_stage_kwargs(self) -> dict[str, Any]:
        self.validate()
        return {"calculation": self.to_dict()}


@dataclass(frozen=True)
class ReferenceEnergyCapability:
    """Typed support contract for one thermodynamic reference formula."""

    formula: str
    quantity: str
    calculated_reference_mode: str
    reference_kinds: tuple[str, ...]
    manual_reference_fields: tuple[str, ...]
    requirements: tuple[str, ...]
    limitations: tuple[str, ...]

    @classmethod
    def from_formula(cls, formula: str) -> "ReferenceEnergyCapability":
        return cls(**reference_energy_capability_contract(formula))

    @property
    def calculated_references_supported(self) -> bool:
        return self.calculated_reference_mode == "first_class"

    @property
    def manual_references_required(self) -> bool:
        return not self.calculated_references_supported

    def raise_for_calculated_references(self) -> None:
        if self.calculated_references_supported:
            return
        raise UnsupportedReferenceWorkflowError(
            f"{self.formula} has no calculated-reference workflow in the stable "
            "contract. Supply explicit ReferenceEnergySettings using: "
            + ", ".join(self.manual_reference_fields)
            + "."
        )

    def summary(self) -> str:
        support = (
            "first-class calculated references"
            if self.calculated_references_supported
            else "manual references only"
        )
        lines = [
            f"Reference capability: {self.formula}",
            f" quantity={self.quantity}",
            f" support={support}",
        ]
        if self.reference_kinds:
            lines.append(" reference_kinds=" + ", ".join(self.reference_kinds))
        lines.append(
            " manual_reference_fields=" + ", ".join(self.manual_reference_fields)
        )
        if self.requirements:
            lines.append(" requirements=" + "; ".join(self.requirements))
        if self.limitations:
            lines.append(" limitations=" + "; ".join(self.limitations))
        return "\n".join(lines)


@dataclass(frozen=True)
class EnergyConvention:
    """Explicit convention for a derived interfacial thermodynamic quantity.

    CALM never infers the reference process, periodic-interface multiplicity, or
    normalization area. These choices are persisted with every derived result.

    Attributes:
        formula: Exact reference-process identifier. Supported values are
            ``"interface_excess_strained_bulk"``,
            ``"work_of_separation_unrelaxed_surfaces"``, and
            ``"work_of_adhesion_relaxed_surfaces"``.
        n_interfaces: Positive number of equivalent interfaces represented by the
            periodic cell. There is no inferred default.
        area_source: Area used in the normalization denominator.
            ``"authoritative_interface_area"`` uses the realized atomistic cell;
            ``"prototype_interface_area"`` uses the search prototype area.
            Default: ``"authoritative_interface_area"``.
    """

    formula: str
    n_interfaces: int
    area_source: str = "authoritative_interface_area"

    @property
    def quantity(self) -> str:
        _formula, quantity = canonical_energy_formula(self.formula)
        return quantity

    def reference_capability(self) -> ReferenceEnergyCapability:
        """Return the current support contract for this reference formula."""
        self.validate()
        return ReferenceEnergyCapability.from_formula(self.formula)

    def validate(self) -> None:
        _ = self.quantity
        if (
            isinstance(self.n_interfaces, bool)
            or not isinstance(self.n_interfaces, Integral)
            or int(self.n_interfaces) < 1
        ):
            raise ValueError(
                "EnergyConvention.n_interfaces must be a positive integer."
            )
        if self.area_source not in {
            "authoritative_interface_area",
            "prototype_interface_area",
        }:
            raise ValueError(
                "EnergyConvention.area_source must be "
                "'authoritative_interface_area' or 'prototype_interface_area'."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "formula": self.formula,
            "quantity": self.quantity,
            "n_interfaces": int(self.n_interfaces),
            "area_source": self.area_source,
        }


@dataclass(frozen=True)
class ReferenceEnergySettings:
    """Explicit manual reference values for a thermodynamic convention.

    Values are named with their units to prevent ambiguous interpretation. Only
    fields required by the selected ``EnergyConvention`` are accepted. Supplying
    unrelated reference families is rejected.

    Attributes:
        bulk_a_eV_per_formula_unit: Strained-bulk A energy per formula unit, in
            eV. Required only by ``interface_excess_strained_bulk``. Default:
            ``None``.
        bulk_b_eV_per_formula_unit: Strained-bulk B energy per formula unit, in
            eV. Required only by ``interface_excess_strained_bulk``. Default:
            ``None``.
        n_formula_units_a: Positive number of bulk-A formula units represented in
            the interface cell. Default: ``None``.
        n_formula_units_b: Positive number of bulk-B formula units represented in
            the interface cell. Default: ``None``.
        surface_a_total_energy_eV: Total energy of the selected isolated surface-A
            reference, in eV. Used by separation and adhesion conventions. Default:
            ``None``.
        surface_b_total_energy_eV: Total energy of the selected isolated surface-B
            reference, in eV. Used by separation and adhesion conventions. Default:
            ``None``.
        metadata: Additional JSON-compatible provenance for manual references.
            Default: an empty mapping.
    """

    bulk_a_eV_per_formula_unit: float | None = None
    bulk_b_eV_per_formula_unit: float | None = None
    n_formula_units_a: int | None = None
    n_formula_units_b: int | None = None
    surface_a_total_energy_eV: float | None = None
    surface_b_total_energy_eV: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def _finite(value: Any, *, name: str) -> float:
        number = float(value)
        if not isfinite(number):
            raise ValueError(f"{name} must be finite.")
        return number

    @staticmethod
    def _positive_count(value: Any, *, name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, Integral):
            raise ValueError(f"{name} must be a positive integer.")
        count = int(value)
        if count < 1:
            raise ValueError(f"{name} must be a positive integer.")
        return count

    def validate_for(self, convention: EnergyConvention) -> None:
        convention.validate()
        if not isinstance(self.metadata, Mapping):
            raise TypeError("ReferenceEnergySettings.metadata must be a mapping.")
        bulk_fields = (
            self.bulk_a_eV_per_formula_unit,
            self.bulk_b_eV_per_formula_unit,
            self.n_formula_units_a,
            self.n_formula_units_b,
        )
        surface_fields = (
            self.surface_a_total_energy_eV,
            self.surface_b_total_energy_eV,
        )
        if convention.formula == "interface_excess_strained_bulk":
            if any(value is None for value in bulk_fields):
                raise ValueError(
                    "interface_excess_strained_bulk requires bulk A/B energies "
                    "per formula unit and formula-unit counts."
                )
            if any(value is not None for value in surface_fields):
                raise ValueError(
                    "Surface reference energies are not used by "
                    "interface_excess_strained_bulk."
                )
            self._finite(
                self.bulk_a_eV_per_formula_unit,
                name="bulk_a_eV_per_formula_unit",
            )
            self._finite(
                self.bulk_b_eV_per_formula_unit,
                name="bulk_b_eV_per_formula_unit",
            )
            self._positive_count(
                self.n_formula_units_a,
                name="n_formula_units_a",
            )
            self._positive_count(
                self.n_formula_units_b,
                name="n_formula_units_b",
            )
        else:
            if any(value is None for value in surface_fields):
                raise ValueError(
                    f"{convention.formula} requires surface A/B total energies."
                )
            if any(value is not None for value in bulk_fields):
                raise ValueError(
                    "Bulk reference fields are not used by surface-separation "
                    "or adhesion conventions."
                )
            self._finite(
                self.surface_a_total_energy_eV,
                name="surface_a_total_energy_eV",
            )
            self._finite(
                self.surface_b_total_energy_eV,
                name="surface_b_total_energy_eV",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bulk_a_eV_per_formula_unit": self.bulk_a_eV_per_formula_unit,
            "bulk_b_eV_per_formula_unit": self.bulk_b_eV_per_formula_unit,
            "n_formula_units_a": self.n_formula_units_a,
            "n_formula_units_b": self.n_formula_units_b,
            "surface_a_total_energy_eV": self.surface_a_total_energy_eV,
            "surface_b_total_energy_eV": self.surface_b_total_energy_eV,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DatasetFeature:
    """Declare one named machine-learning feature from a joined dataset row.

    The declaration is identity-bearing and CALM materializes the resolved value
    into every authoritative learning-dataset item.

    Attributes:
        name: Unique output column name within the feature declarations.
        source: Dotted joined-record path rooted at ``interface``, ``relaxation``,
            ``raw_energy``, ``thermodynamic``, or ``lineage``.
        dtype: Required scalar coercion: ``"float"``, ``"int"``, ``"bool"``,
            or ``"str"``. Default: ``"float"``.
        required: Whether missing or invalid values fail readiness validation.
            Default: ``True``.
        units: Optional human-readable units persisted with the declaration.
            Default: ``None``.
        description: Optional scientific description of the feature. Default:
            ``None``.
    """

    name: str
    source: str
    dtype: str = "float"
    required: bool = True
    units: str | None = None
    description: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "DatasetFeature":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(**dict(value))
        raise TypeError("Dataset features must be DatasetFeature objects or mappings.")

    def validate(self) -> None:
        if not str(self.name).strip():
            raise ValueError("DatasetFeature.name must be non-empty.")
        _validate_dataset_source_path(
            self.source,
            field_name="DatasetFeature.source",
        )
        if self.dtype not in {"float", "int", "bool", "str"}:
            raise ValueError(
                "DatasetFeature.dtype must be 'float', 'int', 'bool', or 'str'."
            )
        if not isinstance(self.required, bool):
            raise TypeError("DatasetFeature.required must be a bool.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        row: dict[str, Any] = {
            "name": str(self.name),
            "source": str(self.source),
            "dtype": self.dtype,
            "required": self.required,
        }
        if self.units is not None:
            row["units"] = str(self.units)
        if self.description is not None:
            row["description"] = str(self.description)
        return row


@dataclass(frozen=True)
class DatasetTarget:
    """Declare one named supervised-learning target from a joined dataset row.

    Attributes:
        name: Unique output column name within the target declarations.
        source: Dotted joined-record path rooted at ``interface``, ``relaxation``,
            ``raw_energy``, ``thermodynamic``, or ``lineage``.
        dtype: Required scalar coercion: ``"float"``, ``"int"``, ``"bool"``,
            or ``"str"``. Default: ``"float"``.
        required: Whether missing or invalid values fail readiness validation.
            Default: ``True``.
        units: Optional human-readable units persisted with the declaration.
            Default: ``None``.
        description: Optional scientific description of the target. Default:
            ``None``.
    """

    name: str
    source: str
    dtype: str = "float"
    required: bool = True
    units: str | None = None
    description: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "DatasetTarget":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(**dict(value))
        raise TypeError("Dataset targets must be DatasetTarget objects or mappings.")

    def validate(self) -> None:
        if not str(self.name).strip():
            raise ValueError("DatasetTarget.name must be non-empty.")
        _validate_dataset_source_path(
            self.source,
            field_name="DatasetTarget.source",
        )
        if self.dtype not in {"float", "int", "bool", "str"}:
            raise ValueError(
                "DatasetTarget.dtype must be 'float', 'int', 'bool', or 'str'."
            )
        if not isinstance(self.required, bool):
            raise TypeError("DatasetTarget.required must be a bool.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        row: dict[str, Any] = {
            "name": str(self.name),
            "source": str(self.source),
            "dtype": self.dtype,
            "required": self.required,
        }
        if self.units is not None:
            row["units"] = str(self.units)
        if self.description is not None:
            row["description"] = str(self.description)
        return row


@dataclass(frozen=True)
class DatasetSplitSettings:
    """Current deterministic group-preserving split policy.

    Policy version 2 hashes canonical seed/group bytes and compares the exact
    unsigned 64-bit prefix ratio with half-open binary64 thresholds. All members
    of one leakage group receive the same partition.

    Attributes:
        train_fraction: Non-negative train interval fraction. Default: ``0.8``.
        validation_fraction: Non-negative validation interval fraction.
            Default: ``0.1``.
        test_fraction: Non-negative test interval fraction. Default: ``0.1``.
        seed: Exact integer included in deterministic split decisions.
            Default: ``0``.
        policy_version: Required split-policy version. Current/default value: ``2``.

    Notes:
        The three fractions must sum to one within ``1e-12``. Mappings must
        declare ``policy_version`` explicitly; unversioned historical mappings
        are rejected rather than reinterpreted.
    """

    train_fraction: float = 0.8
    validation_fraction: float = 0.1
    test_fraction: float = 0.1
    seed: int = 0
    policy_version: int = DATASET_SPLIT_POLICY_VERSION

    @classmethod
    def from_value(cls, value: Any) -> "DatasetSplitSettings":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            payload = dict(value)
            if "policy_version" not in payload:
                raise ValueError(
                    "Dataset split mappings must declare policy_version=2."
                )
            return cls(**payload)
        raise TypeError(
            "split must be a DatasetSplitSettings object, mapping, or None."
        )

    def validate(self) -> None:
        raw_fractions = (
            self.train_fraction,
            self.validation_fraction,
            self.test_fraction,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, Real)
            for value in raw_fractions
        ):
            raise TypeError("Dataset split fractions must be real numbers.")
        fractions = tuple(float(value) for value in raw_fractions)
        if any(not isfinite(value) or value < 0.0 for value in fractions):
            raise ValueError("Dataset split fractions must be finite and non-negative.")
        if abs(sum(fractions) - 1.0) > 1.0e-12:
            raise ValueError("Dataset split fractions must sum to 1.0.")
        if not isinstance(self.seed, Integral) or isinstance(self.seed, bool):
            raise TypeError("DatasetSplitSettings.seed must be an integer.")
        if not isinstance(self.policy_version, Integral) or isinstance(
            self.policy_version, bool
        ):
            raise TypeError("DatasetSplitSettings.policy_version must be an integer.")
        if int(self.policy_version) != DATASET_SPLIT_POLICY_VERSION:
            raise ValueError(
                "DatasetSplitSettings.policy_version must equal "
                f"{DATASET_SPLIT_POLICY_VERSION}."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "train_fraction": float(self.train_fraction),
            "validation_fraction": float(self.validation_fraction),
            "test_fraction": float(self.test_fraction),
            "seed": int(self.seed),
            "policy_version": int(self.policy_version),
        }


def _validate_dataset_policies(settings: "DatasetSettings") -> None:
    if settings.duplicate_policy not in {"error", "skip"}:
        raise ValueError("DatasetSettings.duplicate_policy must be 'error' or 'skip'.")
    if settings.failure_policy not in {"error", "exclude", "include"}:
        raise ValueError(
            "DatasetSettings.failure_policy must be 'error', 'exclude', or 'include'."
        )
    if not isinstance(settings.require_complete_provenance, bool):
        raise TypeError("DatasetSettings.require_complete_provenance must be a bool.")


def _validate_dataset_fields(settings: "DatasetSettings") -> None:
    for feature in settings.features:
        feature.validate()
    for target in settings.targets:
        target.validate()

    feature_names = [feature.name for feature in settings.features]
    target_names = [target.name for target in settings.targets]
    if len(feature_names) != len(set(feature_names)):
        raise ValueError("Dataset feature names must be unique.")
    if len(target_names) != len(set(target_names)):
        raise ValueError("Dataset target names must be unique.")

    overlap = sorted(set(feature_names) & set(target_names))
    if overlap:
        raise ValueError(
            "Dataset feature and target names must not overlap: " + ", ".join(overlap)
        )


def _validate_dataset_grouping(settings: "DatasetSettings") -> None:
    for value in settings.group_by:
        _validate_dataset_source_path(
            value,
            field_name="DatasetSettings.group_by entries",
        )
    if len(settings.group_by) != len(set(settings.group_by)):
        raise ValueError("DatasetSettings.group_by entries must be unique.")
    if settings.split is not None:
        settings.split.validate()


def _validate_dataset_schema_controls(settings: "DatasetSettings") -> None:
    learning_controls = bool(
        settings.features
        or settings.targets
        or settings.group_by
        or settings.split is not None
    )
    if not settings.is_learning_dataset:
        if learning_controls:
            raise ValueError(
                "features, targets, group_by, and split are only supported by "
                "calm.interface_learning.v1."
            )
        return

    if settings.failure_policy == "include":
        raise ValueError(
            "calm.interface_learning.v1 does not include failed samples; "
            "use failure_policy='error' or 'exclude'."
        )
    if not settings.require_complete_provenance:
        raise ValueError(
            "calm.interface_learning.v1 requires require_complete_provenance=True."
        )
    if not settings.features:
        raise ValueError(
            "calm.interface_learning.v1 requires at least one DatasetFeature."
        )
    if not settings.targets:
        raise ValueError(
            "calm.interface_learning.v1 requires at least one DatasetTarget."
        )
    if not settings.group_by:
        raise ValueError(
            "calm.interface_learning.v1 requires group_by to prevent leakage."
        )
    if settings.split is None:
        raise ValueError("calm.interface_learning.v1 requires DatasetSplitSettings.")


@dataclass(frozen=True)
class DatasetSettings:
    """Operational lifecycle and learning contract for a project dataset.

    Homogeneous interface, raw-energy, and thermodynamic schemas remain
    available. ``calm.interface_learning.v1`` joins the authoritative relaxed
    structure, relaxation result, raw energy, and optional thermodynamic result
    under explicit learning declarations.

    Attributes:
        schema_version: Exact public dataset schema. Default:
            ``"calm.interface.v1"``.
        duplicate_policy: Existing-membership behavior: ``"error"`` or
            ``"skip"``. Default: ``"error"``.
        failure_policy: Terminal-source behavior: ``"error"``, ``"exclude"``,
            or ``"include"`` where supported. Default: ``"error"``.
        require_complete_provenance: Require complete authoritative lineage for
            admitted items. Learning datasets require ``True``. Default: ``True``.
        features: Ordered ``DatasetFeature`` declarations. Required and non-empty
            for ``calm.interface_learning.v1``. Default: ``()``.
        targets: Ordered ``DatasetTarget`` declarations. Required and non-empty
            for ``calm.interface_learning.v1``. Default: ``()``.
        group_by: Dotted lineage paths defining leakage-safe groups. Required for
            learning datasets. Default: ``()``.
        split: Deterministic ``DatasetSplitSettings``. Required for learning
            datasets and otherwise omitted. Default: ``None``.
    """

    schema_version: str = "calm.interface.v1"
    duplicate_policy: str = "error"
    failure_policy: str = "error"
    require_complete_provenance: bool = True
    features: tuple[DatasetFeature, ...] = ()
    targets: tuple[DatasetTarget, ...] = ()
    group_by: tuple[str, ...] = ()
    split: DatasetSplitSettings | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            canonical_dataset_schema(self.schema_version),
        )
        object.__setattr__(
            self,
            "features",
            tuple(DatasetFeature.from_value(value) for value in self.features),
        )
        object.__setattr__(
            self,
            "targets",
            tuple(DatasetTarget.from_value(value) for value in self.targets),
        )
        object.__setattr__(
            self,
            "group_by",
            tuple(str(value) for value in self.group_by),
        )
        if self.split is not None:
            object.__setattr__(
                self,
                "split",
                DatasetSplitSettings.from_value(self.split),
            )

    @property
    def schema(self) -> str:
        return canonical_dataset_schema(self.schema_version)

    @property
    def is_learning_dataset(self) -> bool:
        return self.schema == "calm.interface_learning.v1"

    def validate(self) -> None:
        _ = self.schema
        _validate_dataset_policies(self)
        _validate_dataset_fields(self)
        _validate_dataset_grouping(self)
        _validate_dataset_schema_controls(self)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        row: dict[str, Any] = {
            "schema_version": self.schema,
            "duplicate_policy": self.duplicate_policy,
            "failure_policy": self.failure_policy,
            "require_complete_provenance": self.require_complete_provenance,
        }
        if self.is_learning_dataset:
            row.update(
                {
                    "features": [value.to_dict() for value in self.features],
                    "targets": [value.to_dict() for value in self.targets],
                    "group_by": list(self.group_by),
                    "split": self.split.to_dict() if self.split is not None else None,
                }
            )
        return row


@dataclass(frozen=True)
class StrainPartitionSettings:
    """Operational settings for authoritative strain-partition selection.

    Alpha grids are canonicalized so equivalent requests have identical run
    identity. Selection evaluates the persisted scan and chooses the alpha that
    minimizes the explicitly named scientific objective.

    Attributes:
        target_metric: Required exact metric name, including units. Accepted
            values are ``"gamma_eV_per_A2"`` and
            ``"potential_energy_density_eV_per_A2"``.
        alphas: Optional finite, non-empty alpha grid in ``[0, 1]``. Values are
            de-duplicated and sorted. ``None`` selects the canonical operational
            grid. Default: ``None``.
    """

    target_metric: str
    alphas: tuple[float, ...] | None = None

    def resolve_metric(self) -> str:
        return canonical_strain_metric(self.target_metric)

    def resolve_alphas(self) -> tuple[float, ...]:
        return canonical_alpha_grid(self.alphas)

    def validate(self) -> None:
        self.resolve_metric()
        self.resolve_alphas()

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "target_metric": self.resolve_metric(),
            "alphas": list(self.resolve_alphas()),
        }
