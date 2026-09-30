from __future__ import annotations

import pytest

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    canonical_d_cell_key,
)
from calm.project.application.prototypes import _compute_pareto_flags
from calm.project.domain.models import Prototype


def _prototype(
    uid: str,
    *,
    atoms: int,
    d_cell: float,
    area: float,
) -> Prototype:
    return Prototype(
        uid_full=uid,
        id_short=uid.replace(":", "_"),
        run_uid_full="run:test",
        run_id_short="r_test",
        slab_a_uid_full="slab:A",
        slab_b_uid_full="slab:B",
        match_score=0.0,
        hencky_norm=0.5 * d_cell,
        interface_area=area,
        natoms=atoms,
        is_pareto=False,
        pareto_rank=None,
        payload={"metrics": {"d_cell": d_cell}},
    )


def test_persistence_uses_atom_count_strain_front_not_area_strain_front() -> None:
    records = _compute_pareto_flags(
        [
            _prototype("proto:P1", atoms=100, d_cell=0.1, area=1.0),
            _prototype("proto:P2", atoms=50, d_cell=0.2, area=2.0),
        ]
    )

    assert [record.is_pareto for record in records] == [True, True]
    for record in records:
        metadata = record.payload["pareto"]
        assert metadata["policy"] == STRAIN_SIZE_PARETO_POLICY
        assert metadata["population_size"] == 2
        assert metadata["objectives"] == ["n_atoms_interface", "d_cell"]


def test_repository_summary_rejects_missing_current_pareto_metadata() -> None:
    import json

    from calm.project.infrastructure.db.repos import SqlAlchemyPrototypeRepository

    row = {
        "uid_full": "proto:test",
        "id_short": "p_test",
        "run_uid_full": "run:test",
        "run_id_short": "r_test",
        "slab_a_uid_full": "slab:A",
        "slab_a_id_short": "s_a",
        "slab_b_uid_full": "slab:B",
        "slab_b_id_short": "s_b",
        "match_score": 0.1,
        "hencky_norm": 0.05,
        "interface_area": 1.0,
        "n_atoms": 10,
        "is_pareto": True,
        "pareto_rank": 0,
        "created_at": None,
    }

    with pytest.raises(ValueError, match="complete strain-size Pareto metadata"):
        SqlAlchemyPrototypeRepository._row_to_prototype_summary(
            {**row, "payload_json": json.dumps({})}
        )

    current_record = _compute_pareto_flags(
        [_prototype("proto:test", atoms=10, d_cell=0.1, area=1.0)]
    )[0]
    current = SqlAlchemyPrototypeRepository._row_to_prototype_summary(
        {**row, "payload_json": json.dumps(current_record.payload)}
    )
    assert current.is_pareto is True
    assert current.pareto_status == "authoritative"
    assert current.pareto_policy == STRAIN_SIZE_PARETO_POLICY
    assert current.d_cell == 0.1
    assert current.pareto_d_cell_key == canonical_d_cell_key(0.1)

def test_repository_summary_preserves_named_scoped_alternative() -> None:
    import json

    from calm.project.infrastructure.db.repos import (
        SqlAlchemyPrototypeRepository,
    )

    record = _compute_pareto_flags(
        [_prototype("proto:alt", atoms=10, d_cell=0.1, area=1.0)],
        policy="persisted_input_strain_size_pareto",
        population_scope="persisted_input_population",
    )[0]
    summary = SqlAlchemyPrototypeRepository._row_to_prototype_summary(
        {
            "uid_full": record.uid_full,
            "id_short": record.id_short,
            "run_uid_full": record.run_uid_full,
            "run_id_short": record.run_id_short,
            "slab_a_uid_full": record.slab_a_uid_full,
            "slab_a_id_short": "s_a",
            "slab_b_uid_full": record.slab_b_uid_full,
            "slab_b_id_short": "s_b",
            "match_score": record.match_score,
            "hencky_norm": record.hencky_norm,
            "interface_area": record.interface_area,
            "n_atoms": record.natoms,
            "is_pareto": record.is_pareto,
            "pareto_rank": record.pareto_rank,
            "payload_json": json.dumps(record.payload),
            "created_at": None,
        }
    )

    assert summary.is_pareto is True
    assert summary.pareto_status == "scoped_alternative"
    assert summary.pareto_policy == "persisted_input_strain_size_pareto"
    assert summary.pareto_population_scope == "persisted_input_population"


def test_repository_applies_limit_after_authoritative_pareto_filter() -> None:
    import json

    from sqlalchemy import create_engine, insert

    from calm.analysis.pareto import authoritative_pareto_metadata
    from calm.project.infrastructure.db.repos import SqlAlchemyPrototypeRepository
    from calm.project.infrastructure.db.tables import (
        bulks,
        metadata,
        prototypes,
        runs,
        slabs,
    )

    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(bulks),
            {
                "uid_full": "bulk:test",
                "id_short": "b_test",
                "payload_json": "{}",
            },
        )
        bulk_pk = connection.execute(
            bulks.select().with_only_columns(bulks.c.bulk_pk)
        ).scalar_one()
        connection.execute(
            insert(slabs),
            [
                {
                    "uid_full": "slab:A",
                    "id_short": "s_a",
                    "bulk_pk": bulk_pk,
                    "payload_json": "{}",
                },
                {
                    "uid_full": "slab:B",
                    "id_short": "s_b",
                    "bulk_pk": bulk_pk,
                    "payload_json": "{}",
                },
            ],
        )
        connection.execute(
            insert(runs),
            {
                "uid_full": "run:test",
                "id_short": "r_test",
                "run_type": "prototype_search",
                "status": "done",
                "spec_json": "{}",
            },
        )
        current = authoritative_pareto_metadata(
            is_member=True,
            rank=0,
            population_size=2,
            d_cell_key=100,
        )
        scoped_alternative = dict(current)
        scoped_alternative["policy"] = "persisted_input_strain_size_pareto"
        scoped_alternative["population_scope"] = "persisted_input_population"
        connection.execute(
            insert(prototypes),
            [
                {
                    "uid_full": "proto:alternative",
                    "id_short": "p_alternative",
                    "run_uid_full": "run:test",
                    "slab_a_uid_full": "slab:A",
                    "slab_b_uid_full": "slab:B",
                    "n_atoms": 20,
                    "is_pareto": True,
                    "payload_json": json.dumps(
                        {"pareto": scoped_alternative}
                    ),
                },
                {
                    "uid_full": "proto:current",
                    "id_short": "p_current",
                    "run_uid_full": "run:test",
                    "slab_a_uid_full": "slab:A",
                    "slab_b_uid_full": "slab:B",
                    "n_atoms": 10,
                    "is_pareto": True,
                    "payload_json": json.dumps({"pareto": current}),
                },
            ],
        )

        result = SqlAlchemyPrototypeRepository(connection).query(
            pareto_only=True,
            limit=1,
        )

    engine.dispose()
    assert [item.uid_full for item in result] == ["proto:current"]


def test_nonprototype_repository_limits_do_not_use_pareto_state() -> None:
    from sqlalchemy import create_engine

    from calm.project.infrastructure.db.repos import (
        SqlAlchemyBulkRepository,
        SqlAlchemyEdgeRepository,
        SqlAlchemyFollowupResultRepository,
    )
    from calm.project.infrastructure.db.tables import metadata

    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    with engine.begin() as connection:
        assert SqlAlchemyBulkRepository(connection, object()).list(limit=1) == []
        assert SqlAlchemyFollowupResultRepository(connection).list(limit=1) == []
        assert SqlAlchemyEdgeRepository(connection).list(limit=1) == []
    engine.dispose()
