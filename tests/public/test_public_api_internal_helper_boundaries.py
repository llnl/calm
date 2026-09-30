from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PUBLIC_API = ROOT / "public_api.md"

_INTERNAL_HELPER_PATHS = {
    "calm.interface.building._kernel",
    "calm.interface.building._kernel._embed_2x2_in_3x3",
    "calm.interface.building._kernel.apply_deformation_gradient",
    "calm.interface.building._kernel.apply_cartesian_rotation",
    "calm.interface.matching._surface_symmetry",
    "calm.interface.matching._surface_symmetry.surface_pointgroup_ops_2d",
    "calm.serialization.scientific",
    "calm.serialization.scientific.scientific_json_native",
}

_INTERNAL_HELPER_NAMES = {
    "_embed_2x2_in_3x3",
    "apply_deformation_gradient",
    "apply_cartesian_rotation",
    "surface_pointgroup_ops_2d",
    "json_native",
}


def _public_inventory_paths() -> set[str]:
    lines = PUBLIC_API.read_text(encoding="utf-8").splitlines()
    begin = lines.index("<!-- public-api-table:begin -->") + 1
    end = lines.index("<!-- public-api-table:end -->")

    paths: set[str] = set()
    header_seen = False
    for raw in lines[begin:end]:
        line = raw.strip()
        if not line.startswith("|"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if not parts or set(parts[0]) == {"-"}:
            continue
        if not header_seen:
            header_seen = True
            assert parts[0] == "Import path"
            continue
        paths.add(parts[0])
    return paths


def test_internal_helper_owners_are_not_public_api_inventory_rows() -> None:
    paths = _public_inventory_paths()
    leaked = sorted(path for path in _INTERNAL_HELPER_PATHS if path in paths)
    assert leaked == []


def test_internal_helper_names_are_not_top_level_public_exports() -> None:
    import calm.api as api

    exported = set(api.PUBLIC_EXPORTS) | set(api.__all__)
    leaked = sorted(_INTERNAL_HELPER_NAMES & exported)
    assert leaked == []
