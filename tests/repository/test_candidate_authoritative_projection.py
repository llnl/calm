from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from calm.public.persistence.repository import PublicRepository
from calm.public.persistence.adapter import WorkspaceAdapter


class _PrototypeWorkspace:
    def __init__(self) -> None:
        self.prototype = SimpleNamespace(
            uid_full="proto:x",
            id_short="p_x",
            run_uid_full="run:1",
            run_id_short="r_1",
            slab_a_uid_full="slab:a",
            slab_a_id_short="s_a",
            slab_b_uid_full="slab:b",
            slab_b_id_short="s_b",
            match_score=0.2,
            hencky_norm=math.sqrt(2.0) * 0.02633,
            interface_area=9.0,
            natoms=12,
            d_cell=2.0 * math.sqrt(2.0) * 0.02633,
            is_pareto=True,
            pareto_rank=0,
            payload={
                "miller_a": [1, 0, 0],
                "miller_b": [1, 1, 0],
                "metrics": {
                    "d_area": 2.0 * math.sqrt(2.0) * 0.02633,
                    "d_shape": 0.0,
                },
            },
        )
        self.search = SimpleNamespace(
            name="screen",
            search_identity="interface_search:test",
            run_uid_full="run:1",
            spec={
                "surface_a": {
                    "uid_full": "slab:a",
                    "id_short": "s_a",
                    "material": "A",
                    "miller": [1, 0, 0],
                    "termination": "A-top",
                    "termination_shift": 0,
                },
                "surface_b": {
                    "uid_full": "slab:b",
                    "id_short": "s_b",
                    "material": "B",
                    "miller": [1, 1, 0],
                    "termination": "B-top",
                    "termination_shift": 1,
                },
            },
        )

    def list_prototypes(self, *, run=None, limit=None):
        del limit
        if run is not None and run != "run:1":
            return []
        return [self.prototype]

    def list_interface_searches(self, *, limit=None):
        del limit
        return [self.search]


def test_candidate_projection_uses_only_authoritative_records() -> None:
    repository = PublicRepository(WorkspaceAdapter(_PrototypeWorkspace()))

    rows = repository.list_candidates()

    assert len(rows) == 1
    row = rows[0]
    assert row["project_prototype_uid"] == "proto:x"
    assert row["project_prototype_id"] == "p_x"
    assert row["search_name"] == "screen"
    assert row["score"] == 0.2
    assert row["material_a"] == "A"
    assert row["material_b"] == "B"
    assert row["d_area"] == pytest.approx(
        2.0 * math.sqrt(2.0) * 0.02633
    )
    assert row["d_shape"] == 0.0
    assert row["max_principal_strain"] == pytest.approx(0.02633)
    assert row["max_principal_strain"] != row["hencky_norm"]
    assert "eps1" not in row
    assert "eps2" not in row
    assert row["authority"] == "authoritative"
