from __future__ import annotations

import pytest


def test_prototype_search_result_exposes_pareto_property() -> None:
    """PrototypeSearchResult should expose a convenient `.pareto` list.

    This is part of the public UX surface: examples and downstream tooling
    should not have to re-implement Pareto selection.
    """

    from calm.interface.config import PrototypeSearchConfig
    from calm.interface.results import PrototypeSearchResult

    cfg = PrototypeSearchConfig(k_max=1, max_results=10)

    # Two non-dominated points (trade-off), two dominated points
    pts = [
        {"prototype_uid": "A", "n_atoms_interface": 1.0, "d_cell": 2.0},
        {"prototype_uid": "B", "n_atoms_interface": 2.0, "d_cell": 1.0},
        {"prototype_uid": "C", "n_atoms_interface": 2.0, "d_cell": 2.0},  # dominated
        {"prototype_uid": "D", "n_atoms_interface": 3.0, "d_cell": 3.0},  # dominated
    ]

    res = PrototypeSearchResult(
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        config=cfg,
        prototypes=pts,  # type: ignore[arg-type]
    )

    pareto = res.pareto
    assert [p["prototype_uid"] for p in pareto] == ["A", "B"]

    pf = res.pareto_front_2d()
    assert [res.prototypes[i]["prototype_uid"] for i in pf.front_idx] == ["A", "B"]


def test_prototype_search_result_preserves_property_failures() -> None:
    from calm.interface.config import PrototypeSearchConfig
    from calm.interface.results import PrototypeSearchResult

    class BrokenPrototype:
        @property
        def slab_a_uid(self):
            raise RuntimeError("prototype property failed")

        slab_b_uid = "slab:B"

    with pytest.raises(RuntimeError, match="prototype property failed"):
        PrototypeSearchResult(
            config=PrototypeSearchConfig(k_max=1, max_results=10),
            prototypes=[BrokenPrototype()],
        )
