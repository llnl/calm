from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from calm.interface.model import (
    InterfacePrototype,
    MatchSourceProvenance2D,
    PairIdentity2D,
    SupercellRecipe2D,
)
from calm.keys.uid import prototype_uid_v3
from calm.project.application.interface_prototype_payload import (
    IDENTITY_ALGORITHM_V2,
    SCHEMA_V2,
    interface_prototype_identity_algorithm,
    load_interface_prototype,
    serialize_interface_prototype,
    validate_interface_prototype_payload,
)


PAIR_KEY = (1, 0, 0, 1, 1, 0, 0, 1)


def _recipe() -> SupercellRecipe2D:
    return SupercellRecipe2D(
        k=1,
        N_tot=np.eye(2, dtype=int),
        R_sup=np.eye(2),
        hnf_key_pg=(1, 0, 0, 1),
        cond=1.0,
        S_red=np.eye(2),
        G_red=np.eye(2),
    )


def _prototype() -> InterfacePrototype:
    pair_identity = PairIdentity2D(
        key_version=1,
        primitive_pair_key=PAIR_KEY,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        material_exchange_identified=False,
    )
    source_pair = np.vstack([np.eye(2, dtype=int), np.eye(2, dtype=int)])
    provenance = MatchSourceProvenance2D(
        source_count=1,
        minimum_source_indices=(1, 1),
        source_index_pairs=((1, 1),),
        repeat_indices=(1,),
        representative_source_H_A=np.eye(2, dtype=int),
        representative_source_H_B=np.eye(2, dtype=int),
        representative_source_N_A=np.eye(2, dtype=int),
        representative_source_N_B=np.eye(2, dtype=int),
        representative_correspondence_U_B=np.eye(2, dtype=int),
        representative_source_pair_matrix=source_pair,
        representative_source_right_factor=np.eye(2, dtype=int),
    )
    slab_a = SimpleNamespace(project_slab_uid_full="slab:a")
    slab_b = SimpleNamespace(project_slab_uid_full="slab:b")
    return InterfacePrototype(
        prototype_uid=prototype_uid_v3(
            slab_uid_a="slab:a",
            slab_uid_b="slab:b",
            primitive_pair_key=PAIR_KEY,
            pair_key_version=1,
            pair_symmetry_policy="full",
            correspondence_orientation="proper",
            material_exchange_identified=False,
        ),
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
        miller_a=(0, 0, 1),
        miller_b=(0, 0, 1),
        supercell_a=_recipe(),
        supercell_b=_recipe(),
        match_score=0.0,
        d_size=0.0,
        d_cell=0.0,
        d_area=0.0,
        d_shape=0.0,
        rel_da=0.0,
        rel_db=0.0,
        d_gamma_deg=0.0,
        n_atoms_interface=2,
        slab_a=slab_a,
        slab_b=slab_b,
        pair_identity=pair_identity,
        source_provenance=provenance,
    )


def _record(payload: dict[str, object]) -> SimpleNamespace:
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    pareto = payload.get("pareto")
    return SimpleNamespace(
        payload=payload,
        uid_full="prototype:persisted",
        slab_a_uid_full=payload["slab_a_uid"],
        slab_b_uid_full=payload["slab_b_uid"],
        match_score=metrics["match_score"],
        hencky_norm=0.5 * float(metrics["d_cell"]),
        interface_area=metrics["interface_area_A2"],
        natoms=metrics["n_atoms_interface"],
        is_pareto=False if pareto is None else pareto["is_member"],
        pareto_rank=None if pareto is None else pareto["rank"],
    )


def _uow(record: object, slab_a: object, slab_b: object) -> SimpleNamespace:
    return SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=SimpleNamespace(
            get_by_uid_full=lambda uid: {
                "slab:a": slab_a,
                "slab:b": slab_b,
            }.get(uid)
        ),
    )


def test_coupled_prototype_serializes_as_v2_and_validates() -> None:
    payload = serialize_interface_prototype(_prototype())

    assert payload["schema"] == SCHEMA_V2
    assert payload["identity_algorithm"] == IDENTITY_ALGORITHM_V2
    assert payload["pair_identity"]["primitive_pair_key"] == list(PAIR_KEY)
    assert payload["source_provenance"]["repeat_indices"] == [1]
    assert payload["supercell_a"]["N_tot"] == [[1, 0], [0, 1]]
    assert validate_interface_prototype_payload(payload) == (True, None)


