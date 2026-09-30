"""Guard the post-0336d interface, slab, and public package topology."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "calm"


def _python_names(path: Path) -> set[str]:
    return {item.name for item in path.glob("*.py")}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_interface_root_contains_only_shared_composition_modules() -> None:
    interface = PACKAGE / "interface"
    assert _python_names(interface) == {
        "__init__.py",
        "config.py",
        "model.py",
        "pipeline.py",
        "results.py",
        "types.py",
    }
    assert {
        "matching",
        "building",
        "energy",
        "refinement",
    } <= {item.name for item in interface.iterdir() if item.is_dir()}


def test_interface_implementation_owners_are_partitioned() -> None:
    interface = PACKAGE / "interface"
    assert _python_names(interface / "matching") == {
        "__init__.py",
        "_audit_trace.py",
        "_correspondence.py",
        "_orchestrator.py",
        "_pair_identity.py",
        "_surface_orbits.py",
        "_surface_symmetry.py",
        "_types.py",
        "_utils.py",
        "audit.py",
        "conditioning.py",
        "grouping.py",
        "search.py",
        "zur_mcgill.py",
    }
    assert _python_names(interface / "building") == {
        "__init__.py",
        "_geometry.py",
        "_kernel.py",
    }
    assert _python_names(interface / "energy") == {
        "__init__.py",
        "_kernel.py",
        "contract.py",
        "reference.py",
    }
    assert _python_names(interface / "refinement") == {
        "__init__.py",
        "_math.py",
        "analysis.py",
        "contract.py",
        "partition.py",
        "registry.py",
        "strain.py",
    }


def test_oriented_slab_has_one_source_package() -> None:
    slab = PACKAGE / "slab"
    assert _python_names(slab) == {"__init__.py", "slab.py"}
    assert _python_names(slab / "oriented") == {
        "__init__.py",
        "_coordination.py",
        "_lattice.py",
        "_primitive.py",
        "_thickness.py",
        "builder.py",
        "cell_contract.py",
        "model.py",
        "sidecar.py",
        "termination_identity.py",
        "terminations.py",
        "tilt.py",
        "transforms.py",
    }
    assert not any((slab / "ops").rglob("*.py"))
    assert not (slab / "_json.py").exists()


def test_public_root_is_only_the_composition_boundary() -> None:
    public = PACKAGE / "public"
    assert _python_names(public) == {"__init__.py", "errors.py", "project.py"}
    assert {
        "inputs",
        "records",
        "collections",
        "projections",
        "workflows",
        "queries",
        "persistence",
        "presentation",
    } <= {item.name for item in public.iterdir() if item.is_dir()}


def test_public_subpackages_do_not_reexport_private_umbrellas() -> None:
    public = PACKAGE / "public"
    for name in (
        "inputs",
        "records",
        "collections",
        "projections",
        "workflows",
        "queries",
        "persistence",
        "presentation",
    ):
        source = (public / name / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
            and not (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
            )
        ]
        assert imports == []
        assert "__all__" not in source


def test_retired_flat_layout_is_not_imported_by_production() -> None:
    retired = {
        "calm.interface._build_kernel",
        "calm.interface._coupled_matching_orchestrator",
        "calm.interface._energy_kernel",
        "calm.interface._matching_types",
        "calm.interface.energy_contract",
        "calm.interface.interface_energy",
        "calm.interface.registry_search",
        "calm.interface.strain_partition",
        "calm.slab._json",
        "calm.slab.ops",
        "calm.slab.oriented_slab",
        "calm.slab.oriented_slab_transforms",
        "calm.public._collections_base",
        "calm.public._energy_workflows",
        "calm.public.candidate_collections",
        "calm.public.persistent_records",
        "calm.public.repository",
        "calm.public.settings",
    }
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        for imported in _imported_modules(path):
            if imported in retired or any(
                imported.startswith(f"{module}.") for module in retired
            ):
                offenders.append(f"{path.relative_to(ROOT)}: {imported}")
    assert offenders == [], "Retired flat-layout imports found:\n" + "\n".join(offenders)


def test_public_input_and_projection_layers_do_not_start_workflows() -> None:
    public = PACKAGE / "public"
    offenders: list[str] = []
    for owner in (public / "inputs", public / "projections"):
        for path in owner.glob("*.py"):
            for imported in _imported_modules(path):
                if imported.startswith("calm.public.workflows"):
                    offenders.append(f"{path.relative_to(ROOT)}: {imported}")
    assert offenders == []
