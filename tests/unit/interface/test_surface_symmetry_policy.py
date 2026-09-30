from __future__ import annotations

import numpy as np
import pytest

from calm.symmetry.surface_resolver import resolve_surface_pointgroup_2d
from calm.exceptions import SurfaceSymmetryDiscoveryError
from calm.interface.config import PrototypeSearchConfig


class LightweightSlab:
    pass


def test_discovery_failure_is_not_silently_identity_only() -> None:
    with pytest.raises(SurfaceSymmetryDiscoveryError) as caught:
        resolve_surface_pointgroup_2d(LightweightSlab())

    provenance = caught.value.provenance
    assert provenance.status == "failed"
    assert provenance.mode == "discover"
    assert provenance.operation_count == 0
    assert provenance.failure_type
    assert "identity_only" in str(caught.value)


def test_explicit_identity_only_mode_skips_backend_and_records_policy() -> None:
    resolution = resolve_surface_pointgroup_2d(
        LightweightSlab(),
        mode="identity_only",
        symprec=2e-5,
        angle_tolerance=2e-8,
        metric_tolerance=3e-8,
    )

    assert len(resolution.operations) == 1
    np.testing.assert_array_equal(resolution.operations[0], np.eye(2, dtype=int))
    assert resolution.provenance.to_dict() == {
        "policy": "validated_surface_pointgroup",
        "policy_version": 1,
        "mode": "identity_only",
        "status": "identity_only",
        "operation_count": 1,
        "symprec": 2e-5,
        "angle_tolerance": 2e-8,
        "metric_tolerance": 3e-8,
        "max_metric_residual": 0.0,
        "backend": None,
        "backend_version": None,
        "failure_type": None,
        "failure_message": None,
    }


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"mode": "fallback"}, "surface_symmetry_mode"),
        ({"symprec": 0.0}, "symprec"),
        ({"angle_tolerance": -1.0}, "angle_tolerance"),
        ({"metric_tolerance": float("nan")}, "metric_tolerance"),
    ],
)
def test_resolution_controls_are_validated(kwargs, message) -> None:
    parameters = {"mode": "identity_only"}
    parameters.update(kwargs)
    with pytest.raises(ValueError, match=message):
        resolve_surface_pointgroup_2d(
            LightweightSlab(),
            **parameters,
        )


def test_prototype_search_config_persists_symmetry_controls() -> None:
    config = PrototypeSearchConfig(
        surface_symmetry_mode="identity_only",
        surface_symprec=2e-5,
        surface_angle_tolerance=2e-8,
        surface_metric_tolerance=3e-8,
    )
    payload = config.to_dict()
    assert payload["surface_symmetry_mode"] == "identity_only"
    assert payload["surface_symprec"] == 2e-5
    assert payload["surface_angle_tolerance"] == 2e-8
    assert payload["surface_metric_tolerance"] == 3e-8


def test_prototype_search_result_serializes_successful_symmetry_provenance() -> None:
    from calm.interface.results import PrototypeSearchResult

    resolution = resolve_surface_pointgroup_2d(
        LightweightSlab(),
        mode="identity_only",
    )
    result = PrototypeSearchResult(
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        prototypes=[],
        config=PrototypeSearchConfig(surface_symmetry_mode="identity_only"),
        surface_symmetry_a=resolution.provenance,
        surface_symmetry_b=resolution.provenance,
    )

    payload = result.to_dict(include_prototypes=False)
    assert payload["surface_symmetry_a"]["mode"] == "identity_only"
    assert payload["surface_symmetry_b"]["policy_version"] == 1
    assert result.signature()["surface_symmetry_a"]["status"] == "identity_only"


def test_legacy_result_without_symmetry_provenance_is_not_identity_only() -> None:
    from calm.interface.results import PrototypeSearchResult

    result = PrototypeSearchResult(
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        prototypes=[],
    )
    payload = result.to_dict(include_prototypes=False)

    assert payload["surface_symmetry_a"] is None
    assert payload["surface_symmetry_b"] is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"surface_symmetry_mode": "fallback"}, "surface_symmetry_mode"),
        ({"surface_symprec": 0.0}, "surface_symprec"),
        ({"surface_angle_tolerance": -1.0}, "surface_angle_tolerance"),
        ({"surface_metric_tolerance": float("inf")}, "surface_metric_tolerance"),
    ],
)
def test_prototype_search_config_rejects_invalid_symmetry_controls(
    kwargs,
    message,
) -> None:
    with pytest.raises(ValueError, match=message):
        PrototypeSearchConfig(**kwargs)


def test_public_search_settings_forward_symmetry_policy() -> None:
    from calm.public.inputs.settings import SearchSettings

    config = SearchSettings(
        surface_symmetry_mode="identity_only",
        surface_symprec=2e-5,
        surface_angle_tolerance=3e-8,
        surface_metric_tolerance=4e-5,
    ).to_internal_config()

    assert config.surface_symmetry_mode == "identity_only"
    assert config.surface_symprec == 2e-5
    assert config.surface_angle_tolerance == 3e-8
    assert config.surface_metric_tolerance == 4e-5


