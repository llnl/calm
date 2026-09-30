"""calm.interface.pipeline

v2 workflow pipeline (Stage B).

Public functions
----------------
- find_prototypes
- compute_strain_state
- build_interface
- compute_interfacial_energy

This module intentionally:
- keeps I/O out of core computation
- avoids optional dependencies (e.g., matplotlib)
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Sequence

# Ensure these names exist for the optional-dependency fallbacks so linters
# do not report undefined-name when the except: blocks are analyzed statically.
_missing_matching: Exception | None = None
_missing_strain: Exception | None = None

import numpy as np  # noqa: E402

from calm.slab.oriented.cell_contract import (  # noqa: E402
    INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY,
    canonical_interface_deformation_accounting,
)

from calm.analysis.pareto import (  # noqa: E402
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    strain_size_pareto,
)
from calm.calculators.exceptions import (  # noqa: E402
    CalculatorError,
    CalculatorExecutionError,
)
from calm.calculators.identity import get_calculator_uid  # noqa: E402

from calm.keys.uid import (  # noqa: E402
    build_uid,
    energy_config_uid,
    energy_uid,
    material_uid_from_conv_atoms,
    prototype_uid_v3,
    slab_spec_uid,
    slab_uid as slab_uid_fn,
    strain_model_uid,
    strained_uid as strained_uid_fn,
)

try:  # keep this module importable in lightweight/no-ASE environments
    from calm.slab.slab import Slab
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard

    class Slab:  # type: ignore[no-redef]
        pass


from calm.interface.config import (  # noqa: E402
    EnergyConfig,
    InterfaceBuildConfig,
    PrototypeSearchConfig,
    StrainModel,
)

try:  # keep module importable in lightweight/no-spglib environments
    from calm.interface.matching.search import search_primitive_match_classes
except ModuleNotFoundError as _missing_matching:  # pragma: no cover

    def search_primitive_match_classes(*args, **kwargs):
        raise ImportError(
            "CALM interface matching requires optional atomistic dependencies "
            "such as ASE and Spglib."
        ) from _missing_matching


from calm.interface.matching._types import PrimitiveMatchClass2D  # noqa: E402
from calm.interface.model import (  # noqa: E402
    Interface,
    InterfacePrototype,
    MatchSourceProvenance2D,
    PairIdentity2D,
    SupercellRecipe2D,
)

from calm.interface.results import EnergyResult, PrototypeSearchResult, StrainState  # noqa: E402

try:
    from calm.interface.refinement.strain import compute_strain_2d
except ModuleNotFoundError as _missing_strain:  # pragma: no cover

    def compute_strain_2d(*args, **kwargs):
        raise ImportError(
            "compute_strain_2d requires CALM atomistic/symmetry dependencies."
        ) from _missing_strain


from calm.interface.building._kernel import (  # noqa: E402
    _embed_2x2_in_3x3,
    build_interface_atoms,
    quantize_translation_frac,
)


def _slab_miller(slab: Any) -> tuple[int, int, int]:
    """Return Miller indices from an in-memory or persisted slab record."""

    miller = getattr(slab, "hkl", None)
    if miller is None:
        miller = getattr(slab, "miller", None)
    if miller is None:
        raise AttributeError("slab must define hkl or miller")
    values = tuple(int(value) for value in miller)
    if len(values) != 3:
        raise ValueError("slab Miller indices must contain three integers")
    return values


def _slab_uid(slab: Any) -> str:
    """Return an authoritative persisted UID or derive one for a CALM slab."""

    for attribute in (
        "project_slab_uid_full",
        "uid_full",
        "slab_uid",
        "uid",
    ):
        try:
            value = getattr(slab, attribute)
        except (AttributeError, TypeError, ValueError):
            continue
        if isinstance(value, str) and value:
            return value

    bulk = getattr(slab, "bulk", None)
    spec = getattr(slab, "spec", None)
    if bulk is None or spec is None:
        raise AttributeError(
            "slab must define an authoritative UID or a CALM bulk/spec pair"
        )
    mat_uid = material_uid_from_conv_atoms(
        bulk.conv,
        symprec=getattr(bulk, "symprec", 1e-5),
        no_idealize=getattr(bulk, "no_idealize", False),
    )
    ss_uid = slab_spec_uid(spec)
    return slab_uid_fn(
        material_uid=mat_uid,
        miller=_slab_miller(slab),
        slab_spec_uid=ss_uid,
    )


def find_prototypes(
    slab_a: Slab,
    slab_b: Slab,
    config: PrototypeSearchConfig | None = None,
) -> PrototypeSearchResult:
    """Search the complete primitive coupled-pair population.

    Pareto classification is computed over the complete admitted class
    population. ``max_results`` is applied only after that classification and
    deterministic ranking.
    """

    if config is None:
        config = PrototypeSearchConfig()

    slab_a_uid = _slab_uid(slab_a)
    slab_b_uid = _slab_uid(slab_b)
    search = search_primitive_match_classes(slab_a, slab_b, config)

    admitted_prototypes = [
        _prototype_from_primitive_match_class(
            match_class,
            slab_a=slab_a,
            slab_b=slab_b,
            slab_a_uid=slab_a_uid,
            slab_b_uid=slab_b_uid,
        )
        for match_class in search.match_classes
    ]
    annotated, pareto_front_uids = _annotate_authoritative_pareto(admitted_prototypes)
    # The coupled matcher already defines the deterministic total ranking.
    # Reapply that exact rank after Pareto annotation so every entry point keeps
    # one ordering without independently rescoring the primitive classes.
    authoritative_rank = {
        match_class.pair_key: index
        for index, match_class in enumerate(search.match_classes)
    }
    ranked = sorted(
        annotated,
        key=lambda prototype: authoritative_rank[
            tuple(prototype.pair_identity.primitive_pair_key)
        ],
    )
    retained = _retain_ranked_prototypes(
        ranked,
        max_results=config.max_results,
    )

    return PrototypeSearchResult(
        slab_a_uid=slab_a_uid,
        slab_b_uid=slab_b_uid,
        config=config,
        prototypes=retained,
        enumeration_audit=search.enumeration_audit,
        surface_symmetry_a=search.surface_symmetry_a,
        surface_symmetry_b=search.surface_symmetry_b,
        pareto_policy=STRAIN_SIZE_PARETO_POLICY,
        pareto_policy_version=STRAIN_SIZE_PARETO_VERSION,
        pareto_population_scope=STRAIN_SIZE_PARETO_POPULATION_SCOPE,
        pareto_population_size=len(admitted_prototypes),
        pareto_front_uids=pareto_front_uids,
    )


def _annotate_authoritative_pareto(
    prototypes: Sequence[InterfacePrototype],
) -> tuple[list[InterfacePrototype], tuple[str, ...]]:
    """Attach full-population ``strain_size_pareto`` provenance."""

    result = strain_size_pareto(
        prototypes,
        atom_count="n_atoms_interface",
        d_cell="d_cell",
        ids="prototype_uid",
    )
    rank_by_index = {index: rank for rank, index in enumerate(result.front_idx)}
    annotated = [
        replace(
            prototype,
            is_pareto=bool(result.mask[index]),
            pareto_rank=rank_by_index.get(index),
            pareto_policy=result.policy,
            pareto_policy_version=result.version,
            pareto_population_scope=result.population_scope,
            pareto_population_size=result.population_size,
            pareto_d_cell_key=result.d_cell_keys[index],
        )
        for index, prototype in enumerate(prototypes)
    ]
    return annotated, result.front_ids


def _retain_ranked_prototypes(
    ranked: Sequence[InterfacePrototype],
    *,
    max_results: int | None,
) -> list[InterfacePrototype]:
    """Apply the output limit without preferring dominated points to front points.

    The full-population Pareto relation has already been computed. When the
    limit can contain the complete front, every front member is retained and
    remaining slots are filled in weighted-rank order. If the front itself is
    larger than the limit, its weighted-rank prefix is retained. Returned
    records preserve the weighted ordering of the selected set.
    """

    records = list(ranked)
    if max_results is None:
        return records
    limit = max(0, int(max_results))
    if len(records) <= limit:
        return records
    if limit == 0:
        return []

    front = [item for item in records if item.is_pareto]
    if len(front) >= limit:
        selected_uids = {item.prototype_uid for item in front[:limit]}
    else:
        selected_uids = {item.prototype_uid for item in front}
        for item in records:
            if item.prototype_uid in selected_uids:
                continue
            selected_uids.add(item.prototype_uid)
            if len(selected_uids) == limit:
                break
    return [item for item in records if item.prototype_uid in selected_uids]


def _determinant_2d_exact(matrix: np.ndarray) -> int:
    array = np.asarray(matrix)
    return int(array[0, 0]) * int(array[1, 1]) - int(array[0, 1]) * int(array[1, 0])


def _inverse_unimodular_2d(matrix: np.ndarray) -> np.ndarray:
    array = np.asarray(matrix, dtype=int)
    determinant = _determinant_2d_exact(array)
    if abs(determinant) != 1:
        raise ValueError("Expected a unimodular 2x2 matrix")
    inverse = determinant * np.array(
        [[array[1, 1], -array[0, 1]], [-array[1, 0], array[0, 0]]],
        dtype=int,
    )
    if not np.array_equal(array @ inverse, np.eye(2, dtype=int)):
        raise RuntimeError("Exact unimodular inversion failed")
    return inverse


def _primitive_recipe_from_match_class(
    match_class: PrimitiveMatchClass2D,
    *,
    slab: Slab,
    side: str,
) -> SupercellRecipe2D:
    candidate = match_class.representative
    if side == "A":
        integer_map = candidate.build_N_A
        rotation = candidate.build_R_A
        source_key = candidate.source_provenance.source_orbit_key_A
    elif side == "B":
        integer_map = candidate.build_N_B
        rotation = candidate.build_R_B
        source_key = candidate.source_provenance.source_orbit_key_B
    else:
        raise ValueError("side must be 'A' or 'B'")

    cell_columns = np.asarray(slab.atoms.cell.array, dtype=float).T
    integer_3d = _embed_2x2_in_3x3(integer_map, dtype="int")
    rotation_3d = _embed_2x2_in_3x3(rotation, dtype="float")
    physical_3d = rotation_3d @ cell_columns @ integer_3d
    physical_2d = np.asarray(physical_3d[:2, :2], dtype=float)
    gram = physical_2d.T @ physical_2d
    determinant = abs(_determinant_2d_exact(integer_map))
    return SupercellRecipe2D(
        k=determinant,
        N_tot=np.asarray(integer_map, dtype=int),
        R_sup=np.asarray(rotation, dtype=float),
        hnf_key_pg=source_key,
        cond=float(np.linalg.cond(physical_2d)),
        S_red=physical_2d,
        G_red=gram,
        gauge_orientation=(
            "proper" if float(np.linalg.det(rotation)) > 0.0 else "reflection_allowed"
        ),
    )


def _prototype_from_primitive_match_class(
    match_class: PrimitiveMatchClass2D,
    *,
    prototype_uid: str | None = None,
    slab_a: Slab,
    slab_b: Slab,
    slab_a_uid: str,
    slab_b_uid: str,
) -> InterfacePrototype:
    """Project one coupled-v2 match class into a build-ready prototype model."""

    candidate = match_class.representative
    policy = candidate.pair_identity_policy
    internal_provenance = candidate.source_provenance
    build_inverse = _inverse_unimodular_2d(candidate.build_common_right_transform)
    build_to_source = build_inverse @ internal_provenance.source_right_factor
    source_pairs = tuple(sorted(match_class.source_index_pairs))
    minimum_pair = min(source_pairs, key=lambda pair: (max(pair), pair))
    pair_identity = PairIdentity2D(
        key_version=policy.key_version,
        primitive_pair_key=match_class.pair_key,
        pair_symmetry_policy=policy.pair_symmetry,
        correspondence_orientation=policy.correspondence_orientation,
        material_exchange_identified=policy.identify_material_exchange,
    )
    if prototype_uid is None:
        prototype_uid = prototype_uid_v3(
            slab_uid_a=slab_a_uid,
            slab_uid_b=slab_b_uid,
            primitive_pair_key=pair_identity.primitive_pair_key,
            pair_key_version=pair_identity.key_version,
            pair_symmetry_policy=pair_identity.pair_symmetry_policy,
            correspondence_orientation=(pair_identity.correspondence_orientation),
            material_exchange_identified=(pair_identity.material_exchange_identified),
        )
    source_provenance = MatchSourceProvenance2D(
        source_count=match_class.source_count,
        minimum_source_indices=minimum_pair,
        source_index_pairs=source_pairs,
        repeat_indices=tuple(sorted(match_class.repeat_indices)),
        representative_source_H_A=internal_provenance.source_H_A,
        representative_source_H_B=internal_provenance.source_H_B,
        representative_source_N_A=internal_provenance.source_N_A,
        representative_source_N_B=internal_provenance.source_N_B,
        representative_correspondence_U_B=(internal_provenance.correspondence_U_B),
        representative_source_pair_matrix=(internal_provenance.source_pair_matrix),
        representative_source_right_factor=build_to_source,
    )
    supercell_a = _primitive_recipe_from_match_class(match_class, slab=slab_a, side="A")
    supercell_b = _primitive_recipe_from_match_class(match_class, slab=slab_b, side="B")
    return InterfacePrototype(
        prototype_uid=prototype_uid,
        slab_a_uid=slab_a_uid,
        slab_b_uid=slab_b_uid,
        miller_a=_slab_miller(slab_a),
        miller_b=_slab_miller(slab_b),
        supercell_a=supercell_a,
        supercell_b=supercell_b,
        match_score=float(candidate.match_score),
        d_size=float(candidate.d_size),
        d_cell=float(candidate.ai_strain.d_cell),
        d_area=float(candidate.ai_strain.d_area),
        d_shape=float(candidate.ai_strain.d_shape),
        rel_da=float(candidate.zm_strain.rel_da),
        rel_db=float(candidate.zm_strain.rel_db),
        d_gamma_deg=float(candidate.zm_strain.d_gamma_deg),
        n_atoms_interface=int(candidate.atom_count),
        slab_a=slab_a,
        slab_b=slab_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
    )


def compute_strain_state(
    prototype: InterfacePrototype,
    model: StrainModel | None = None,
) -> StrainState:
    """Compute a strain state for a given prototype under a specified model.

    Parameters
    ----------
    prototype
        The interface prototype.
    model
        Strain-partition model. When omitted, use :class:`StrainModel` defaults.
    """
    if model is None:
        model = StrainModel()

    sm_uid = strain_model_uid(model)

    S_rot = _rotated_supercell_basis_3d(prototype.slab_a, prototype.supercell_a)
    T_rot = _rotated_supercell_basis_3d(prototype.slab_b, prototype.supercell_b)

    # Base affine-invariant split
    base = compute_strain_2d(
        S_rot,
        T_rot,
        alpha=float(model.alpha),
        eps_spd=float(model.eps_spd),
        check_common=bool(model.check_common),
        common_tol=float(model.common_tol),
    )

    if model.partition == "both":
        return StrainState(
            prototype_uid=prototype.prototype_uid,
            strain_model_uid=sm_uid,
            F_tot=np.asarray(base.F_tot, dtype=float),
            F_A=np.asarray(base.F_A, dtype=float),
            F_B=np.asarray(base.F_B, dtype=float),
            E_A_rms=float(base.E_A_rms),
            E_B_rms=float(base.E_B_rms),
            raw=base,
        )

    if model.partition == "A_only":
        I_mat = np.eye(3, dtype=float)
        F_A = np.asarray(base.F_tot, dtype=float)
        F_B = I_mat
        E_A_rms = _hencky_rms_2d(F_A)
        return StrainState(
            prototype_uid=prototype.prototype_uid,
            strain_model_uid=sm_uid,
            F_tot=np.asarray(base.F_tot, dtype=float),
            F_A=F_A,
            F_B=F_B,
            E_A_rms=float(E_A_rms),
            E_B_rms=0.0,
            raw=base,
        )

    if model.partition == "B_only":
        I_mat = np.eye(3, dtype=float)
        F_A = I_mat
        F_B = np.linalg.inv(np.asarray(base.F_tot, dtype=float))
        E_B_rms = _hencky_rms_2d(F_B)
        return StrainState(
            prototype_uid=prototype.prototype_uid,
            strain_model_uid=sm_uid,
            F_tot=np.asarray(base.F_tot, dtype=float),
            F_A=F_A,
            F_B=F_B,
            E_A_rms=0.0,
            E_B_rms=float(E_B_rms),
            raw=base,
        )

    raise ValueError(f"Unknown partition: {model.partition}")


def _hencky_rms_2d(F3: np.ndarray) -> float:
    """RMS Hencky strain from the polar decomposition of the in-plane block."""
    from scipy.linalg import polar

    from calm.math2d._core import sym2
    from calm.math2d.spd2x2 import log_spd

    F2 = np.asarray(F3, dtype=float)[:2, :2]
    _R2, U2 = polar(F2)
    U2 = sym2(U2)
    E2 = log_spd(U2)
    return float((1.0 / np.sqrt(2.0)) * np.linalg.norm(E2, ord="fro"))


def _rotated_supercell_basis_3d(slab: Slab, recipe: SupercellRecipe2D) -> np.ndarray:
    """Return 3x3 supercell basis (columns) after deterministic in-plane rotation."""
    A = np.asarray(slab.atoms.cell.array, dtype=float).T
    N3 = _embed_2x2_in_3x3(recipe.N_tot, dtype="int")
    R3 = _embed_2x2_in_3x3(recipe.R_sup, dtype="float")
    return R3 @ A @ N3


def build_interface(
    prototype: InterfacePrototype,
    strain: StrainState,
    build: InterfaceBuildConfig | None = None,
) -> Interface:
    """Build the atomistic interface corresponding to a prototype + strain state."""

    if build is None:
        build = InterfaceBuildConfig()

    strained = strained_uid_fn(
        prototype_uid=prototype.prototype_uid, strain_model_uid=strain.strain_model_uid
    )

    # Quantize translation for determinism (wrap into [0, 1) then round).
    t1, t2 = quantize_translation_frac(
        build.translation_frac, int(build.translation_round_decimals)
    )

    b_uid = build_uid(
        strained_uid=strained,
        translation_frac=(t1, t2),
        z_padding=float(build.z_padding),
        vacuum_padding=(
            None if build.vacuum_padding is None else float(build.vacuum_padding)
        ),
        round_decimals=int(build.translation_round_decimals),
    )

    slab_A = prototype.slab_a
    slab_B = prototype.slab_b
    if slab_A is None or slab_B is None:
        raise ValueError(
            "Prototype does not carry slab objects; cannot build atomistic interface."
        )

    N_A3 = _embed_2x2_in_3x3(prototype.supercell_a.N_tot, dtype="int")
    N_B3 = _embed_2x2_in_3x3(prototype.supercell_b.N_tot, dtype="int")
    R_A3 = _embed_2x2_in_3x3(prototype.supercell_a.R_sup, dtype="float")
    R_B3 = _embed_2x2_in_3x3(prototype.supercell_b.R_sup, dtype="float")

    built_structure = build_interface_atoms(
        slab_A_atoms=slab_A.atoms,
        slab_B_atoms=slab_B.atoms,
        N_A3=N_A3,
        N_B3=N_B3,
        R_A3=R_A3,
        R_B3=R_B3,
        F_A=np.asarray(strain.F_A, dtype=float),
        F_B=np.asarray(strain.F_B, dtype=float),
        translation_frac=(t1, t2),
        z_padding=float(build.z_padding),
        vacuum_padding=(
            None if build.vacuum_padding is None else float(build.vacuum_padding)
        ),
    )

    atoms = built_structure.atoms
    lower_idx = built_structure.lower_indices
    upper_idx = built_structure.upper_indices

    # Stamp metadata for downstream provenance
    build_metadata: dict[str, Any] = {
        "calm:prototype_uid": prototype.prototype_uid,
        "calm:strain_model_uid": strain.strain_model_uid,
        "calm:strained_uid": strained,
        "calm:build_uid": b_uid,
        "calm:translation_frac": (float(t1), float(t2)),
        "calm:z_padding": float(build.z_padding),
        "calm:vacuum_padding": (
            None if build.vacuum_padding is None else float(build.vacuum_padding)
        ),
    }
    if prototype.pair_identity is not None:
        build_metadata.update(
            {
                "calm:primitive_pair_key": tuple(
                    prototype.pair_identity.primitive_pair_key
                ),
                "calm:pair_key_version": int(prototype.pair_identity.key_version),
                "calm:pair_symmetry_policy": (
                    prototype.pair_identity.pair_symmetry_policy
                ),
                "calm:correspondence_orientation": (
                    prototype.pair_identity.correspondence_orientation
                ),
                "calm:material_exchange_identified": bool(
                    prototype.pair_identity.material_exchange_identified
                ),
            }
        )
    deformation_accounting = built_structure.deformation_accounting
    if deformation_accounting is not None:

        def _side_payload(side):
            return {
                "F_construction_slab": side.F_construction.tolist(),
                "F_interface_slab": side.F_interface.tolist(),
                "F_total_slab": side.F_total.tolist(),
            }

        build_metadata[INTERFACE_DEFORMATION_ACCOUNTING_INFO_KEY] = (
            canonical_interface_deformation_accounting(
                {
                    "policy": deformation_accounting.policy,
                    "version": int(deformation_accounting.version),
                    "lower": _side_payload(deformation_accounting.lower),
                    "upper": _side_payload(deformation_accounting.upper),
                }
            )
        )
    atoms.info.update(build_metadata)

    return Interface(
        prototype_uid=prototype.prototype_uid,
        strained_uid=strained,
        build_uid=b_uid,
        atoms=atoms,
        lower_indices=lower_idx,
        upper_indices=upper_idx,
        prototype=prototype,
        strain_state=strain,
        build_config=build,
    )


def compute_interfacial_energy(
    interface: Interface,
    calc: Any,
    config: EnergyConfig | None = None,
) -> EnergyResult:
    """Compute strained-bulk interface excess energy per interface area.

    This is the public *runner* entrypoint. It intentionally separates concerns:

    - Geometry and reference-structure preparation (calculator-free) lives in
      :func:`calm.interface.energy._kernel.prepare_interfacial_energy_geometry`.

    - The scalar reduction from energies to ``(mu_bulk_A, mu_bulk_B, gamma)``
      lives in
      :func:`calm.interface.energy._kernel.compute_interfacial_energy_from_energies`.

    The split improves testability (the scalar kernel can be unit-tested without an
    ASE calculator) and reduces brittleness from side effects.
    """

    if config is None:
        config = EnergyConfig()

    if interface.atoms is None:
        raise ValueError(
            "Interface has no atoms (build_interface must be called first)."
        )

    # UIDs
    econf_uid = energy_config_uid(config)
    calc_uid = get_calculator_uid(calc)
    e_uid = energy_uid(
        build_uid=interface.build_uid,
        calc_uid=calc_uid,
        econf_uid=econf_uid,
    )

    # Defer heavy work to the kernel (lazy import keeps the module import light).
    from calm.interface.energy._kernel import (
        compute_interfacial_energy_from_energies,
        prepare_interfacial_energy_geometry,
    )

    geom = prepare_interfacial_energy_geometry(interface, config)

    def _potential_energy_eV(atoms: Any) -> float:
        """Evaluate potential energy in eV for an ASE Atoms-like object.

        Back-compat: ``calc`` is typically an ASE calculator. For improved
        unit-testability, we also accept a callable ``calc(atoms) -> float`` as a
        lightweight energy function, provided it does not look like an ASE calculator
        (i.e., no ``calculate`` attribute) and exposes an explicit CALM UID or
        mapping-valued settings for deterministic provenance.
        """
        try:
            if callable(calc) and not hasattr(calc, "calculate"):
                energy = float(calc(atoms))  # type: ignore[misc]
            else:
                atoms.calc = calc  # type: ignore[assignment]
                energy = float(atoms.get_potential_energy())
        except CalculatorError:
            raise
        except Exception as exc:
            raise CalculatorExecutionError(
                "Calculator failed during interfacial-energy evaluation: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        if not np.isfinite(energy):
            raise CalculatorExecutionError(
                "Calculator returned a non-finite interfacial energy."
            )
        return energy

    bulk_A_reference_total_energy_eV = _potential_energy_eV(geom.bulk_A_strained)
    bulk_B_reference_total_energy_eV = _potential_energy_eV(geom.bulk_B_strained)
    interface_total_energy_eV = _potential_energy_eV(interface.atoms)

    vals = compute_interfacial_energy_from_energies(
        E_int_eV=interface_total_energy_eV,
        E_bulk_A_eV=bulk_A_reference_total_energy_eV,
        E_bulk_B_eV=bulk_B_reference_total_energy_eV,
        geom=geom,
    )

    # Compose EnergyResult with extended provenance fields related to strain
    # and strained-bulk reference construction. These fields are added
    # additively to avoid breaking existing consumers.
    return EnergyResult(
        interface_uid=interface.build_uid,
        calc_uid=calc_uid,
        econf_uid=econf_uid,
        energy_uid=e_uid,
        gamma_eV_per_A2=float(vals.gamma_eV_per_A2),
        gamma_J_per_m2=float(vals.gamma_J_per_m2),
        area_A2=float(geom.area_A2),
        E_int_eV=float(interface_total_energy_eV),
        n_fu_slab_A=int(geom.n_fu_slab_A),
        n_fu_slab_B=int(geom.n_fu_slab_B),
        mu_bulk_A_eV_per_fu=float(vals.mu_bulk_A_eV_per_fu),
        mu_bulk_B_eV_per_fu=float(vals.mu_bulk_B_eV_per_fu),
        formula_A=str(geom.formula_A),
        formula_B=str(geom.formula_B),
        n_interfaces=int(geom.n_interfaces),
        thermodynamic_formula=str(geom.thermodynamic_formula),
        thermodynamic_quantity=str(geom.thermodynamic_quantity),
        config=config,
        # Extended provenance
        # Note: these aliases are intentionally optional and will be present
        # in the EnergyResult.to_dict()/signature() via explicit checks.
        **{
            "F_A_slab": getattr(geom, "F_A_slab", None),
            "F_B_slab": getattr(geom, "F_B_slab", None),
            "F_A_construction_slab": getattr(
                geom, "F_A_construction_slab", None
            ),
            "F_B_construction_slab": getattr(
                geom, "F_B_construction_slab", None
            ),
            "F_A_total_slab": getattr(geom, "F_A_total_slab", None),
            "F_B_total_slab": getattr(geom, "F_B_total_slab", None),
            "F_A_conv": getattr(geom, "F_A_conv", None),
            "F_B_conv": getattr(geom, "F_B_conv", None),
            "F_A_construction_conv": getattr(
                geom, "F_A_construction_conv", None
            ),
            "F_B_construction_conv": getattr(
                geom, "F_B_construction_conv", None
            ),
            "F_A_total_conv": getattr(geom, "F_A_total_conv", None),
            "F_B_total_conv": getattr(geom, "F_B_total_conv", None),
            "slab_deformation_accounting_policy": getattr(
                geom, "slab_deformation_accounting_policy", None
            ),
            "slab_deformation_accounting_version": getattr(
                geom, "slab_deformation_accounting_version", None
            ),
            "strained_bulk_cell_A_3x3": getattr(geom, "strained_bulk_cell_A_3x3", None),
            "strained_bulk_cell_B_3x3": getattr(geom, "strained_bulk_cell_B_3x3", None),
            "strained_bulk_reference_mode": getattr(
                geom,
                "strained_bulk_reference_mode",
                "unrelaxed_scaled_positions",
            ),
            "bulk_reference_relaxed": getattr(geom, "bulk_reference_relaxed", False),
            "bulk_reference_calculation_id_A": getattr(
                geom, "bulk_reference_calculation_id_A", None
            ),
            "bulk_reference_calculation_id_B": getattr(
                geom, "bulk_reference_calculation_id_B", None
            ),
            "gamma_reference_convention": getattr(
                geom,
                "gamma_reference_convention",
                "strained_unrelaxed_bulk_subtraction",
            ),
        },
    )
