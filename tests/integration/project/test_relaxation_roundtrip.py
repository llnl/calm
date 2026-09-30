from __future__ import annotations

import pytest

pytest.importorskip("ase")

from test_helpers import make_test_interface_prototype
from calm.public.project import open_project
from calm.public.inputs.settings import RelaxSettings


def test_typed_relaxation_roundtrip_resume_and_changed_settings(tmp_path) -> None:
    project = open_project(tmp_path)
    mapping = project._workspace.persist_interface_prototypes(
        [
            make_test_interface_prototype(prototype_uid="relaxation_roundtrip", miller_a=(1, 0, 0), miller_b=(1, 0, 0), n_atoms_interface=2)
        ]
    )
    prototype_uid = next(iter(mapping.values()))["uid_full"]
    refined = project._workspace.create_derived_interface(
        prototype_uid,
        label="relaxation_registry_refined",
        stage="registry_refined",
        params={"search_name": "relaxation_search"},
    )

    settings = RelaxSettings(fmax=0.03, steps=4, relax_cell=False)
    first = project.relax_interfaces(
        [refined.uid_full],
        settings=settings,
        backend="deterministic",
        resume=True,
    )

    assert first.ok
    assert first.run.run_type == "relaxation_stage"
    assert first.run.status == "done"
    assert len(first.results) == 1
    result = first.results.records()[0]
    assert result.succeeded
    assert result.target_uid_full == refined.uid_full
    assert result.target_kind == "interface"
    assert result.relaxed_interface_uid is None
    assert result.backend == "deterministic"
    assert result.settings == settings.to_dict()
    assert result.artifact_refs
    assert len(first.relaxed_interfaces) == 0
    assert result.backend_identity["scientific_authority"] == "synthetic_test_only"

    reopened = open_project(tmp_path)
    resumed = reopened.relax_interfaces(
        [refined.uid_full],
        settings=settings,
        backend="deterministic",
        resume=True,
    )
    assert resumed.run.uid_full == first.run.uid_full
    assert len(resumed.results) == 1
    assert len(resumed.relaxed_interfaces) == 0
    assert resumed.results.records()[0].uid_full == result.uid_full

    changed = reopened.relax_interfaces(
        [refined.uid_full],
        settings=RelaxSettings(fmax=0.02, steps=4),
        backend="deterministic",
        resume=True,
    )
    assert changed.run.uid_full != first.run.uid_full
    assert len(reopened.relaxation_runs()) == 2
    assert len(reopened.relaxation_results()) == 2
    assert len(reopened.relaxed_interfaces(search_name="relaxation_search")) == 0
