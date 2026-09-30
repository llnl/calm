from __future__ import annotations

import json

from energy_result_fixtures import raw_energy_payload

from calm.analysis.pareto import strain_size_pareto_metadata
from calm.project.application.followups.common import persisted_followup_uid
from calm.project.domain.models import FollowupResult
from calm.public.records.persistence import RecordAuthority
from calm.public.project import Project


class _DatabaseWorkspace:
    """Dependency-light Workspace slice backed by the real project UoW."""

    def __init__(self, uow):
        self._uow = uow
        self._uow_factory = lambda: self._uow

    def list_runs(self, *, run_type=None, status=None, limit=None):
        with self._uow as active:
            return active.runs.list(
                run_type=run_type,
                status=status,
                limit=limit,
            )

    def get_run(self, identifier):
        with self._uow as active:
            uid = active.ids.resolve(identifier, expected_tag="r")
            value = active.runs.get_by_uid_full(uid)
        if value is None:
            raise KeyError(identifier)
        return value

    def list_interface_searches(self, *, limit=None):
        with self._uow as active:
            return active.interface_searches.list(limit=limit)

    def get_interface_search(self, identifier):
        with self._uow as active:
            value = (
                active.interface_searches.get_by_name(identifier)
                or active.interface_searches.get_by_search_identity(identifier)
                or active.interface_searches.get_by_run_uid_full(identifier)
                or active.interface_searches.get_by_run_id_short(identifier)
            )
        if value is None:
            raise KeyError(identifier)
        return value

    def list_followup_results(
        self,
        *,
        run=None,
        prototype=None,
        kind=None,
        limit=None,
    ):
        with self._uow as active:
            run_uid = active.ids.resolve(run, expected_tag="r") if run else None
            prototype_uid = (
                active.ids.resolve(prototype, expected_tag="p")
                if prototype
                else None
            )
            return active.followups.list(
                run_uid_full=run_uid,
                prototype_uid_full=prototype_uid,
                kind=kind,
                limit=limit,
            )


    def get_followup_result(self, identifier):
        with self._uow as active:
            value = active.followups.get_by_uid_full(identifier)
        if value is None:
            raise KeyError(identifier)
        return value

    def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
        with self._uow as active:
            return active.edges.list(
                src_uid_full=src,
                dst_uid_full=dst,
                kind=kind,
                limit=limit,
            )


    def resolve_identifier(self, identifier):
        with self._uow as active:
            return active.ids.resolve(identifier)

    def list_artifacts(self, run):
        with self._uow as active:
            run_uid = active.ids.resolve(run, expected_tag="r")
            return active.artifacts.list_artifacts(run_uid_full=run_uid)

    def list_prototypes(self, *, run=None, limit=None):
        with self._uow as active:
            run_uid = active.ids.resolve(run, expected_tag="r") if run else None
            return active.prototypes.query(
                run_uid_full=run_uid,
                limit=limit,
            )

    def get_prototype(self, identifier):
        with self._uow as active:
            uid = active.ids.resolve(identifier, expected_tag="p")
            value = active.prototypes.get_by_uid_full(uid)
        if value is None:
            raise KeyError(identifier)
        return value


def test_public_lineage_roundtrips_real_sqlite_edges(
    schema_uow_factory,
    tmp_path,
):
    from calm.project.infrastructure.db.tables import (
        bulks,
        interface_searches,
        prototypes,
        runs,
    )
    from calm.project.domain.models import Slab
    from slab_record_fixtures import current_slab_payload, current_slab_uid

    uow = schema_uow_factory()
    try:
        with uow as active:
            active.connection.execute(
                bulks.insert().values(
                    uid_full="bulk:phase1",
                    id_short="b_deadbeef",
                    payload_json=json.dumps({}),
                )
            )
            slab_rows = []
            for token, short in (
                ("slab:phase1:a", "s_a1a1a1a1"),
                ("slab:phase1:b", "s_b2b2b2b2"),
            ):
                payload = current_slab_payload(
                    bulk_uid_full="bulk:phase1",
                    user_payload={"fixture_token": token},
                )
                uid = current_slab_uid(
                    bulk_uid_full="bulk:phase1",
                    miller=(0, 0, 1),
                    payload=payload,
                )
                slab_rows.append(
                    Slab(
                        uid_full=uid,
                        id_short=short,
                        bulk_uid_full="bulk:phase1",
                        bulk_id_short="b_deadbeef",
                        miller=(0, 0, 1),
                        payload=payload,
                    )
                )
            active.slabs.create_many(slab_rows)
            active.connection.execute(
                runs.insert().values(
                    uid_full="run:phase1",
                    id_short="r_c3c3c3c3",
                    run_type="prototype_search",
                    status="done",
                    spec_json=json.dumps(
                        {"search_identity": "interface_search:phase1"}
                    ),
                )
            )
            active.connection.execute(
                interface_searches.insert().values(
                    name="phase1_search",
                    search_identity="interface_search:phase1",
                    run_uid_full="run:phase1",
                )
            )
            active.connection.execute(
                prototypes.insert().values(
                    uid_full="proto:phase1",
                    id_short="p_d4d4d4d4",
                    run_uid_full="run:phase1",
                    slab_a_uid_full=slab_rows[0].uid_full,
                    slab_b_uid_full=slab_rows[1].uid_full,
                    payload_json=json.dumps(
                        {
                            "pareto": strain_size_pareto_metadata(
                                policy="current_collection_strain_size_pareto",
                                population_scope="current_collection_population",
                                is_member=True,
                                rank=0,
                                population_size=1,
                                d_cell_key=0,
                            )
                        }
                    ),
                )
            )
            followup = FollowupResult(
                uid_full=persisted_followup_uid(
                    run_uid_full="run:phase1",
                    prototype_uid_full="proto:phase1",
                    target_uid_full="proto:phase1",
                    target_kind="prototype",
                    kind="energy_stage",
                ),
                id_short="f_01234567",
                run_uid_full="run:phase1",
                run_id_short="r_c3c3c3c3",
                prototype_uid_full="proto:phase1",
                prototype_id_short="p_d4d4d4d4",
                target_uid_full="proto:phase1",
                target_kind="prototype",
                kind="energy_stage",
                n_points=1,
                best_energy=-1.0,
                payload=raw_energy_payload(-1.0, interface_area_A2=None),
            )
            active.followups.upsert_many([followup])
            active.edges.add(
                src_uid_full="run:phase1",
                dst_uid_full="proto:phase1",
                kind="run_to_prototype",
            )
            active.edges.add(
                src_uid_full="proto:phase1",
                dst_uid_full=followup.uid_full,
                kind="prototype_to_followup",
            )

        project = Project(_DatabaseWorkspace(uow), path=tmp_path / "phase1.calm")

        search = project.search("phase1_search")
        graph = project.lineage("p_d4d4d4d4")
        followup_record = project.followups(kind="energy_stage")[0]

        assert search.uid_full == "run:phase1"
        assert search.authority is RecordAuthority.AUTHORITATIVE
        assert graph.root_uid_full == "proto:phase1"
        assert {edge.kind for edge in graph.edges} == {
            "run_to_prototype",
            "prototype_to_followup",
        }
        assert graph.node(followup.uid_full).kind == "followup_result"
        assert graph.node(followup.uid_full).id_short == "f_01234567"
        assert followup_record.uid_full == followup.uid_full
        assert followup_record.is_authoritative
    finally:
        uow.engine.dispose()
