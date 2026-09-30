"""Current project surface-control validation guardrails."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"surface_symmetry_mode": "fallback"}, ValueError),
        ({"surface_symprec": True}, TypeError),
        ({"surface_angle_tolerance": -1.0}, ValueError),
        ({"surface_metric_tolerance": "1e-5"}, TypeError),
    ],
)
def test_prototype_search_service_validates_symmetry_controls_before_run(
    kwargs,
    error_type,
) -> None:
    from calm.project.application.prototypes import PrototypeSearchService

    service = PrototypeSearchService(uow_factory=lambda: None)
    with pytest.raises(error_type):
        service.start_search(
            slab_a="slab:A",
            slab_b="slab:B",
            **kwargs,
        )

def test_selected_slab_rebuild_rejects_malformed_symmetry_provenance() -> None:
    from calm.project.application.slabs import _build_selected_slab_atoms

    with pytest.raises(TypeError, match="surface_symmetry provenance"):
        _build_selected_slab_atoms(
            bulk_obj=object(),
            miller=(0, 0, 1),
            layers=4,
            vacuum=10.0,
            reduce_inplane=True,
            center_slab=True,
            termination_shift=1,
            termination_metadata={"surface_symmetry": "identity_only"},
            target_width=None,
            width_tolerance=1e-4,
            max_n_layers=10,
        )