def test_public_projection_marks_validated_and_legacy_symmetry_records() -> None:
    from types import SimpleNamespace

    from calm.public.records.interfaces import InterfaceSearchResult

    resolution = resolve_surface_pointgroup_2d(
        LightweightSlab(),
        mode="identity_only",
    )
    validated = InterfaceSearchResult.from_internal(
        SimpleNamespace(
            prototypes=[],
            surface_symmetry_a=resolution.provenance,
            surface_symmetry_b=resolution.provenance,
        )
    )
    assert validated.metadata["surface_symmetry_status"] == "validated"
    assert validated.metadata["surface_symmetry_a"]["mode"] == "identity_only"

    legacy = InterfaceSearchResult.from_internal(SimpleNamespace(prototypes=[]))
    assert legacy.metadata["surface_symmetry_status"] == "legacy_unrecorded"
    assert "surface_symmetry_a" not in legacy.metadata
    assert "surface_symmetry_b" not in legacy.metadata


def _fake_surface_subject():
    from types import SimpleNamespace

    cell = SimpleNamespace(array=np.eye(3, dtype=float))
    return SimpleNamespace(atoms=SimpleNamespace(cell=cell))


def test_successful_backend_discovery_is_validated_and_recorded(
    monkeypatch,
) -> None:
    import sys
    from types import SimpleNamespace

    fake_adapter = SimpleNamespace(
        spglib=SimpleNamespace(__version__="test-spglib"),
        get_surface_pointgroup_ops=lambda *args, **kwargs: [
            np.eye(2, dtype=int),
            -np.eye(2, dtype=int),
        ],
    )
    monkeypatch.setitem(
        sys.modules,
        "calm.symmetry",
        SimpleNamespace(spglib_adapter=fake_adapter),
    )

    resolution = resolve_surface_pointgroup_2d(_fake_surface_subject())

    assert len(resolution.operations) == 2
    assert resolution.provenance.status == "discovered"
    assert resolution.provenance.backend == "spglib"
    assert resolution.provenance.backend_version == "test-spglib"
    assert resolution.provenance.operation_count == 2


def test_malformed_backend_group_fails_closed_with_provenance(
    monkeypatch,
) -> None:
    import sys
    from types import SimpleNamespace

    shear = np.array([[1, 1], [0, 1]], dtype=int)
    fake_adapter = SimpleNamespace(
        spglib=SimpleNamespace(__version__="test-spglib"),
        get_surface_pointgroup_ops=lambda *args, **kwargs: [
            np.eye(2, dtype=int),
            shear,
        ],
    )
    monkeypatch.setitem(
        sys.modules,
        "calm.symmetry",
        SimpleNamespace(spglib_adapter=fake_adapter),
    )

    with pytest.raises(SurfaceSymmetryDiscoveryError) as caught:
        resolve_surface_pointgroup_2d(_fake_surface_subject())

    provenance = caught.value.provenance
    assert provenance.status == "failed"
    assert provenance.backend == "spglib"
    assert provenance.backend_version == "test-spglib"
    assert provenance.failure_type == "ValueError"
    assert "inverse" in provenance.failure_message


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("symprec", True),
        ("angle_tolerance", False),
        ("metric_tolerance", "1e-5"),
    ],
)
def test_resolution_controls_reject_coercible_nonreal_values(
    name,
    value,
) -> None:
    parameters = {"mode": "identity_only", name: value}
    with pytest.raises(TypeError):
        resolve_surface_pointgroup_2d(LightweightSlab(), **parameters)


def test_result_rejects_symmetry_provenance_with_mismatched_controls() -> None:
    from calm.interface.results import PrototypeSearchResult

    resolution = resolve_surface_pointgroup_2d(
        LightweightSlab(),
        mode="identity_only",
        symprec=2e-5,
    )
    with pytest.raises(ValueError, match="symprec"):
        PrototypeSearchResult(
            slab_a_uid="slab:A",
            slab_b_uid="slab:B",
            prototypes=[],
            config=PrototypeSearchConfig(
                surface_symmetry_mode="identity_only",
                surface_symprec=1e-5,
            ),
            surface_symmetry_a=resolution.provenance,
            surface_symmetry_b=resolution.provenance,
        )


def test_public_projection_rejects_one_sided_symmetry_provenance() -> None:
    from types import SimpleNamespace

    from calm.public.records.interfaces import InterfaceSearchResult

    resolution = resolve_surface_pointgroup_2d(
        LightweightSlab(),
        mode="identity_only",
    )
    with pytest.raises(ValueError, match="incomplete"):
        InterfaceSearchResult.from_internal(
            SimpleNamespace(
                prototypes=[],
                surface_symmetry_a=resolution.provenance,
                surface_symmetry_b=None,
            )
        )
