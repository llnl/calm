from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_current_atoms_info_provenance_has_one_key_and_schema_owner() -> None:
    schema = _source("calm/slab/oriented/transforms.py")
    wrapper = _source("calm/slab/slab.py")

    assert 'ORIENTED_SLAB_TRANSFORMS_INFO_KEY = "calm_oriented_slab_transforms"' in schema
    assert "calm_oriented_slab_transforms_json" not in wrapper
    assert "backend=\"legacy\"" not in wrapper
    assert "ORIENTED_SLAB_TRANSFORMS_BACKEND" not in wrapper
    assert "ORIENTED_SLAB_TRANSFORMS_SCHEMA_VERSION" not in wrapper


def test_current_transform_parser_rejects_retired_alias_vocabulary() -> None:
    schema = _source("calm/slab/oriented/transforms.py")

    for key in (
        '"schema_version"',
        '"miller"',
        '"miller_index"',
        '"U_slab_from_conv"',
        '"U_conv_to_slab"',
        '"transforms"',
        '"backend"',
    ):
        assert key in schema
    assert "Historical oriented-slab transform keys are unsupported" in schema
    assert "_original_version" not in schema


def test_current_frame_mapping_does_not_infer_historical_rotation_or_shear() -> None:
    source = _source("calm/interface/refinement/analysis.py")
    function = source.split(
        "def slab_to_conventional_cartesian_map_from_payload", 1
    )[1].split("def _mapped_direction_arrays", 1)[0]

    assert "from_transforms_payload" in function
    assert 'current["M_slab_to_conv_cart"]' in function
    assert 'current["M_conv_to_slab_cart"]' in function
    assert "shear_info" not in function
    assert "R_conv_to_slab" not in function
    assert 'transforms.get("U")' not in function


def test_all_current_slab_writers_attach_the_canonical_payload() -> None:
    slab = _source("calm/slab/slab.py")
    terminations = _source("calm/slab/oriented/terminations.py")

    assert "from calm.slab.oriented.model import" in slab
    assert terminations.count(
        "from calm.slab.oriented.model import build_oriented_slab"
    ) == 2
    assert "from calm.slab.oriented.builder import build_oriented_slab" not in terminations


def test_workspace_validation_fails_closed_on_missing_or_historical_provenance() -> None:
    source = _source("calm/project/application/workspace_validation.py")
    function = source.split("def _check_slab_provenance", 1)[1].split(
        "def _check_orphaned_bulks", 1
    )[0]

    assert "get_oriented_slab_transforms_payload" in function
    assert 'severity="error"' in function
    assert "historical" in function
    assert "json.loads" not in function
