#!/usr/bin/env python3
"""Smoke-test one isolated installed CALM artifact environment."""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import tempfile
from importlib import metadata
from pathlib import Path


def _require_absent(names: tuple[str, ...]) -> None:
    present = [name for name in names if importlib.util.find_spec(name) is not None]
    if present:
        raise RuntimeError(
            "base installation unexpectedly contains optional modules: "
            + ", ".join(present)
        )


def _assert_installed_module(module_path: str, forbidden_source_root: Path) -> None:
    resolved = Path(module_path).resolve()
    forbidden = forbidden_source_root.resolve()
    if resolved == forbidden or forbidden in resolved.parents:
        raise RuntimeError(
            "isolated artifact smoke imported CALM from the source checkout: "
            f"{resolved}"
        )


def _base_smoke(
    expected_version: str, forbidden_source_root: Path
) -> dict[str, object]:
    import calm
    import calm.api

    if calm.__version__ != expected_version:
        raise RuntimeError(
            f"installed CALM version {calm.__version__!r} does not match "
            f"artifact version {expected_version!r}"
        )
    _assert_installed_module(calm.__file__, forbidden_source_root)
    for name in calm.api.PUBLIC_EXPORTS:
        getattr(calm, name)

    _require_absent(("ase", "spglib", "scipy", "pandas", "matplotlib", "lammps"))
    with tempfile.TemporaryDirectory(prefix="calm-install-smoke-") as root:
        project_path = Path(root) / "base-project.calm"
        project = calm.open_project(project_path)
        project.write_reproducibility_manifest(overwrite=True)
        del project
        gc.collect()
        reopened = calm.open_project(project_path)
        verification = reopened.verify_reproducibility_manifest()
        verification.raise_for_errors()
        summary = reopened.summary()

    return {
        "mode": "base",
        "version": calm.__version__,
        "module_path": str(Path(calm.__file__).resolve()),
        "project_summary": summary,
    }


def _science_smoke(
    expected_version: str, forbidden_source_root: Path
) -> dict[str, object]:
    import ase
    import numpy as np
    import scipy
    import spglib
    from ase import Atoms

    import calm

    if calm.__version__ != expected_version:
        raise RuntimeError(
            f"installed CALM version {calm.__version__!r} does not match "
            f"artifact version {expected_version!r}"
        )
    _assert_installed_module(calm.__file__, forbidden_source_root)
    atoms = Atoms(
        numbers=[3, 9],
        cell=np.eye(3) * 4.0,
        scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        pbc=True,
    )
    material = calm.Material.from_ase(atoms, name="LiF")
    if "n_atoms=2" not in material.summary():
        raise RuntimeError("science installation did not preserve the atomistic input")

    with tempfile.TemporaryDirectory(prefix="calm-science-smoke-") as root:
        project = calm.open_project(Path(root) / "science-project.calm")
        saved = project.add_material(material, name="LiF")
        restored = saved.to_ase()
        if restored is None or len(restored) != 2:
            raise RuntimeError("science installation could not round-trip ASE atoms")

    return {
        "mode": "science",
        "version": calm.__version__,
        "module_path": str(Path(calm.__file__).resolve()),
        "dependencies": {
            "ase": ase.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "spglib": spglib.__version__,
        },
    }


def _extra_smoke(
    extra: str, expected_version: str, forbidden_source_root: Path
) -> dict[str, object]:
    import calm

    if calm.__version__ != expected_version:
        raise RuntimeError("installed version does not match artifact version")
    _assert_installed_module(calm.__file__, forbidden_source_root)
    modules = {
        "dataframe": ("pandas",),
        "plot": ("matplotlib",),
        "viz": ("matplotlib", "seaborn", "plotly"),
    }[extra]
    versions = {name: metadata.version(name) for name in modules}
    return {
        "mode": extra,
        "version": calm.__version__,
        "module_path": str(Path(calm.__file__).resolve()),
        "dependencies": versions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("base", "science", "dataframe", "plot", "viz"),
        required=True,
    )
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--forbidden-source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.mode == "base":
        result = _base_smoke(args.expected_version, args.forbidden_source_root)
    elif args.mode == "science":
        result = _science_smoke(args.expected_version, args.forbidden_source_root)
    else:
        result = _extra_smoke(
            args.mode, args.expected_version, args.forbidden_source_root
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
