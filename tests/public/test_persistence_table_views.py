from __future__ import annotations

import csv
from pathlib import Path

from calm.public.collections.persistence import (
    ArtifactCollection,
    EdgeCollection,
    FollowupCollection,
    RunCollection,
    SearchCollection,
)
from calm.public.records.persistence import (
    ProjectArtifact,
    ProjectEdge,
    ProjectFollowupResult,
    ProjectRun,
    ProjectSearch,
    RecordAuthority,
)


def test_general_persistence_collections_use_named_views(tmp_path: Path) -> None:
    search = SearchCollection(
        [
            ProjectSearch(
                name="lif-lio",
                uid_full="run:search-one",
                id_short="r_search",
                run_uid_full="run:search-one",
                run_id_short="r_search",
                search_identity="search_identity:one",
                status="completed",
                n_candidates=50,
                metadata={"custom_metric": 3.0},
                created_at="2026-01-01T00:00:00",
                authority=RecordAuthority.AUTHORITATIVE,
            )
        ]
    )
    run = RunCollection(
        [
            ProjectRun(
                uid_full="run:one",
                id_short="r_one",
                run_type="interface_search",
                status="completed",
                created_at="2026-01-01T00:00:00",
                authority=RecordAuthority.AUTHORITATIVE,
            )
        ]
    )
    followup = FollowupCollection(
        [
            ProjectFollowupResult(
                uid_full="followup:one",
                id_short="f_one",
                kind="strain_partition_scan",
                status="completed",
                run_uid_full="run:one",
                target_uid_full="prototype:one",
                target_kind="prototype",
                param1=0.4,
                n_points=11,
                authority=RecordAuthority.AUTHORITATIVE,
            )
        ]
    )
    artifact = ArtifactCollection(
        [
            ProjectArtifact(
                uid_full="artifact:one",
                id_short="a_one",
                run_uid_full="run:one",
                kind="csv",
                uri="artifacts/results.csv",
                authority=RecordAuthority.AUTHORITATIVE,
            )
        ]
    )
    edge = EdgeCollection(
        [
            ProjectEdge(
                uid_full="edge:one",
                src_uid_full="run:one",
                dst_uid_full="artifact:one",
                kind="produced",
                authority=RecordAuthority.AUTHORITATIVE,
            )
        ]
    )

    for collection in (search, run, followup, artifact, edge):
        assert collection.available_views() == ("summary", "provenance", "all")
        assert list(collection.to_rows()[0]) == list(
            collection.to_dataframe().columns
        )
        assert "authority" not in collection.to_rows()[0]
        assert collection.to_rows(view="provenance")[0]["authority"] == (
            "authoritative"
        )

    assert search.to_rows()[0]["n_candidates"] == 50
    assert search.to_rows(view="all")[0]["custom_metric"] == 3.0
    assert followup.to_rows(view="all")[0]["alpha_opt"] == 0.4
    assert followup.to_rows()[0]["target_id_short"].startswith("p_")
    assert artifact.to_rows()[0]["run_id_short"].startswith("r_")
    assert edge.to_rows()[0]["src_id_short"].startswith("r_")
    assert edge.to_rows()[0]["dst_id_short"].startswith("a_")

    for name, collection in (
        ("search", SearchCollection([])),
        ("run", RunCollection([])),
        ("followup", FollowupCollection([])),
        ("artifact", ArtifactCollection([])),
        ("edge", EdgeCollection([])),
    ):
        output = tmp_path / f"{name}.csv"
        collection.write_table(output)
        with output.open(newline="", encoding="utf-8") as stream:
            header = next(csv.reader(stream))
        assert header == list(collection._view_specs[0].columns)


def test_general_persistence_views_reject_retired_table_selector() -> None:
    collection = RunCollection([])

    try:
        collection.to_table(table="runs")  # type: ignore[call-arg]
    except TypeError as exc:
        assert "table" in str(exc)
    else:  # pragma: no cover - contract guard
        raise AssertionError("retired table selector was unexpectedly accepted")
