from __future__ import annotations

import json

from energy_result_fixtures import raw_energy_payload, reference_energy_payload

from calm.project.application.followups.common import persisted_followup_uid
from calm.project.application.followups.thermodynamics import ThermodynamicOrchestrator
from calm.project.domain.models import FollowupResult, Slab
from calm.public.records.persistence import ProjectReferenceEnergyResult
from slab_record_fixtures import current_slab_payload, current_slab_uid


def _seed_energy_rows(uow) -> tuple[str, str, str]:
    from calm.project.infrastructure.db.tables import bulks, prototypes, runs

    raw_uid = persisted_followup_uid(
        run_uid_full="run:raw-reference-test",
        prototype_uid_full="proto:reference-test",
        target_uid_full="interface:reference-test",
        target_kind="interface",
        kind="energy_stage",
    )
    reference_a_uid = persisted_followup_uid(
        run_uid_full="run:reference-test",
        prototype_uid_full="proto:reference-test",
        target_uid_full="interface:reference-test",
        target_kind="interface",
        kind="reference_energy",
        qualifiers={"reference_kind": "strained_bulk_a"},
    )
    reference_b_uid = persisted_followup_uid(
        run_uid_full="run:reference-test",
        prototype_uid_full="proto:reference-test",
        target_uid_full="interface:reference-test",
        target_kind="interface",
        kind="reference_energy",
        qualifiers={"reference_kind": "strained_bulk_b"},
    )

    with uow as active:
        active.connection.execute(
            bulks.insert().values(
                uid_full="bulk:reference-test",
                id_short="b_ref0001",
                payload_json=json.dumps({}),
            )
        )
        slab_rows = []
        for token, short in (
            ("slab:reference-test:a", "s_ref000a"),
            ("slab:reference-test:b", "s_ref000b"),
        ):
            payload = current_slab_payload(
                bulk_uid_full="bulk:reference-test",
                user_payload={"fixture_token": token},
            )
            uid = current_slab_uid(
                bulk_uid_full="bulk:reference-test",
                miller=(0, 0, 1),
                payload=payload,
            )
            slab_rows.append(
                Slab(
                    uid_full=uid,
                    id_short=short,
                    bulk_uid_full="bulk:reference-test",
                    bulk_id_short="b_ref0001",
                    miller=(0, 0, 1),
                    payload=payload,
                )
            )
        active.slabs.create_many(slab_rows)
        for uid, short, run_type in (
            ("run:raw-reference-test", "r_refraw1", "energy_stage"),
            ("run:reference-test", "r_refcalc", "reference_energy"),
        ):
            active.connection.execute(
                runs.insert().values(
                    uid_full=uid,
                    id_short=short,
                    run_type=run_type,
                    status="done",
                    spec_json=json.dumps({"kind": run_type}),
                )
            )
        active.connection.execute(
            prototypes.insert().values(
                uid_full="proto:reference-test",
                id_short="p_ref0001",
                run_uid_full="run:raw-reference-test",
                slab_a_uid_full=slab_rows[0].uid_full,
                slab_b_uid_full=slab_rows[1].uid_full,
                payload_json=json.dumps(
                    {"metrics": {"interface_area_A2": 10.0}}
                ),
            )
        )

        active.followups.upsert_many(
            [
                FollowupResult(
                    uid_full=raw_uid,
                    id_short="f_refraw1",
                    run_uid_full="run:raw-reference-test",
                    prototype_uid_full="proto:reference-test",
                    target_uid_full="interface:reference-test",
                    target_kind="interface",
                    kind="energy_stage",
                    best_energy=-7.0,
                    n_points=1,
                    payload=raw_energy_payload(-7.0),
                ),
                FollowupResult(
                    uid_full=reference_a_uid,
                    id_short="f_ref000a",
                    run_uid_full="run:reference-test",
                    prototype_uid_full="proto:reference-test",
                    target_uid_full="interface:reference-test",
                    target_kind="interface",
                    kind="reference_energy",
                    best_energy=-2.0,
                    param1=-1.0,
                    param2=2.0,
                    n_points=0,
                    payload=reference_energy_payload(
                        reference_uid_full="reference:bulk-a",
                        reference_kind="strained_bulk_a",
                        formula_id="interface_excess_strained_bulk",
                        energy_eV=-2.0,
                        energy_eV_per_formula_unit=-1.0,
                        reference_formula_units=2,
                        interface_formula_units=2,
                    ),
                ),
                FollowupResult(
                    uid_full=reference_b_uid,
                    id_short="f_ref000b",
                    run_uid_full="run:reference-test",
                    prototype_uid_full="proto:reference-test",
                    target_uid_full="interface:reference-test",
                    target_kind="interface",
                    kind="reference_energy",
                    best_energy=-4.0,
                    param1=-2.0,
                    param2=1.0,
                    n_points=0,
                    payload=reference_energy_payload(
                        reference_uid_full="reference:bulk-b",
                        reference_kind="strained_bulk_b",
                        formula_id="interface_excess_strained_bulk",
                        energy_eV=-4.0,
                        energy_eV_per_formula_unit=-2.0,
                        reference_formula_units=2,
                        interface_formula_units=1,
                    ),
                ),
            ]
        )

    return raw_uid, reference_a_uid, reference_b_uid


