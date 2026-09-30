from __future__ import annotations

from calm.public.project import open_project
from slab_record_fixtures import current_slab_payload, current_slab_uid


def test_authoritative_candidate_projection_preserves_exact_surface_identity(
    tmp_path,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    slab_a_token = persisted_test_uid("slab", "slab:a-o")
    slab_b_token = persisted_test_uid("slab", "slab:b-li")
    bulk_uid = persisted_test_uid("bulk", "bulk:1")
    slab_a_payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=(1, 0, 0),
        label="O",
        shift=0,
        top="O",
        bottom="O",
        user_payload={"fixture_token": slab_a_token},
    )
    slab_b_payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=(1, 0, 0),
        label="Li",
        shift=1,
        top="Li",
        bottom="Li",
        user_payload={"fixture_token": slab_b_token},
    )
    slab_a_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=(1, 0, 0),
        payload=slab_a_payload,
    )
    slab_b_uid = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=(1, 0, 0),
        payload=slab_b_payload,
    )
    run_spec = {
        "schema_version": 2,
        "implementation": "primitive_coupled_pair_v2",
        "search_identity": "search:test:explicit_terminations",
        "surface_a": {
            "uid_full": slab_a_uid,
            "id_short": "s_a_o",
            "material": "A",
            "miller": [1, 0, 0],
            "termination": "O",
            "termination_shift": 0,
        },
        "surface_b": {
            "uid_full": slab_b_uid,
            "id_short": "s_b_li",
            "material": "B",
            "miller": [1, 0, 0],
            "termination": "Li",
            "termination_shift": 1,
        },
        "settings": {},
    }
    prototype_graph_factory(
        slab_a_uid_full=slab_a_token,
        slab_a_id_short="s_a_o",
        slab_b_uid_full=slab_b_token,
        slab_b_id_short="s_b_li",
        run_type="prototype_search",
        run_spec=run_spec,
        search_name="explicit_terminations",
        search_identity="search:test:explicit_terminations",
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    project = open_project(str(tmp_path), summarize=False)
    rows = project.search("explicit_terminations").candidates().to_rows(view="all")

    assert len(rows) == 1
    row = rows[0]
    assert row["surface_a_uid_full"] == slab_a_uid
    assert row["surface_b_uid_full"] == slab_b_uid
    assert row["surface_a_id_short"] == "s_a_o"
    assert row["surface_b_id_short"] == "s_b_li"
    assert row["termination_a"] == "O"
    assert row["termination_b"] == "Li"
    assert row["termination_shift_a"] == 0
    assert row["termination_shift_b"] == 1
    assert row["material_a"] == "A"
    assert row["material_b"] == "B"
    assert row["search_name"] == "explicit_terminations"
