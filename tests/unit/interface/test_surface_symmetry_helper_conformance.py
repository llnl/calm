from pathlib import Path

import numpy as np

from calm.interface.matching._surface_symmetry import surface_pointgroup_ops_2d

ROOT = Path(__file__).resolve().parents[3]


def test_surface_pointgroup_ops_2d_requires_explicit_identity_only_mode() -> None:
    class LightweightSlab:
        pass

    ops = surface_pointgroup_ops_2d(
        LightweightSlab(),
        mode="identity_only",
    )

    assert len(ops) == 1
    np.testing.assert_array_equal(ops[0], np.eye(2, dtype=int))


def test_surface_pointgroup_ops_2d_has_single_interface_owner() -> None:
    sources = {
        path.name: path.read_text()
        for path in [
            ROOT / "calm/interface/matching/search.py",
            ROOT / "calm/interface/pipeline.py",
            ROOT / "calm/interface/matching/_surface_symmetry.py",
        ]
    }

    assert "def surface_pointgroup_ops_2d" in sources["_surface_symmetry.py"]
    for name in ["search.py", "pipeline.py"]:
        assert "def _safe_surface_pointgroup_ops_2d" not in sources[name]
        assert "return [np.eye(2" not in sources[name]

    assert "surface_pointgroup_ops_2d" not in sources["search.py"]
    assert "find_prototypes(" in sources["pipeline.py"]
    assert "search_primitive_match_classes(" in sources["pipeline.py"]
    assert "resolve_surface_pointgroup_2d(" in sources["search.py"]
