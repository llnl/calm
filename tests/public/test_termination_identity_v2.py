from __future__ import annotations

from types import SimpleNamespace

import pytest

from calm.public.projections.slab import normalize_slab_row
from calm.public.records.generated_surface import GeneratedSurface
from calm.public.records.surfaces import Surface
from calm.slab.oriented import terminations as termination_enumeration
from slab_record_fixtures import (
    current_slab_payload,
    current_surface_symmetry,
    current_termination_identity,
)


class _FakeSlab:
    def get_chemical_formula(self):
        return "AB"

    def __len__(self):
        return 2


def _identity(name: str, orientation: str = "plus_surface_normal"):
    return {
        "version": 2,
        "scheme": "decorated_periodic_halfspace_v2",
        "orientation": orientation,
        "digest": f"sha256:{name}",
    }


def _surface_symmetry(mode: str = "identity_only"):
    return {
        "policy": "validated_surface_pointgroup",
        "policy_version": 1,
        "mode": mode,
        "status": "identity_only" if mode == "identity_only" else "discovered",
        "operation_count": 1,
        "symprec": 2e-5,
        "angle_tolerance": 3e-8,
        "metric_tolerance": 4e-5,
        "max_metric_residual": 0.0,
        "backend": None if mode == "identity_only" else "spglib",
        "backend_version": None if mode == "identity_only" else "test",
        "failure_type": None,
        "failure_message": None,
    }


def test_normalized_v2_identity_preserves_versioned_pair_fields():
    identity = current_termination_identity("top")
    row = normalize_slab_row(
        {
            "uid_full": "slab:v2",
            "id_short": "s_v2",
            "bulk_uid_full": "bulk:m",
            "bulk_id_short": "b_m",
            "miller": (0, 0, 1),
            "payload": current_slab_payload(
                bulk_uid_full="bulk:m",
                miller=(0, 0, 1),
                label="A",
                top="A",
                bottom="B",
                identity=identity,
            ),
        }
    )

    assert row["termination_identity_version"] == 2
    assert row["termination_identity_status"] == "versioned"
    assert row["termination_identity"] == identity["primary"]
    assert row["termination_top_identity"] == identity["top"]
    assert row["termination_bottom_identity"] == identity["bottom"]
    assert row["termination_pair_identity"] == identity["pair"]

    generated = GeneratedSurface.from_workspace(row)
    assert generated.termination_identity_version == 2
    assert generated.termination_pair_identity == identity["pair"]
    assert generated.termination_surface_symmetry == current_surface_symmetry()
    assert generated.termination_surface_symmetry_status == "validated"


def test_unversioned_legacy_identity_is_rejected():
    with pytest.raises(ValueError, match="missing required current field"):
        normalize_slab_row(
            {
                "uid_full": "slab:v1",
                "id_short": "s_v1",
                "bulk_uid_full": "bulk:m",
                "bulk_id_short": "b_m",
                "miller": (0, 0, 1),
                "payload": {"termination_identity": [[['A', 1]]]},
            }
        )


def test_invalid_persisted_surface_symmetry_is_rejected():
    identity = current_termination_identity("bad")
    identity["surface_symmetry"] = {
        "policy": "validated_surface_pointgroup",
        "policy_version": 1,
        "mode": "identity_only",
    }
    with pytest.raises((TypeError, ValueError)):
        current_slab_payload(
            bulk_uid_full="bulk:m",
            miller=(0, 0, 1),
            label="A",
            top="A",
            bottom="B",
            identity=identity,
        )


def test_surface_termination_table_exposes_v2_identity_metadata(monkeypatch):
    top = _identity("top")
    bottom = _identity("bottom", "minus_surface_normal")
    pair = {
        "version": 2,
        "scheme": "ordered_termination_pair_v2",
        "digest": "sha256:pair",
    }
    enumerated = [
        termination_enumeration.EnumeratedTermination(
            slab=_FakeSlab(),
            label="A",
            shift=0,
            metadata={
                "termination_identity_version": 2,
                "termination_identity": top,
                "termination_top_identity": top,
                "termination_bottom_identity": bottom,
                "termination_pair_identity": pair,
                "decorated_stacking_period_layers": 3,
                "stacking_translation_order": 3,
                "cut_fractional": 0.5,
                "surface_symmetry": _surface_symmetry(),
            },
        )
    ]
    monkeypatch.setattr(Surface, "to_bulk", lambda self: object())
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        lambda *args, **kwargs: enumerated,
    )
    monkeypatch.setattr(
        termination_enumeration,
        "_cluster_atoms_by_z",
        lambda atoms, tolerance: [
            SimpleNamespace(composition="B"),
            SimpleNamespace(composition="A"),
        ],
    )

    row = Surface(object(), miller=(0, 0, 1), layers=4).terminations()[0]

    assert row["top_species"] == "A"
    assert row["bottom_species"] == "B"
    assert row["termination_identity_version"] == 2
    assert row["termination_identity"] == top
    assert row["termination_pair_identity"] == pair
    assert row["decorated_stacking_period_layers"] == 3
    assert row["surface_symmetry"] == _surface_symmetry()


