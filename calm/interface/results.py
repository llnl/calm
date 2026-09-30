"""calm.interface.results

Result objects for the v2 pipeline.

These are immutable and designed to be persisted into a workspace database.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, overload

import numpy as np

from calm.symmetry.surface_group import SurfaceSymmetryProvenance
from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    strain_size_pareto,
)
from calm.interface.energy.contract import (
    EV_PER_A2_TO_J_PER_M2 as EV_PER_A2_TO_J_PER_M2,
)
from calm.interface.matching.audit import CoupledMatchEnumerationAudit
from calm.interface.refinement.strain import INCREMENTAL_INTERFACE_MATCHING_SCOPE
from calm.serialization.regression import fingerprint_json

from calm.interface.config import PrototypeSearchConfig
from calm.interface.model import InterfacePrototype

if TYPE_CHECKING:
    from calm.viz.pareto import ParetoFront2DResult


@dataclass(frozen=True)
class InterfaceEnergyScalarResult:
    """Scalar interface-energy arithmetic result.

    This lightweight result is intended for cases where the interface total
    energy, strained-bulk reference energies, formula-unit counts, number of
    interfaces, and area are already known.

    Units
    -----
    - energies are stored in eV
    - area/denominator are stored in Å²
    - ``gamma_eV_per_A2`` is stored in eV/Å²
    - ``gamma_J_per_m2`` is stored in J/m²

    Notes
    -----
    The associated public helper performs only arithmetic. It does not generate
    strained bulk references or run any calculator.
    """

    numerator_eV: float
    denominator_A2: float
    gamma_eV_per_A2: float
    gamma_J_per_m2: float
    interface_energy_eV: float
    n_formula_units_A: float
    n_formula_units_B: float
    mu_A_eV_per_formula_unit: float
    mu_B_eV_per_formula_unit: float
    interface_area_A2: float
    n_interfaces: int
    thermodynamic_formula: str = "interface_excess_strained_bulk"
    thermodynamic_quantity: str = "interface_excess_energy"
    strained_bulk_reference_mode: str = "unrelaxed_scaled_positions"
    bulk_reference_relaxed: bool = False
    gamma_reference_convention: str = "strained_unrelaxed_bulk_subtraction"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""

        return {
            "numerator_eV": self.numerator_eV,
            "denominator_A2": self.denominator_A2,
            "gamma_eV_per_A2": self.gamma_eV_per_A2,
            "gamma_J_per_m2": self.gamma_J_per_m2,
            "interface_energy_eV": self.interface_energy_eV,
            "n_formula_units_A": self.n_formula_units_A,
            "n_formula_units_B": self.n_formula_units_B,
            "mu_A_eV_per_formula_unit": self.mu_A_eV_per_formula_unit,
            "mu_B_eV_per_formula_unit": self.mu_B_eV_per_formula_unit,
            "interface_area_A2": self.interface_area_A2,
            "n_interfaces": self.n_interfaces,
            "thermodynamic_formula": self.thermodynamic_formula,
            "thermodynamic_quantity": self.thermodynamic_quantity,
            "strained_bulk_reference_mode": self.strained_bulk_reference_mode,
            "bulk_reference_relaxed": self.bulk_reference_relaxed,
            "gamma_reference_convention": self.gamma_reference_convention,
        }


@dataclass(frozen=True)
class PrototypeSearchResult:
    """Container for the results of a prototype search.

    For convenience, ``slab_a_uid`` and ``slab_b_uid`` may be omitted when
    ``prototypes`` is non-empty; in that case they are inferred from the
    prototypes and validated for consistency.

    When ``prototypes`` is empty, ``slab_a_uid`` and ``slab_b_uid`` must be
    provided explicitly.
    """

    slab_a_uid: str = ""
    slab_b_uid: str = ""

    # Optional versioned enumeration accounting for the coupled search.
    enumeration_audit: CoupledMatchEnumerationAudit | None = None
    surface_symmetry_a: SurfaceSymmetryProvenance | None = None
    surface_symmetry_b: SurfaceSymmetryProvenance | None = None
    config: PrototypeSearchConfig = field(default_factory=PrototypeSearchConfig)
    prototypes: list[InterfacePrototype] = field(default_factory=list)

    pareto_policy: str | None = None
    pareto_policy_version: int | None = None
    pareto_population_scope: str | None = None
    pareto_population_size: int = 0
    pareto_front_uids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.enumeration_audit is not None:
            self.enumeration_audit.validate()
            if int(self.enumeration_audit.k_max) != int(self.config.k_max):
                raise ValueError("enumeration_audit.k_max does not match config.k_max")
        if (self.surface_symmetry_a is None) != (self.surface_symmetry_b is None):
            raise ValueError(
                "surface symmetry provenance must be recorded for both "
                "slabs or neither."
            )
        for label, provenance in (
            ("surface_symmetry_a", self.surface_symmetry_a),
            ("surface_symmetry_b", self.surface_symmetry_b),
        ):
            if provenance is None:
                continue
            if provenance.status == "failed":
                raise ValueError(f"{label} cannot contain failed-run provenance.")
            if provenance.mode != self.config.surface_symmetry_mode:
                raise ValueError(
                    f"{label}.mode does not match config.surface_symmetry_mode."
                )
            expected_controls = (
                ("symprec", self.config.surface_symprec),
                (
                    "angle_tolerance",
                    self.config.surface_angle_tolerance,
                ),
                (
                    "metric_tolerance",
                    self.config.surface_metric_tolerance,
                ),
            )
            for field_name, expected in expected_controls:
                if float(getattr(provenance, field_name)) != float(expected):
                    raise ValueError(
                        f"{label}.{field_name} does not match search config."
                    )

        # Ensure the result always has a well-defined slab pair.
        #
        # Public UX goal: allow a lightweight construction of PrototypeSearchResult
        # when the slab pair is already known (e.g., in tests or after JSON
        # round-trip), without requiring every prototype payload to redundantly
        # carry slab ids.
        #
        # Policy:
        # - If slab_a_uid/slab_b_uid are provided, keep them and validate prototypes
        #   only if prototypes expose these fields.
        # - If either slab uid is missing, attempt to infer both from the first
        #   prototype (dict-like or attribute-based). If inference is impossible,
        #   raise.
        def _proto_field(p: Any, name: str) -> str | None:
            if isinstance(p, dict):
                value = p.get(name)
            else:
                value = getattr(p, name, None)
            return None if value is None else str(value)

        a_in = str(self.slab_a_uid) if self.slab_a_uid is not None else ""
        b_in = str(self.slab_b_uid) if self.slab_b_uid is not None else ""

        if (not a_in) or (not b_in):
            if not self.prototypes:
                raise ValueError(
                    "PrototypeSearchResult requires slab_a_uid and slab_b_uid when prototypes is empty."
                )
            a0 = _proto_field(self.prototypes[0], "slab_a_uid")
            b0 = _proto_field(self.prototypes[0], "slab_b_uid")
            if not a0 or not b0:
                raise ValueError(
                    "PrototypeSearchResult requires slab_a_uid and slab_b_uid (either provided explicitly "
                    "or present on prototypes)."
                )
            object.__setattr__(self, "slab_a_uid", a0)
            object.__setattr__(self, "slab_b_uid", b0)
            a_in, b_in = a0, b0

        # Validate that all prototypes agree with the slab pair, when they carry
        # slab ids (dict-like or attribute-based). If a prototype does not expose
        # slab ids, we skip validation for that prototype.
        for i, p in enumerate(self.prototypes):
            pa = _proto_field(p, "slab_a_uid")
            pb = _proto_field(p, "slab_b_uid")
            if pa is not None and pa != a_in:
                raise ValueError(
                    f"PrototypeSearchResult: prototypes[{i}].slab_a_uid={pa!r} does not match slab_a_uid={a_in!r}."
                )
            if pb is not None and pb != b_in:
                raise ValueError(
                    f"PrototypeSearchResult: prototypes[{i}].slab_b_uid={pb!r} does not match slab_b_uid={b_in!r}."
                )

        def _value(item: Any, name: str, default: Any = None) -> Any:
            if isinstance(item, dict):
                return item.get(name, default)
            return getattr(item, name, default)

        authoritative = bool(self.prototypes) and all(
            _value(item, "pareto_policy") == STRAIN_SIZE_PARETO_POLICY
            and _value(item, "pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
            and _value(item, "pareto_population_scope")
            == STRAIN_SIZE_PARETO_POPULATION_SCOPE
            and _value(item, "pareto_d_cell_key") is not None
            for item in self.prototypes
        )

        if self.prototypes and not authoritative:
            result = strain_size_pareto(
                self.prototypes,
                atom_count="n_atoms_interface",
                d_cell="d_cell",
                ids="prototype_uid",
                policy="current_result_strain_size_pareto",
                population_scope="current_result_population",
            )
            object.__setattr__(self, "pareto_policy", result.policy)
            object.__setattr__(self, "pareto_policy_version", result.version)
            object.__setattr__(self, "pareto_population_scope", result.population_scope)
            object.__setattr__(self, "pareto_population_size", result.population_size)
            object.__setattr__(self, "pareto_front_uids", result.front_ids)
        elif authoritative:
            first = self.prototypes[0]
            if self.pareto_policy is None:
                object.__setattr__(
                    self, "pareto_policy", _value(first, "pareto_policy")
                )
            if self.pareto_policy_version is None:
                object.__setattr__(
                    self,
                    "pareto_policy_version",
                    _value(first, "pareto_policy_version"),
                )
            if self.pareto_population_scope is None:
                object.__setattr__(
                    self,
                    "pareto_population_scope",
                    _value(first, "pareto_population_scope"),
                )
            population_size = int(self.pareto_population_size)
            if population_size <= 0:
                population_size = max(
                    int(_value(item, "pareto_population_size", 0) or 0)
                    for item in self.prototypes
                )
                object.__setattr__(self, "pareto_population_size", population_size)
            if not self.pareto_front_uids:
                front = tuple(
                    str(
                        _proto_field(item, "prototype_uid") or _proto_field(item, "uid")
                    )
                    for item in self.prototypes
                    if bool(_value(item, "is_pareto", False))
                )
                if front and all(uid != "None" for uid in front):
                    object.__setattr__(self, "pareto_front_uids", front)

    # ---------------------------------------------------------------------
    # Sequence-like UX helpers
    # ---------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of prototypes.

        Public UX convenience: allows ``len(result)``, truthiness checks, and
        simple notebook usage without reaching into ``result.prototypes``.
        """

        return len(self.prototypes)

    def __iter__(self) -> Iterator[Any]:
        """Iterate over prototypes (in stored order)."""

        return iter(self.prototypes)

    @overload
    def __getitem__(self, idx: int) -> Any: ...

    @overload
    def __getitem__(self, idx: slice) -> list[Any]: ...

    def __getitem__(self, idx: int | slice) -> Any | list[Any]:
        """Index/slice into the stored prototypes.

        - ``result[i]`` returns a single prototype
        - ``result[i:j]`` returns a *list* of prototypes
        """

        return self.prototypes[idx]

    # ---------------------------------------------------------------------
    # Pareto utilities (part of the public UX surface)
    # ---------------------------------------------------------------------

    def pareto_front_2d(
        self,
        *,
        x: str = "n_atoms_interface",
        y: str = "d_cell",
        ids: str = "prototype_uid",
        strict: bool = True,
        minimize: tuple[bool, bool] = (True, True),
    ) -> "ParetoFront2DResult":
        """Compute a 2D Pareto front over the stored prototypes.

        This is a thin wrapper around :func:`calm.viz.pareto.pareto_front_2d`.

        Parameters
        ----------
        x, y
            Feature names to use for the 2D dominance calculation.

        ids
            Stable identifier field.

        strict
            If True, equal points do **not** dominate each other.

        minimize
            Per-axis minimization flags.
        """

        from calm.viz.pareto import pareto_front_2d as _pareto_front_2d

        return _pareto_front_2d(
            self.prototypes,
            x=x,
            y=y,
            ids=ids,
            strict=strict,
            minimize=minimize,
        )

    @property
    def pareto(self) -> list[InterfacePrototype]:
        """Return retained members of the authoritative strain--size front.

        Search-produced prototypes carry membership computed over the complete
        admitted canonical population before ranking and truncation. Lightweight
        manually constructed results without that provenance are classified over
        their current population using the same named policy.
        """

        if self.prototypes and all(
            (
                item.get("pareto_policy") == STRAIN_SIZE_PARETO_POLICY
                and item.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
                and item.get("pareto_population_scope")
                == STRAIN_SIZE_PARETO_POPULATION_SCOPE
                and item.get("pareto_d_cell_key") is not None
                and item.get("is_pareto") is not None
            )
            if isinstance(item, dict)
            else (
                getattr(item, "pareto_policy", None) == STRAIN_SIZE_PARETO_POLICY
                and getattr(item, "pareto_policy_version", None)
                == STRAIN_SIZE_PARETO_VERSION
                and getattr(item, "pareto_population_scope", None)
                == STRAIN_SIZE_PARETO_POPULATION_SCOPE
                and getattr(item, "pareto_d_cell_key", None) is not None
            )
            for item in self.prototypes
        ):
            return [
                item
                for item in self.prototypes
                if bool(
                    item.get("is_pareto", False)
                    if isinstance(item, dict)
                    else getattr(item, "is_pareto", False)
                )
            ]

        result = strain_size_pareto(
            self.prototypes,
            atom_count="n_atoms_interface",
            d_cell="d_cell",
            ids="prototype_uid",
            policy="current_result_strain_size_pareto",
            population_scope="current_result_population",
        )
        return [self.prototypes[index] for index in result.front_idx]

    def group_numerical_variants(
        self,
        *,
        contact_side_A: str = "top",
        contact_side_B: str = "bottom",
        z_window_angstrom: float = 0.25,
        metric_quantization_step_angstrom2: float = 1e-10,
        xy_decimals: int = 8,
        z_decimals: int = 3,
    ):
        """Group prototypes by versioned numerical metric and motif bins.

        This post-processing relation is deliberately weaker than exact
        candidate identity and crystallographic equivalence.  Returned keys
        record their units, quantization, quotient actions, version, and
        collision limitations.
        """
        from calm.interface.matching.grouping import (
            group_prototypes_by_numerical_metric_then_contact_motif,
        )

        return group_prototypes_by_numerical_metric_then_contact_motif(
            self.prototypes,
            contact_side_A=contact_side_A,
            contact_side_B=contact_side_B,
            z_window_angstrom=z_window_angstrom,
            metric_quantization_step_angstrom2=(metric_quantization_step_angstrom2),
            xy_decimals=xy_decimals,
            z_decimals=z_decimals,
        )

    def signature(self, *, max_prototypes: int | None = None) -> dict[str, Any]:
        """Return a stable, JSON-serializable signature for regression testing.

        The signature is intentionally lightweight (no numpy arrays) and focuses
        on the information needed to reproduce downstream decisions.
        """

        # Keep the signature small/robust: store per-prototype fingerprints
        # rather than embedding the full prototype structures.
        protos = self.prototypes
        if max_prototypes is not None:
            protos = protos[: int(max_prototypes)]

        return {
            "slab_a_uid": str(self.slab_a_uid),
            "slab_b_uid": str(self.slab_b_uid),
            "config": (
                self.config.to_dict()
                if hasattr(self.config, "to_dict")
                else getattr(self.config, "__dict__", self.config)
            ),
            "surface_symmetry_status": (
                "validated"
                if self.surface_symmetry_a is not None
                else "legacy_unrecorded"
            ),
            "surface_symmetry_a": (
                None
                if self.surface_symmetry_a is None
                else self.surface_symmetry_a.to_dict()
            ),
            "surface_symmetry_b": (
                None
                if self.surface_symmetry_b is None
                else self.surface_symmetry_b.to_dict()
            ),
            "n_prototypes": len(self.prototypes),
            "pareto_policy": self.pareto_policy,
            "pareto_policy_version": self.pareto_policy_version,
            "pareto_population_scope": self.pareto_population_scope,
            "pareto_population_size": self.pareto_population_size,
            "pareto_front_uids": list(self.pareto_front_uids),
            "prototype_fingerprints": [
                (p.fingerprint() if hasattr(p, "fingerprint") else repr(p))
                for p in protos
            ],
        }

    def fingerprint(self, *, max_prototypes: int | None = None) -> str:
        """Return a deterministic SHA-256 fingerprint of :meth:`signature`."""

        return fingerprint_json(self.signature(max_prototypes=max_prototypes))

    def to_dict(
        self,
        *,
        max_prototypes: int | None = None,
        include_prototypes: bool = True,
        include_config: bool = True,
        include_fingerprints: bool = False,
        include_enumeration_audit: bool = False,
    ) -> dict[str, Any]:
        """Return a JSON-serializable dictionary suitable for writing to disk."""

        out: dict[str, Any] = {
            "slab_a_uid": str(self.slab_a_uid),
            "slab_b_uid": str(self.slab_b_uid),
            "surface_symmetry_status": (
                "validated"
                if self.surface_symmetry_a is not None
                else "legacy_unrecorded"
            ),
            "surface_symmetry_a": (
                None
                if self.surface_symmetry_a is None
                else self.surface_symmetry_a.to_dict()
            ),
            "surface_symmetry_b": (
                None
                if self.surface_symmetry_b is None
                else self.surface_symmetry_b.to_dict()
            ),
            "pareto_policy": self.pareto_policy,
            "pareto_policy_version": self.pareto_policy_version,
            "pareto_population_scope": self.pareto_population_scope,
            "pareto_population_size": self.pareto_population_size,
            "pareto_front_uids": list(self.pareto_front_uids),
        }

        if include_config:
            out["config"] = (
                self.config.to_dict()
                if hasattr(self.config, "to_dict")
                else getattr(self.config, "__dict__", self.config)
            )

        if include_fingerprints:
            out["fingerprint"] = self.fingerprint(max_prototypes=max_prototypes)

        if include_enumeration_audit and self.enumeration_audit is not None:
            out["enumeration_audit"] = self.enumeration_audit.to_dict(cumulative=False)

        if include_prototypes:
            protos = self.prototypes
            if max_prototypes is not None:
                protos = protos[: int(max_prototypes)]

            # User-facing ranks are 1-based.
            proto_dicts: list[dict[str, Any]] = []
            for i, p in enumerate(protos, start=1):
                if hasattr(p, "to_dict"):
                    # Prefer the prototype's own stable façade.
                    d = p.to_dict(rank=i, include_fingerprints=include_fingerprints)  # type: ignore[call-arg]
                else:
                    d = {"repr": repr(p), "rank": i}
                d.setdefault("rank", i)
                proto_dicts.append(d)

            out["prototypes"] = proto_dicts

        return out


