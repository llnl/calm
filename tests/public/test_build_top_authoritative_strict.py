from pathlib import Path

import pytest


def test_build_top_authoritative_raises_on_authoritative_builder_error(
    tmp_path: Path,
    monkeypatch,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        run_type="prototype_search",
        search_name="s1",
        prototype_payload=prototype_payload_factory(
            include_supercells=True,
        ),
    )

    from calm.public.project import open_project

    proj = open_project(str(tmp_path))
    # Patch the single internal build owner. The public facade must propagate
    # the failure rather than falling back to a second builder.
    def _fail(*args, **kwargs):
        raise RuntimeError("authoritative build failed")

    monkeypatch.setattr(
        proj._interface_builds,
        "_build_interface_model",
        _fail,
    )

    # Project construction raises instead of falling back.
    with pytest.raises(RuntimeError):
        proj.build_interfaces("s1", top=1)