def test_with_termination_preserves_v2_identity_metadata(monkeypatch):
    top = _identity("top")
    pair = {
        "version": 2,
        "scheme": "ordered_termination_pair_v2",
        "digest": "sha256:pair",
    }
    enumerated = [
        termination_enumeration.EnumeratedTermination(
            slab=_FakeSlab(),
            label="A",
            shift=1,
            metadata={
                "termination_identity_version": 2,
                "termination_identity": top,
                "termination_top_identity": top,
                "termination_bottom_identity": _identity(
                    "bottom",
                    "minus_surface_normal",
                ),
                "termination_pair_identity": pair,
                "surface_symmetry": _surface_symmetry(),
            },
        )
    ]
    monkeypatch.setattr(Surface, "to_bulk", lambda self: object())
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        lambda *args, **kwargs: enumerated,
    )

    selected = Surface(object(), miller=(0, 0, 1), layers=4).with_termination(1)

    assert selected.termination == "A"
    assert selected.termination_shift == 1
    assert selected.termination_identity_version == 2
    assert selected.termination_identity == top
    assert selected.termination_pair_identity == pair
    assert selected.termination_surface_symmetry == _surface_symmetry()


def test_with_termination_rejects_ambiguous_composition_label(monkeypatch):
    enumerated = [
        termination_enumeration.EnumeratedTermination(
            slab=_FakeSlab(),
            label="X₂",
            shift=0,
            metadata={
                "termination_identity_version": 2,
                "termination_identity": _identity("first"),
            },
        ),
        termination_enumeration.EnumeratedTermination(
            slab=_FakeSlab(),
            label="X₂",
            shift=1,
            metadata={
                "termination_identity_version": 2,
                "termination_identity": _identity("second"),
            },
        ),
    ]
    monkeypatch.setattr(Surface, "to_bulk", lambda self: object())
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        lambda *args, **kwargs: enumerated,
    )

    surface = Surface(object(), miller=(0, 0, 1), layers=4)
    with pytest.raises(ValueError, match="ambiguous"):
        surface.with_termination("X₂")

    selected = surface.with_termination("sha256:second")
    assert selected.termination_shift == 1
    assert selected.termination_identity == _identity("second")


def test_surface_termination_methods_forward_declared_symmetry_controls(
    monkeypatch,
):
    captured: list[dict[str, object]] = []
    enumerated = [
        termination_enumeration.EnumeratedTermination(
            slab=_FakeSlab(),
            label="A",
            shift=0,
            metadata={
                "termination_identity_version": 2,
                "termination_identity": _identity("A"),
                "surface_symmetry": _surface_symmetry(),
            },
        )
    ]

    def fake_enumerate(*args, **kwargs):
        captured.append(dict(kwargs))
        return enumerated

    monkeypatch.setattr(Surface, "to_bulk", lambda self: object())
    monkeypatch.setattr(
        termination_enumeration,
        "enumerate_all_terminations",
        fake_enumerate,
    )
    monkeypatch.setattr(
        termination_enumeration,
        "_cluster_atoms_by_z",
        lambda atoms, tolerance: [],
    )

    surface = Surface(object(), miller=(0, 0, 1), layers=4, symprec=9e-5)
    surface.terminations(
        surface_symmetry_mode="identity_only",
        surface_angle_tolerance=3e-8,
        surface_metric_tolerance=4e-5,
    )
    surface.with_termination(0, surface_symprec=2e-5)

    first, second = captured
    assert first["surface_symmetry_mode"] == "identity_only"
    assert first["surface_symprec"] == 9e-5
    assert first["surface_angle_tolerance"] == 3e-8
    assert first["surface_metric_tolerance"] == 4e-5
    assert second["surface_symprec"] == 2e-5