@dataclass(frozen=True)
class StrainState:
    """Incremental interface-matching strain for one prototype and model.

    These matrices exclude physical slab-construction deformation and any later
    cell-relaxation deformation. Total deformation is carried by the versioned
    interface deformation-accounting payload.
    """

    prototype_uid: str
    strain_model_uid: str

    F_tot: np.ndarray
    F_A: np.ndarray
    F_B: np.ndarray

    E_A_rms: float
    E_B_rms: float

    # Optional extended diagnostics (kept opaque in Stage B)
    raw: Any = None

    def signature(self) -> dict[str, Any]:
        """Return a deterministic, JSON-serializable signature."""

        return {
            "prototype_uid": str(self.prototype_uid),
            "strain_model_uid": str(self.strain_model_uid),
            "deformation_scope": INCREMENTAL_INTERFACE_MATCHING_SCOPE,
            "F_tot": self.F_tot,
            "F_A": self.F_A,
            "F_B": self.F_B,
            "E_A_rms": float(self.E_A_rms),
            "E_B_rms": float(self.E_B_rms),
        }

    def fingerprint(self) -> str:
        """Stable SHA-256 fingerprint for regression testing."""

        return fingerprint_json(self.signature())

    def to_dict(
        self,
        *,
        include_matrices: bool = True,
        include_fingerprints: bool = False,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "prototype_uid": str(self.prototype_uid),
            "strain_model_uid": str(self.strain_model_uid),
            "deformation_scope": INCREMENTAL_INTERFACE_MATCHING_SCOPE,
            "E_A_rms": float(self.E_A_rms),
            "E_B_rms": float(self.E_B_rms),
        }

        if include_matrices:
            out.update(
                {
                    "F_tot": self.F_tot.tolist(),
                    "F_A": self.F_A.tolist(),
                    "F_B": self.F_B.tolist(),
                }
            )

        if include_fingerprints:
            out["fingerprint"] = self.fingerprint()

        return out


