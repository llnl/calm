"""Ownership guardrails for oriented-slab sidecar compatibility."""

from __future__ import annotations

from dataclasses import MISSING, fields
from pathlib import Path

from calm.slab.oriented.builder import OrientedSlabTransforms as KernelTransforms


ROOT = Path(__file__).resolve().parents[2]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_version_one_sidecar_compatibility_has_a_separate_parser() -> None:
    schema = _source("calm/slab/oriented/transforms.py")
    sidecar = _source("calm/slab/oriented/sidecar.py")
    model = _source("calm/slab/oriented/model.py")
    slab = _source("calm/slab/slab.py")
    record = _source("calm/project/domain/contracts/slab_record.py")

    assert "ORIENTED_SLAB_TRANSFORMS_VERSION = 1" in schema
    assert "def from_transforms_payload" in schema
    assert "def from_transforms_sidecar_payload" in schema
    assert "from_transforms_sidecar_payload(payload)" in sidecar
    assert "from_transforms_sidecar_payload" not in model
    assert "from_transforms_sidecar_payload" not in slab
    assert "from_transforms_payload" in record


def test_bounded_gauge_policy_has_one_production_literal_owner() -> None:
    paths = tuple((ROOT / "calm").rglob("*.py"))
    assignments = []
    literals = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        if 'BOUNDED_SURFACE_GAUGE_POLICY = "bounded_surface_gauges"' in source:
            assignments.append(path.relative_to(ROOT).as_posix())
        if '"bounded_surface_gauges"' in source:
            literals.append(path.relative_to(ROOT).as_posix())

    assert assignments == ["calm/slab/oriented/transforms.py"]
    assert literals == ["calm/slab/oriented/transforms.py"]


def test_current_kernel_provenance_cannot_omit_construction_controls() -> None:
    field = next(
        item for item in fields(KernelTransforms) if item.name == "construction_controls"
    )

    assert field.default is MISSING
    assert field.default_factory is MISSING

    builder = _source("calm/slab/oriented/builder.py")
    assert 'construction_controls=d["construction_controls"]' in builder
    assert "Older payloads omit this field" not in builder
    assert "canonical_construction_controls(self.construction_controls)" in builder


def test_current_compact_writer_revalidates_kernel_controls() -> None:
    model = _source("calm/slab/oriented/model.py")
    projection = model.split("def _kernel_transforms_to_payload", 1)[1].split(
        "def _attach_transforms_payload",
        1,
    )[0]

    assert "from_transforms_payload(payload).payload" in projection
