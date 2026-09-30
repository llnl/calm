from pathlib import Path

import pytest

from calm.project.application.interface_building import (
    build_interface_model_from_prototype,
)


def test_authoritative_build_atoms_from_prototype(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_uid = persisted_test_uid("prototype", "proto:x")
    uow = prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    with uow as uw:
        built = build_interface_model_from_prototype(
            uw,
            prototype_uid,
            alpha=0.5,
            translation_frac=(0.0, 0.0),
            z_padding=1.5,
        )
        assert built.atoms is not None
        assert len(built.atoms) > 0
        assert built.prototype_uid_full == prototype_uid


def test_authoritative_build_applies_explicit_vacuum_padding(
    tmp_path: Path,
    hydrogen_atoms_payload_factory,
    prototype_graph_factory,
    prototype_payload_factory,
    persisted_test_uid,
):
    payload = hydrogen_atoms_payload_factory()
    prototype_uid = persisted_test_uid("prototype", "proto:x")
    uow = prototype_graph_factory(
        slab_a_payload=payload,
        slab_b_payload=payload,
        prototype_payload=prototype_payload_factory(include_supercells=True),
    )

    with uow as uw:
        low = build_interface_model_from_prototype(
            uw,
            prototype_uid,
            z_padding=1.5,
            vacuum=5.0,
        )
        high = build_interface_model_from_prototype(
            uw,
            prototype_uid,
            z_padding=1.5,
            vacuum=20.0,
        )

    assert high.atoms.cell.lengths()[2] - low.atoms.cell.lengths()[2] == pytest.approx(
        15.0
    )
    assert low.spec["vacuum"] == pytest.approx(5.0)
    assert high.spec["vacuum"] == pytest.approx(20.0)