@dataclass(frozen=True)
class EnergyResult:
    """Output of an interface energy evaluation.

    This result is used both by the workspace persistence layer (persisted energy evaluations)
    and by lightweight workflow helpers/tests.

    Strain/reference provenance
    --------------------------
    The following optional provenance fields capture how strained-bulk references
    were constructed and are included in ``to_dict()`` and ``signature()`` when
    present:

    - ``F_A_slab`` / ``F_B_slab``: interface-matching deformation gradients
      in the post-gauge slab frames (3×3 arrays)
    - ``F_*_construction_slab`` and ``F_*_total_slab``: pre-existing slab
      construction deformation and its composition with interface strain
    - ``F_A_conv`` / ``F_B_conv``: interface-only gradients mapped to the
      conventional bulk frames
    - ``F_*_construction_conv`` and ``F_*_total_conv``: construction and total
      deformation in the conventional bulk frames
    - ``slab_deformation_accounting_policy`` and
      ``slab_deformation_accounting_version``: versioned composition semantics
    - ``strained_bulk_cell_A_3x3`` / ``strained_bulk_cell_B_3x3``: strained cell
      matrices (columns)
    - ``strained_bulk_reference_mode``: string indicating mode (default
      "unrelaxed_scaled_positions")
    - ``bulk_reference_relaxed``: boolean (default False)
    - ``gamma_reference_convention``: short description of subtraction convention
      (default "strained_unrelaxed_bulk_subtraction")
    """

    # Canonical identifiers (used by workspace persistence).
    interface_uid: str = ""
    calc_uid: str = ""
    econf_uid: str = ""
    energy_uid: str = ""

    # Canonical metrics (used internally and for persistence).
    gamma_eV_per_A2: float = float("nan")
    gamma_J_per_m2: float = float("nan")

    # Additional physical/contextual quantities.
    area_A2: float = float("nan")
    E_int_eV: float = float("nan")
    n_fu_slab_A: int = 0
    n_fu_slab_B: int = 0
    mu_bulk_A_eV_per_fu: float = float("nan")
    mu_bulk_B_eV_per_fu: float = float("nan")
    formula_A: str = ""
    formula_B: str = ""
    # Extended provenance fields for strained-bulk reference (optional)
    F_A_slab: Any | None = None
    F_B_slab: Any | None = None
    F_A_construction_slab: Any | None = None
    F_B_construction_slab: Any | None = None
    F_A_total_slab: Any | None = None
    F_B_total_slab: Any | None = None
    F_A_conv: Any | None = None
    F_B_conv: Any | None = None
    F_A_construction_conv: Any | None = None
    F_B_construction_conv: Any | None = None
    F_A_total_conv: Any | None = None
    F_B_total_conv: Any | None = None
    slab_deformation_accounting_policy: str | None = None
    slab_deformation_accounting_version: int | None = None
    strained_bulk_cell_A_3x3: Any | None = None
    strained_bulk_cell_B_3x3: Any | None = None
    strained_bulk_reference_mode: str = "unrelaxed_scaled_positions"
    bulk_reference_relaxed: bool = False
    bulk_reference_calculation_id_A: Any | None = None
    bulk_reference_calculation_id_B: Any | None = None
    gamma_reference_convention: str = "strained_unrelaxed_bulk_subtraction"
    n_interfaces: int = 2
    thermodynamic_formula: str = "interface_excess_strained_bulk"
    thermodynamic_quantity: str = "interface_excess_energy"

    # EnergyConfig serialized as a dict (kept generic to remain stable across
    # light API adjustments).
    config: dict[str, Any] = field(default_factory=dict, repr=False)

    def fingerprint(self) -> str:
        return fingerprint_json(self.signature())

    def signature(self) -> dict[str, Any]:
        return {
            "interface_uid": str(self.interface_uid),
            "calc_uid": str(self.calc_uid),
            "econf_uid": str(self.econf_uid),
            "gamma_eV_per_A2": float(self.gamma_eV_per_A2),
            "gamma_J_per_m2": float(self.gamma_J_per_m2),
            "area_A2": float(self.area_A2),
            "E_int_eV": float(self.E_int_eV),
            "n_fu_slab_A": int(self.n_fu_slab_A),
            "n_fu_slab_B": int(self.n_fu_slab_B),
            "mu_bulk_A_eV_per_fu": float(self.mu_bulk_A_eV_per_fu),
            "mu_bulk_B_eV_per_fu": float(self.mu_bulk_B_eV_per_fu),
            "formula_A": str(self.formula_A),
            "formula_B": str(self.formula_B),
            # Include extended provenance when present
            "F_A_slab": getattr(self, "F_A_slab", None),
            "F_B_slab": getattr(self, "F_B_slab", None),
            "F_A_construction_slab": getattr(
                self, "F_A_construction_slab", None
            ),
            "F_B_construction_slab": getattr(
                self, "F_B_construction_slab", None
            ),
            "F_A_total_slab": getattr(self, "F_A_total_slab", None),
            "F_B_total_slab": getattr(self, "F_B_total_slab", None),
            "F_A_conv": getattr(self, "F_A_conv", None),
            "F_B_conv": getattr(self, "F_B_conv", None),
            "F_A_construction_conv": getattr(
                self, "F_A_construction_conv", None
            ),
            "F_B_construction_conv": getattr(
                self, "F_B_construction_conv", None
            ),
            "F_A_total_conv": getattr(self, "F_A_total_conv", None),
            "F_B_total_conv": getattr(self, "F_B_total_conv", None),
            "slab_deformation_accounting_policy": getattr(
                self, "slab_deformation_accounting_policy", None
            ),
            "slab_deformation_accounting_version": getattr(
                self, "slab_deformation_accounting_version", None
            ),
            "strained_bulk_cell_A_3x3": getattr(self, "strained_bulk_cell_A_3x3", None),
            "strained_bulk_cell_B_3x3": getattr(self, "strained_bulk_cell_B_3x3", None),
            "strained_bulk_reference_mode": getattr(
                self, "strained_bulk_reference_mode", None
            ),
            "bulk_reference_relaxed": getattr(self, "bulk_reference_relaxed", None),
            "gamma_reference_convention": getattr(
                self, "gamma_reference_convention", None
            ),
            "n_interfaces": int(getattr(self, "n_interfaces", 2)),
            "thermodynamic_formula": getattr(self, "thermodynamic_formula", None),
            "thermodynamic_quantity": getattr(self, "thermodynamic_quantity", None),
        }

    def to_dict(self, *, include_config: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "energy_uid": str(self.energy_uid),
            "interface_uid": str(self.interface_uid),
            "calc_uid": str(self.calc_uid),
            "econf_uid": str(self.econf_uid),
            "gamma_eV_per_A2": float(self.gamma_eV_per_A2),
            "gamma_J_per_m2": float(self.gamma_J_per_m2),
            "area_A2": float(self.area_A2),
            "E_int_eV": float(self.E_int_eV),
            "n_fu_slab_A": int(self.n_fu_slab_A),
            "n_fu_slab_B": int(self.n_fu_slab_B),
            "mu_bulk_A_eV_per_fu": float(self.mu_bulk_A_eV_per_fu),
            "mu_bulk_B_eV_per_fu": float(self.mu_bulk_B_eV_per_fu),
            "formula_A": str(self.formula_A),
            "formula_B": str(self.formula_B),
        }
        # Extended provenance (explicit fields for reproducibility)
        out.update(
            {
                "F_A_slab": getattr(self, "F_A_slab", None),
                "F_B_slab": getattr(self, "F_B_slab", None),
                "F_A_construction_slab": getattr(
                    self, "F_A_construction_slab", None
                ),
                "F_B_construction_slab": getattr(
                    self, "F_B_construction_slab", None
                ),
                "F_A_total_slab": getattr(self, "F_A_total_slab", None),
                "F_B_total_slab": getattr(self, "F_B_total_slab", None),
                "F_A_conv": getattr(self, "F_A_conv", None),
                "F_B_conv": getattr(self, "F_B_conv", None),
                "F_A_construction_conv": getattr(
                    self, "F_A_construction_conv", None
                ),
                "F_B_construction_conv": getattr(
                    self, "F_B_construction_conv", None
                ),
                "F_A_total_conv": getattr(self, "F_A_total_conv", None),
                "F_B_total_conv": getattr(self, "F_B_total_conv", None),
                "slab_deformation_accounting_policy": getattr(
                    self, "slab_deformation_accounting_policy", None
                ),
                "slab_deformation_accounting_version": getattr(
                    self, "slab_deformation_accounting_version", None
                ),
                "strained_bulk_cell_A_3x3": getattr(
                    self, "strained_bulk_cell_A_3x3", None
                ),
                "strained_bulk_cell_B_3x3": getattr(
                    self, "strained_bulk_cell_B_3x3", None
                ),
                "strained_bulk_reference_mode": getattr(
                    self, "strained_bulk_reference_mode", None
                ),
                "bulk_reference_relaxed": getattr(self, "bulk_reference_relaxed", None),
                "bulk_reference_calculation_id_A": getattr(
                    self, "bulk_reference_calculation_id_A", None
                ),
                "bulk_reference_calculation_id_B": getattr(
                    self, "bulk_reference_calculation_id_B", None
                ),
                "gamma_reference_convention": getattr(
                    self, "gamma_reference_convention", None
                ),
                "n_interfaces": int(getattr(self, "n_interfaces", 2)),
                "thermodynamic_formula": getattr(self, "thermodynamic_formula", None),
                "thermodynamic_quantity": getattr(self, "thermodynamic_quantity", None),
            }
        )
        if include_config:
            out["config"] = self.config
        return out
