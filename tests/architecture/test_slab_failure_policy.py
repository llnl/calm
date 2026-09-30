from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _function_source(relative: str, start: str, end: str) -> str:
    source = (ROOT / relative).read_text(encoding="utf-8")
    return source.split(start, 1)[1].split(end, 1)[0]


def test_atomistic_slab_builder_has_no_best_effort_exception_fallback() -> None:
    source = _function_source(
        "calm/project/application/slabs.py",
        "def _build_slab_atoms_if_available",
        "def _normalized_slab_build_params",
    )

    assert "except Exception" not in source
    assert "Failed to build slab atoms" not in source
    assert "return None" in source
    assert "if atoms_dict is None" in source


def test_slab_metadata_and_magnetism_do_not_swallow_failures() -> None:
    source = (ROOT / "calm/slab/slab.py").read_text(encoding="utf-8")
    init_source = source.split("def __init__", 1)[1].split("@classmethod", 1)[0]
    stamp_source = source.split("def _stamp_metadata", 1)[1].split(
        "@staticmethod", 1
    )[0]

    assert "except Exception" not in init_source
    assert "except Exception" not in stamp_source
    assert "warnings.warn" not in stamp_source


def test_slab_optional_imports_are_bounded_and_actionable() -> None:
    oriented = (ROOT / "calm/slab/oriented/builder.py").read_text(
        encoding="utf-8"
    )
    transforms = (ROOT / "calm/slab/oriented/transforms.py").read_text(
        encoding="utf-8"
    )
    tilt = (ROOT / "calm/slab/oriented/tilt.py").read_text(
        encoding="utf-8"
    )

    assert "except ImportError" in oriented
    assert "optional_dependency_error" in oriented
    assert "except Exception" not in oriented.split(
        "try:\n    from ase import Atoms", 1
    )[1].split("ArrayF", 1)[0]
    assert "except Exception" not in transforms
    assert "except Exception" not in tilt
