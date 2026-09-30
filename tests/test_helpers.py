"""Test helper utilities.

Provides common fixtures and helpers for workspace tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from calm.project.domain.models import Bulk
    from calm.project.runtime.workspace import Workspace


def make_test_bulk(
    ws: "Workspace",
    symbol: str = "Al",
    structure: str = "fcc",
    a: float = 4.05,
    with_calculator: bool = True,
) -> "Bulk":
    """Create a bulk with a real atomic structure for testing.

    Parameters
    ----------
    ws : Workspace
        Workspace instance.
    symbol : str
        Chemical symbol (e.g., "Al", "Cu", "Fe").
    structure : str
        Crystal structure ("fcc", "bcc", "hcp", "diamond", etc.).
    a : float
        Lattice parameter in Angstroms.
    with_calculator : bool, optional
        If True, attach a test calculator (EMT) for energy computations.
        Required for tests that run followups (strain scan, registry search).
        Default is True.

    Returns
    -------
    Bulk
        Bulk record with atomic structure data.

    Examples
    --------
    >>> ws = open_workspace(root=tmp_path)
    >>> bulk_al = make_test_bulk(ws, "Al", "fcc", 4.05)
    >>> bulk_cu = make_test_bulk(ws, "Cu", "fcc", 3.61)

    Notes
    -----
    When with_calculator=True, attaches ASE EMT calculator for test energy
    computations. This is required for followup operations (strain scans,
    registry searches) which need real calculator provenance.
    """
    from ase.build import bulk as ase_bulk

    atoms = ase_bulk(symbol, structure, a=a)

    # Attach calculator if requested (required for followup operations)
    if with_calculator:
        from calm.calculators.spec import CalculatorSpec

        calc_spec = CalculatorSpec(family="ase", model="EMT")
        return ws.add_bulk(structure=atoms, label=symbol, optimized_with=calc_spec)
    else:
        return ws.add_bulk(structure=atoms, label=symbol)


def make_test_slabs(
    ws: "Workspace", bulk_id: str, millers: list[tuple[int, int, int]]
) -> list:
    """Build slabs from a bulk with real atomic structures.

    Parameters
    ----------
    ws : Workspace
        Workspace instance.
    bulk_id : str
        Bulk identifier (short ID).
    millers : list[tuple[int, int, int]]
        List of Miller indices.

    Returns
    -------
    list[Slab]
        List of slab records with atomic structure data.

    Examples
    --------
    >>> bulk = make_test_bulk(ws, "Al")
    >>> slabs = make_test_slabs(ws, bulk.id_short, [(1, 1, 1), (1, 0, 0)])
    >>> assert all(s.atoms is not None for s in slabs)
    """
    return ws.build_slabs(bulk_id, millers=millers)


def coupled_pair_metadata(supercell_a, supercell_b):
    """Return exact coupled identity/provenance for primitive test recipes."""
    import numpy as np

    from calm.interface.model import MatchSourceProvenance2D, PairIdentity2D

    n_a = np.asarray(supercell_a.N_tot, dtype=int)
    n_b = np.asarray(supercell_b.N_tot, dtype=int)
    pair = np.vstack([n_a, n_b])
    index_pair = (
        abs(int(round(np.linalg.det(n_a)))),
        abs(int(round(np.linalg.det(n_b)))),
    )
    identity = PairIdentity2D(
        key_version=1,
        primitive_pair_key=tuple(int(value) for value in pair.ravel()),
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        material_exchange_identified=False,
    )
    provenance = MatchSourceProvenance2D(
        source_count=1,
        minimum_source_indices=index_pair,
        source_index_pairs=(index_pair,),
        repeat_indices=(1,),
        representative_source_H_A=n_a,
        representative_source_H_B=n_b,
        representative_source_N_A=n_a,
        representative_source_N_B=n_b,
        representative_correspondence_U_B=np.eye(2, dtype=int),
        representative_source_pair_matrix=pair,
        representative_source_right_factor=np.eye(2, dtype=int),
    )
    return identity, provenance


def make_test_interface_prototype(
    *,
    prototype_uid: str,
    miller_a: tuple[int, int, int] = (0, 0, 1),
    miller_b: tuple[int, int, int] = (0, 0, 1),
    match_score: float = 0.1,
    n_atoms_interface: int = 1,
    interface_area_A2: float = 1.0,
    slab_a_uid: str = "slab:test:a",
    slab_b_uid: str = "slab:test:b",
):
    """Return a minimal valid primitive coupled-pair prototype for tests."""
    from types import SimpleNamespace

    import numpy as np

    from calm.interface.model import InterfacePrototype, SupercellRecipe2D

    area = float(interface_area_A2)
    if not np.isfinite(area) or area <= 0.0:
        raise ValueError("interface_area_A2 must be positive and finite")
    reduced_basis = np.array([[area, 0.0], [0.0, 1.0]], dtype=float)
    recipe = SupercellRecipe2D(
        k=1,
        N_tot=np.eye(2, dtype=int),
        R_sup=np.eye(2),
        hnf_key_pg=(1, 0, 0, 1),
        cond=max(area, 1.0 / area),
        S_red=reduced_basis,
        G_red=reduced_basis.T @ reduced_basis,
    )
    pair_identity, source_provenance = coupled_pair_metadata(recipe, recipe)
    slab_a = SimpleNamespace(project_slab_uid_full=slab_a_uid)
    slab_b = SimpleNamespace(project_slab_uid_full=slab_b_uid)
    return InterfacePrototype(
        prototype_uid=prototype_uid,
        slab_a_uid=slab_a_uid,
        slab_b_uid=slab_b_uid,
        miller_a=tuple(int(value) for value in miller_a),
        miller_b=tuple(int(value) for value in miller_b),
        supercell_a=recipe,
        supercell_b=recipe,
        match_score=float(match_score),
        d_size=0.0,
        d_cell=0.0,
        d_area=0.0,
        d_shape=0.0,
        rel_da=0.0,
        rel_db=0.0,
        d_gamma_deg=0.0,
        n_atoms_interface=int(n_atoms_interface),
        slab_a=slab_a,
        slab_b=slab_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
    )


@dataclass(frozen=True)
class CapturedReportEvent:
    """One event emitted by the test-only capture reporter."""

    kind: str
    message: str
    meta: dict[str, Any]


class CaptureReporter:
    """Test-only structural reporter that records workflow events."""

    def __init__(self) -> None:
        self.events: list[CapturedReportEvent] = []

    class _Context:
        def __init__(
            self,
            parent: "CaptureReporter",
            label: str,
            meta: dict[str, Any],
            *,
            prefix: str,
        ) -> None:
            self.parent = parent
            self.label = label
            self.meta = meta
            self.prefix = prefix

        def __enter__(self):
            self.parent.events.append(
                CapturedReportEvent(
                    kind=f"{self.prefix}_start",
                    message=self.label,
                    meta=dict(self.meta),
                )
            )
            return self

        def __exit__(self, exc_type, exc, tb):
            kind = f"{self.prefix}_end" if exc_type is None else f"{self.prefix}_fail"
            meta = dict(self.meta)
            if exc_type is not None:
                meta.update({"exc_type": exc_type.__name__, "exc": str(exc)})
            self.parent.events.append(
                CapturedReportEvent(kind=kind, message=self.label, meta=meta)
            )
            return False

    def stage(self, label: str, **meta: Any):
        return self._Context(self, str(label), dict(meta), prefix="stage")

    def section(self, title: str, **meta: Any):
        return self._Context(self, str(title), dict(meta), prefix="section")

    def info(self, message: str, **meta: Any) -> None:
        self.events.append(CapturedReportEvent("info", str(message), dict(meta)))

    def warn(self, message: str, **meta: Any) -> None:
        self.events.append(CapturedReportEvent("warn", str(message), dict(meta)))

    def mapping(self, mapping: dict[str, Any], *, title: str | None = None) -> None:
        message = "\n".join(f"  {key}: {value}" for key, value in mapping.items())
        self.events.append(
            CapturedReportEvent(
                "mapping",
                message or "(no items)",
                {"title": title} if title else {},
            )
        )

    def paths(self, paths, *, title: str | None = None) -> None:
        message = "\n".join(f"  - {path}" for path in paths)
        self.events.append(
            CapturedReportEvent(
                "paths",
                message or "(no paths)",
                {"title": title} if title else {},
            )
        )

    def summary(self, message: str, **meta: Any) -> None:
        self.events.append(CapturedReportEvent("summary", str(message), dict(meta)))


def make_current_strain_result_payload(
    *,
    alpha: float = 0.25,
    value: float = 0.1,
    metric: str = "potential_energy_density_eV_per_A2",
) -> dict[str, Any]:
    """Return one dependency-light exact-current strain result payload."""

    from calm.project.domain.contracts.refinement_result import (
        make_strain_partition_result_payload,
    )
    from calm.calculators.spec import CalculatorSpec
    from calm.interface.energy.contract import EV_PER_A2_TO_J_PER_M2

    calculator = CalculatorSpec(family="test", model="strain-result-fixture")
    total_principal = (-0.02, 0.04)
    side_a_principal = sorted(float(alpha) * item for item in total_principal)
    side_b_principal = sorted(-(1.0 - float(alpha)) * item for item in total_principal)
    side_a_distance = 2.0 * sum(item * item for item in side_a_principal) ** 0.5
    side_b_distance = 2.0 * sum(item * item for item in side_b_principal) ** 0.5
    point = {
        "alpha": float(alpha),
        "side_a_principal_log_strains": side_a_principal,
        "side_b_principal_log_strains": side_b_principal,
        "side_a_max_abs_principal_log_strain": max(
            abs(item) for item in side_a_principal
        ),
        "side_b_max_abs_principal_log_strain": max(
            abs(item) for item in side_b_principal
        ),
        "side_a_airm_distance": side_a_distance,
        "side_b_airm_distance": side_b_distance,
        "potential_energy_eV": float(value) * 10.0,
        "area_A2": 10.0,
        "interface_area_A2": 10.0,
        "potential_energy_density_eV_per_A2": float(value),
        "gamma_eV_per_A2": float(value),
        "gamma_J_per_m2": float(value) * EV_PER_A2_TO_J_PER_M2,
        "n_fu_slab_A": 1,
        "n_fu_slab_B": 1,
        "mu_bulk_A_eV_per_fu": -1.0,
        "mu_bulk_B_eV_per_fu": -1.0,
        "energy_reference": "strained_bulk",
    }
    return make_strain_partition_result_payload(
        points=[point],
        target_metric=metric,
        target_alpha=alpha,
        target_value=value,
        calculator=calculator.to_dict(),
        calculator_fingerprint=calculator.fingerprint(),
    )


def make_current_registry_result_payload(
    *,
    n_steps: int = 2,
    score: float = -0.5,
    z_padding: float = 1.5,
    vacuum: float | None = None,
) -> dict[str, Any]:
    """Return one dependency-light exact-current registry result payload."""

    from calm.interface.refinement.contract import (
        REGISTRY_SEED_DERIVATION,
        REGISTRY_SEED_DERIVATION_VERSION,
    )
    from calm.project.domain.contracts.refinement_result import (
        make_registry_search_result_payload,
    )
    from calm.calculators.spec import CalculatorSpec
    from calm.interface.refinement.registry import (
        PERSISTED_REGISTRY_IMPLEMENTATION,
        PERSISTED_REGISTRY_OBJECTIVE,
        PERSISTED_REGISTRY_SCORE_UNITS,
        PERSISTED_REGISTRY_TEMPERATURE,
        monte_carlo_registry_search,
    )

    calculator = CalculatorSpec(family="test", model="registry-result-fixture")
    result = monte_carlo_registry_search(
        lambda _translation: float(score),
        x0=(0.0, 0.0),
        n_steps=n_steps,
        seed=7,
        keep_trace=True,
        temperature=PERSISTED_REGISTRY_TEMPERATURE,
        score_units=PERSISTED_REGISTRY_SCORE_UNITS,
    )
    provenance = dict(result.metadata)
    provenance.update(
        {
            "implementation": PERSISTED_REGISTRY_IMPLEMENTATION,
            "alpha": 0.5,
            "initial_translation": [0.0, 0.0],
            "fixed_z_padding": float(z_padding),
            "fixed_vacuum_padding": vacuum,
            "z_search_enabled": False,
            "requested_seed": 7,
            "seed_derivation": REGISTRY_SEED_DERIVATION,
            "seed_derivation_version": REGISTRY_SEED_DERIVATION_VERSION,
        }
    )
    return make_registry_search_result_payload(
        registry_shift_frac_a=result.translation,
        z_padding=z_padding,
        vacuum=vacuum,
        objective=PERSISTED_REGISTRY_OBJECTIVE,
        objective_units=PERSISTED_REGISTRY_SCORE_UNITS,
        score=result.score,
        n_steps=result.n_steps,
        n_accepted=result.n_accepted,
        trace=result.trace,
        proposal_trace=[item.to_dict() for item in result.proposal_trace],
        calculator=calculator.to_dict(),
        calculator_fingerprint=calculator.fingerprint(),
        provenance=provenance,
    )