def test_target_indexed_references_roundtrip_with_lineage(schema_uow_factory) -> None:
    uow = schema_uow_factory("reference-energy.sqlite")
    try:
        raw_uid, reference_a_uid, reference_b_uid = _seed_energy_rows(uow)
        references = {
            "mode": "by_target_uid",
            "reference_run_uid_full": "run:reference-test",
            "formula_id": "interface_excess_strained_bulk",
            "by_target_uid": {
                "interface:reference-test": {
                    "bulk_a_eV_per_formula_unit": -1.0,
                    "bulk_b_eV_per_formula_unit": -2.0,
                    "n_formula_units_a": 2,
                    "n_formula_units_b": 1,
                    "metadata": {
                        "reference_run_uid_full": "run:reference-test",
                        "reference_result_uids": {
                            "strained_bulk_a": reference_a_uid,
                            "strained_bulk_b": reference_b_uid,
                        },
                        "source": "calm.reference_energy.v3",
                        "compatibility_source": (
                            "calculated_reference_workflow"
                        ),
                        "energy_backend": "deterministic",
                        "backend_identity": {"name": "deterministic"},
                        "energy_settings": {"mode": "single_point"},
                        "formula_id": "interface_excess_strained_bulk",
                        "reference_area_A2": 10.0,
                    },
                }
            },
        }

        run, results = ThermodynamicOrchestrator(uow).run_stage(
            raw_energy_results=[raw_uid],
            convention={
                "formula": "interface_excess_strained_bulk",
                "quantity": "interface_excess_energy",
                "n_interfaces": 2,
                "area_source": "prototype_interface_area",
            },
            references=references,
            resume=False,
            partial_resume=False,
        )

        assert run.status == "done"
        assert len(results) == 1
        assert results[0].status == "completed"
        assert results[0].value_eV_per_A2 == -0.15

        with uow as active:
            derived = active.followups.get_by_uid_full(results[0].followup_uid)
            edges = active.edges.list(
                dst_uid_full=results[0].followup_uid,
                kind="reference_to_thermodynamic",
            )
            reference_row = active.followups.get_by_uid_full(reference_a_uid)

        assert derived is not None
        assert derived.payload["source"] == {
            "raw_energy_followup_uid": raw_uid,
            "reference_mode": "by_target_uid",
            "reference_run_uid_full": "run:reference-test",
        }
        assert {
            (edge.src_uid_full, edge.payload["reference_kind"])
            for edge in edges
        } == {
            (reference_a_uid, "strained_bulk_a"),
            (reference_b_uid, "strained_bulk_b"),
        }

        typed_reference = ProjectReferenceEnergyResult.from_item(reference_row)
        assert typed_reference.source_interface_uid_full == "interface:reference-test"
        assert typed_reference.energy_eV_per_formula_unit == -1.0
    finally:
        uow.engine.dispose()


def test_calculator_mismatch_persists_exact_failed_thermodynamic_row(
    schema_uow_factory,
) -> None:
    uow = schema_uow_factory("reference-energy-mismatch.sqlite")
    try:
        raw_uid, reference_a_uid, reference_b_uid = _seed_energy_rows(uow)
        references = {
            "mode": "by_target_uid",
            "reference_run_uid_full": "run:reference-test",
            "formula_id": "interface_excess_strained_bulk",
            "by_target_uid": {
                "interface:reference-test": {
                    "bulk_a_eV_per_formula_unit": -1.0,
                    "bulk_b_eV_per_formula_unit": -2.0,
                    "n_formula_units_a": 2,
                    "n_formula_units_b": 1,
                    "metadata": {
                        "reference_run_uid_full": "run:reference-test",
                        "reference_result_uids": {
                            "strained_bulk_a": reference_a_uid,
                            "strained_bulk_b": reference_b_uid,
                        },
                        "source": "calm.reference_energy.v3",
                        "compatibility_source": (
                            "calculated_reference_workflow"
                        ),
                        "energy_backend": "different",
                        "backend_identity": {"name": "different"},
                        "energy_settings": {"mode": "single_point"},
                        "formula_id": "interface_excess_strained_bulk",
                        "reference_area_A2": 10.0,
                    },
                }
            },
        }

        run, results = ThermodynamicOrchestrator(uow).run_stage(
            raw_energy_results=[raw_uid],
            convention={
                "formula": "interface_excess_strained_bulk",
                "quantity": "interface_excess_energy",
                "n_interfaces": 2,
                "area_source": "prototype_interface_area",
            },
            references=references,
            resume=False,
            partial_resume=False,
        )

        assert run.status == "failed"
        assert len(results) == 1
        assert results[0].status == "failed"
        assert "different backends" in str(results[0].reason)

        with uow as active:
            persisted = active.followups.get_by_uid_full(
                results[0].followup_uid
            )
        assert persisted is not None
        assert persisted.payload["references"]["status"] == "resolved"
        assert persisted.payload["calculator_compatibility"] == {
            "status": "unresolved",
            "reason": (
                "thermodynamic_derivation_failed_before_calculator_"
                "compatibility_verification"
            ),
        }
        assert persisted.payload["failure"]["exception_type"] == "ValueError"
    finally:
        uow.engine.dispose()
