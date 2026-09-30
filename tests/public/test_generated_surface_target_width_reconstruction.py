from __future__ import annotations

import pytest

from calm.public.records.generated_surface import GeneratedSurface
from slab_record_fixtures import current_atoms, current_slab_payload, current_slab_uid


def _surface(*, payload: dict, measured_thickness: float, layers: int = 1):
    generated = GeneratedSurface(
        id_short="s_test",
        uid_full="slab:test",
        label="test surface",
        material="A",
        miller=(1, 0, 0),
        natoms=1,
        area=9.0,
        payload=payload,
        vacuum=10.0,
        thickness=measured_thickness,
        layers=layers,
        _object=object(),
    )
    return generated.to_surface()


def test_measured_zero_thickness_does_not_become_target_width() -> None:
    surface = _surface(
        payload={"params": {"layers": 1, "vacuum": 10.0}},
        measured_thickness=0.0,
    )

    assert surface.layers == 1
    assert surface.thickness is None


def test_reconstruction_uses_persisted_target_width_not_measured_span() -> None:
    surface = _surface(
        payload={
            "params": {
                "layers": 4,
                "target_width": 8.0,
                "vacuum": 10.0,
            }
        },
        measured_thickness=8.25,
        layers=5,
    )

    assert surface.layers == 5
    assert surface.thickness == pytest.approx(8.0)


@pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
def test_invalid_persisted_target_width_fails_closed(value: float) -> None:
    generated = GeneratedSurface(
        id_short="s_test",
        uid_full="slab:test",
        label="test surface",
        material="A",
        miller=(1, 0, 0),
        natoms=1,
        area=9.0,
        payload={"params": {"target_width": value}},
        thickness=0.0,
        layers=1,
        _object=object(),
    )

    with pytest.raises(ValueError, match="finite and positive"):
        generated.to_surface()


def test_workspace_roundtrip_keeps_one_layer_surface_in_layer_mode() -> None:
    bulk_uid = "bulk:v2:test"
    miller = (1, 0, 0)
    payload = current_slab_payload(
        bulk_uid_full=bulk_uid,
        miller=miller,
        params={"layers": 1, "vacuum": 10.0},
        atoms=current_atoms(with_tilt=False),
        slab_thickness_A=0.0,
        vacuum_A=10.0,
        layers=1,
    )
    uid_full = current_slab_uid(
        bulk_uid_full=bulk_uid,
        miller=miller,
        payload=payload,
    )
    generated = GeneratedSurface.from_workspace(
        {
            "id_short": "s_test",
            "uid_full": uid_full,
            "bulk_uid_full": bulk_uid,
            "bulk_id_short": "b_test",
            "material": "A",
            "miller": miller,
            "payload": payload,
        }
    )

    assert generated.thickness == pytest.approx(0.0)
    surface = generated.to_surface()
    assert surface.layers == 1
    assert surface.thickness is None
