"""Contracts for CALM's vendored two-dimensional lattice figure tool."""

from __future__ import annotations

from pathlib import Path
import sys
import tomllib
import xml.etree.ElementTree as ET

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
TOOL_ROOT = ROOT / "engineering" / "documentation" / "figures"
VENDOR_ROOT = TOOL_ROOT / "latticeplot2d"
PUBLIC_ASSET_ROOT = ROOT / "docs" / "assets" / "figures" / "lattice"
BUILD_ROOT = ROOT / "build" / "documentation-figures" / "lattice"


def _load_tool():
    pytest.importorskip("matplotlib")
    sys.path.insert(0, str(TOOL_ROOT))
    import generate_lattice_figures as generator
    import lattice_figure_recipes as recipes
    import latticeplot2d

    return generator, recipes, latticeplot2d


def _all_declared_requirements() -> tuple[str, ...]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project.get("dependencies", ()))
    for values in project.get("optional-dependencies", {}).values():
        requirements.extend(values)
    return tuple(requirements)


def test_latticeplot2d_is_vendored_tooling_not_a_calm_dependency() -> None:
    normalized = tuple(requirement.casefold() for requirement in _all_declared_requirements())
    assert all(not requirement.startswith("latticeplot2d") for requirement in normalized)
    expected_files = {
        "latticeplot2d-MIT.txt",
        "VENDORING.txt",
        "__init__.py",
        "geometry.py",
        "plotting.py",
        "style.py",
        "workflows.py",
    }
    assert {path.name for path in VENDOR_ROOT.iterdir() if path.is_file()} == expected_files
    assert (VENDOR_ROOT / "latticeplot2d-MIT.txt").read_text(encoding="utf-8").startswith("MIT License")


def test_vendored_latticeplot2d_uses_column_basis_convention() -> None:
    _, _, latticeplot2d = _load_tool()
    basis = np.array([[2.0, 0.5], [0.0, 1.5]])
    np.testing.assert_allclose(
        latticeplot2d.cell_vertices(basis),
        [[0.0, 0.0], [2.0, 0.0], [2.5, 1.5], [0.5, 1.5]],
    )
    reduction = latticeplot2d.gauss_reduce(np.array([[4.0, 1.0], [1.0, 1.0]]))
    np.testing.assert_allclose(
        reduction.reduced_basis,
        np.array([[4.0, 1.0], [1.0, 1.0]]) @ reduction.integer_transform,
    )
    assert np.linalg.det(reduction.gauged_basis) > 0.0


def test_greenfield_skeleton_keeps_legacy_recipes_out_of_public_assets() -> None:
    generator, recipes, latticeplot2d = _load_tool()
    assert generator.DEFAULT_OUTPUT == BUILD_ROOT
    assert generator.PUBLIC_OUTPUT == PUBLIC_ASSET_ROOT
    assert not PUBLIC_ASSET_ROOT.exists()
    assert set(recipes.published_recipe_map()) == {
        "cell-map-types",
        "coupled-common-cell",
        "strain-partition-path",
    }
    assert Path(latticeplot2d.__file__).resolve().is_relative_to(VENDOR_ROOT.resolve())


def test_lattice_figure_rendering_is_deterministic_and_accessible(tmp_path: Path) -> None:
    generator, recipes, _ = _load_tool()
    for recipe in recipes.recipe_map().values():
        first = generator.render_svg(recipe)
        second = generator.render_svg(recipe)
        assert first == second
        written = generator.write_figures((recipe,), output_dir=tmp_path)
        assert written == (tmp_path / recipe.filename,)
        assert generator.validate_svg(written[0], recipe) == []
        root = ET.parse(written[0]).getroot()
        assert root.attrib["data-calm-lattice-recipe"] == recipe.name
        assert not list(root.iter("{http://www.w3.org/2000/svg}image"))


def test_lattice_figure_cli_uses_explicit_preview_output(tmp_path: Path, capsys) -> None:
    generator, recipes, _ = _load_tool()
    assert generator.main(["--list"]) == 0
    assert set(capsys.readouterr().out.strip().splitlines()) == set(recipes.recipe_map())

    assert generator.main(["--output-dir", str(tmp_path)]) == 0
    capsys.readouterr()
    assert generator.main(["--check", "--output-dir", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "validated 3 lattice figures" in output

    assert generator.main([
        "--only",
        "gauss-reduction-sequence",
        "--output-dir",
        str(PUBLIC_ASSET_ROOT),
    ]) == 2
    assert "engineering-only lattice recipes" in capsys.readouterr().err


def test_vendored_coupled_match_preserves_two_net_relationships() -> None:
    _, _, latticeplot2d = _load_tool()
    import matplotlib.pyplot as plt

    primitive = np.eye(2)
    supercell_a = primitive @ np.array([[2, -1], [1, 2]])
    supercell_b = primitive @ np.array([[1, -2], [2, 1]])
    figure, axis = plt.subplots()
    try:
        result = latticeplot2d.plot_coupled_match(
            axis,
            primitive,
            primitive,
            supercell_a,
            supercell_b,
            grid_i_range=(-1, 1),
            grid_j_range=(-1, 1),
            site_i_range=(-2, 2),
            site_j_range=(-2, 2),
        )
        np.testing.assert_allclose(result.supercell_basis_a, result.common_basis)
        np.testing.assert_allclose(result.supercell_basis_b, result.common_basis)
        assert result.artists.sites_a is not None
        assert result.artists.sites_b is not None
    finally:
        plt.close(figure)


def test_vendored_strain_partition_path_applies_frame_maps() -> None:
    _, _, latticeplot2d = _load_tool()
    import matplotlib.pyplot as plt

    frames = [
        latticeplot2d.StrainPartitionFrame(
            alpha=0.0,
            common_basis=np.array([[2.0, 0.2], [0.0, 2.0]]),
            deformation_a=np.eye(2),
            deformation_b=np.array([[0.95, 0.0], [0.0, 1.05]]),
        ),
        {
            "alpha": 1.0,
            "common_basis": np.array([[2.1, 0.1], [0.0, 1.9]]),
            "deformation_a": np.array([[1.05, 0.0], [0.0, 0.95]]),
            "deformation_b": np.eye(2),
        },
    ]
    result = latticeplot2d.plot_strain_partition_path(
        np.eye(2),
        np.array([[1.05, 0.0], [0.0, 0.95]]),
        frames,
        ncols=2,
        site_i_range=(-1, 1),
        site_j_range=(-1, 1),
    )
    try:
        assert len(result.axes) == 2
        assert all(reduction is not None for reduction in result.reductions)
        assert all(artist.sites_a is not None for artist in result.artists)
        assert all(artist.sites_b is not None for artist in result.artists)
    finally:
        plt.close(result.figure)