def test_prototype_without_exact_coupled_identity_is_rejected() -> None:
    incomplete = SimpleNamespace(
        prototype_uid="proto:incomplete",
        slab_a_uid="slab:a",
        slab_b_uid="slab:b",
        miller_a=(0, 0, 1),
        miller_b=(0, 0, 1),
        supercell_a=_recipe(),
        supercell_b=_recipe(),
        match_score=0.0,
        d_size=0.0,
        d_cell=0.0,
        d_area=0.0,
        d_shape=0.0,
        rel_da=0.0,
        rel_db=0.0,
        d_gamma_deg=0.0,
        n_atoms_interface=2,
    )

    with pytest.raises(TypeError, match="requires an InterfacePrototype"):
        serialize_interface_prototype(incomplete)


def test_identity_algorithm_must_be_explicit_coupled_v2() -> None:
    with pytest.raises(ValueError, match="primitive_coupled_pair_v2"):
        interface_prototype_identity_algorithm(
            {"schema": "calm.interface_prototype_build_payload/v1"}
        )


def test_v2_validation_rejects_missing_exact_provenance() -> None:
    payload = serialize_interface_prototype(_prototype())
    payload.pop("source_provenance")

    ok, reason = validate_interface_prototype_payload(payload)

    assert ok is False
    assert reason is not None
    assert "source_provenance" in reason


def test_v2_payload_rehydrates_exact_identity_and_primitive_maps() -> None:
    prototype = _prototype()
    payload = serialize_interface_prototype(prototype)
    slab_a = SimpleNamespace(uid="slab:a")
    slab_b = SimpleNamespace(uid="slab:b")

    class _Slabs:
        def get_by_uid_full(self, uid):
            return {"slab:a": slab_a, "slab:b": slab_b}.get(uid)

    record = _record(payload)
    uow = SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=_Slabs(),
    )

    restored = load_interface_prototype(uow, "prototype:persisted")

    assert restored is not None
    assert restored.prototype_uid == prototype.prototype_uid
    assert restored.pair_identity == prototype.pair_identity
    assert restored.source_provenance is not None
    assert np.array_equal(
        restored.source_provenance.representative_source_pair_matrix,
        prototype.source_provenance.representative_source_pair_matrix,
    )
    assert np.array_equal(restored.supercell_a.N_tot, np.eye(2, dtype=int))


def test_payload_without_pair_identity_is_rejected() -> None:
    prototype = _prototype()
    payload = serialize_interface_prototype(prototype)
    payload["pair_identity"] = None
    slabs = {"slab:a": SimpleNamespace(), "slab:b": SimpleNamespace()}
    record = _record(payload)
    uow = SimpleNamespace(
        prototypes=SimpleNamespace(get_by_uid_full=lambda _uid: record),
        slabs=SimpleNamespace(get_by_uid_full=lambda uid: slabs.get(uid)),
    )

    with pytest.raises(ValueError, match="pair_identity"):
        load_interface_prototype(uow, "prototype:persisted")


def test_loader_rejects_payload_and_indexed_slab_identity_disagreement() -> None:
    payload = serialize_interface_prototype(_prototype())
    record = _record(payload)
    record.slab_a_uid_full = "slab:wrong"
    uow = _uow(record, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(ValueError, match="side-A slab identity"):
        load_interface_prototype(uow, "prototype:persisted")


def test_loader_rejects_scalar_projection_disagreement() -> None:
    payload = serialize_interface_prototype(_prototype())
    record = _record(payload)
    record.match_score = 1.0
    uow = _uow(record, SimpleNamespace(), SimpleNamespace())

    with pytest.raises(ValueError, match="match_score projection"):
        load_interface_prototype(uow, "prototype:persisted")


def test_loader_rejects_missing_persisted_slab() -> None:
    payload = serialize_interface_prototype(_prototype())
    record = _record(payload)
    uow = _uow(record, SimpleNamespace(), None)

    with pytest.raises(ValueError, match="could not be resolved"):
        load_interface_prototype(uow, "prototype:persisted")


def test_loader_rehydrates_authoritative_pareto_metadata() -> None:
    from calm.analysis.pareto import authoritative_pareto_metadata

    payload = serialize_interface_prototype(_prototype())
    payload["pareto"] = authoritative_pareto_metadata(
        is_member=True,
        rank=0,
        population_size=1,
        d_cell_key=0,
    )
    record = _record(payload)
    uow = _uow(record, SimpleNamespace(), SimpleNamespace())

    restored = load_interface_prototype(uow, "prototype:persisted")

    assert restored.is_pareto is True
    assert restored.pareto_rank == 0
    assert restored.pareto_policy == "strain_size_pareto"
    assert restored.pareto_population_size == 1


def test_prototype_persistence_uses_authoritative_payload_contract() -> None:
    import inspect

    from calm.project.application.prototypes import PrototypesService

    source = inspect.getsource(
        PrototypesService.persist_interface_prototypes
    )

    assert "serialize_interface_prototype(internal)" in source
    assert "_serialize_interface_prototype" not in source
