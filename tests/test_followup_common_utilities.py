"""Unit tests for followup common utilities.

Tests shared followup utilities in isolation.
"""

from __future__ import annotations

from pathlib import Path
import pytest


def test_resolve_followup_targets_with_prototype(tmp_path: Path):
    """Test resolve_followup_targets with prototype identifiers."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)

    # Create bulks with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    slabs = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)])
    slab_id = slabs[0].id_short

    # Need two slabs for prototype search
    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(1, 0, 0)])
    slab2_id = slabs2[0].id_short

    run = ws.start_prototype_search(slab_id, slab2_id, n_candidates=1)
    prototypes = ws.list_prototypes(run=run.id_short)

    if prototypes:
        proto_id = prototypes[0].id_short

        # Resolve prototype target
        with ws._uow_factory() as uow:
            targets = resolve_followup_targets(uow, [proto_id])

        # Should return one target
        assert len(targets) == 1
        assert targets[0]["target_kind"] == "prototype"
        assert targets[0]["target_uid_full"].startswith("proto:")
        assert targets[0]["prototype_uid_full"] == targets[0]["target_uid_full"]


def test_resolve_followup_targets_with_interface(tmp_path: Path):
    """Test resolve_followup_targets with derived interface identifiers."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)

    # Create prototypes with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    slabs = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)])
    slab_id = slabs[0].id_short

    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(1, 0, 0)])
    slab2_id = slabs2[0].id_short

    run = ws.start_prototype_search(slab_id, slab2_id, n_candidates=1)
    prototypes = ws.list_prototypes(run=run.id_short)

    if prototypes:
        proto_id = prototypes[0].id_short

        # Create derived interface from prototype
        iface = ws.create_derived_interface(
            proto_id,
            strain_alpha=0.5,
            label="test_interface"
        )

        # Resolve interface target
        with ws._uow_factory() as uow:
            targets = resolve_followup_targets(uow, [iface.id_short])

        # Should return one target
        assert len(targets) == 1
        assert targets[0]["target_kind"] == "interface"
        assert targets[0]["target_uid_full"].startswith("iface:")
        assert targets[0]["prototype_uid_full"].startswith("proto:")
        # Interface target should have underlying prototype
        assert targets[0]["target_uid_full"] != targets[0]["prototype_uid_full"]


def test_resolve_followup_targets_multiple_identifiers(tmp_path: Path):
    """Test resolve_followup_targets with multiple identifiers."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)

    # Create prototypes with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    slabs1 = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)])
    slab1_id = slabs1[0].id_short

    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(1, 0, 0)])
    slab2_id = slabs2[0].id_short

    run1 = ws.start_prototype_search(slab1_id, slab2_id, n_candidates=2)
    prototypes = ws.list_prototypes(run=run1.id_short, limit=2)

    if len(prototypes) >= 2:
        proto_ids = [p.id_short for p in prototypes[:2]]

        # Resolve multiple targets
        with ws._uow_factory() as uow:
            targets = resolve_followup_targets(uow, proto_ids)

        # Should return two targets
        assert len(targets) == 2
        assert all(t["target_kind"] == "prototype" for t in targets)


def test_resolve_followup_targets_invalid_identifier(tmp_path: Path):
    """Test resolve_followup_targets with invalid identifier."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets

    ws = open_workspace(root=tmp_path)

    # Try to resolve invalid identifier
    with ws._uow_factory() as uow:
        with pytest.raises(ValueError, match="Followups currently accept"):
            # Try with a bulk ID (not valid for followups)
            bulk = ws.add_bulk(label="Al", payload={"test": "data"})
            resolve_followup_targets(uow, [bulk.id_short])


def test_resolve_followup_targets_missing_interface(tmp_path: Path):
    """Test resolve_followup_targets with non-existent interface."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets

    ws = open_workspace(root=tmp_path)

    # Try to resolve non-existent interface
    with ws._uow_factory() as uow:
        # Create fake interface UID
        fake_iface_uid = "iface:0000000000000000000000000000000000000000000000000000000000000000"

        # Error message comes from IdResolver, not resolve_followup_targets
        with pytest.raises(KeyError, match="No entity found with uid"):
            resolve_followup_targets(uow, [fake_iface_uid])


def test_resolve_followup_targets_mixed_types(tmp_path: Path):
    """Test resolve_followup_targets with mix of prototypes and interfaces."""
    from calm.project.bootstrap import open_workspace
    from calm.project.application.followups.common import resolve_followup_targets
    from test_helpers import make_test_bulk

    ws = open_workspace(root=tmp_path)

    # Create prototypes with real atomic structures
    bulk1 = make_test_bulk(ws, "Al", "fcc", 4.05)
    slabs = ws.build_slabs(bulk1.id_short, millers=[(1, 1, 1)])
    slab_id = slabs[0].id_short

    bulk2 = make_test_bulk(ws, "Cu", "fcc", 3.61)
    slabs2 = ws.build_slabs(bulk2.id_short, millers=[(1, 0, 0)])
    slab2_id = slabs2[0].id_short

    run = ws.start_prototype_search(slab_id, slab2_id, n_candidates=2)
    prototypes = ws.list_prototypes(run=run.id_short, limit=2)

    if len(prototypes) >= 2:
        proto1_id = prototypes[0].id_short
        proto2_id = prototypes[1].id_short

        # Create interface from second prototype
        iface = ws.create_derived_interface(
            proto2_id,
            strain_alpha=0.5,
            label="test_interface"
        )

        # Resolve mixed targets
        with ws._uow_factory() as uow:
            targets = resolve_followup_targets(uow, [proto1_id, iface.id_short])

        # Should return two targets with different kinds
        assert len(targets) == 2
        assert targets[0]["target_kind"] == "prototype"
        assert targets[1]["target_kind"] == "interface"
