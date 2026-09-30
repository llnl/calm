from __future__ import annotations

from pathlib import Path


def _pareto_points() -> list[dict[str, float | str]]:
    return [
        {"uid": "A", "n_atoms_interface": 1.0, "d_cell": 2.0},
        {"uid": "B", "n_atoms_interface": 2.0, "d_cell": 1.0},
    ]


def test_pareto_plot_export_uses_canonical_savepath(tmp_path: Path) -> None:
    import inspect

    import calm.api as api
    from calm.viz._save import coerce_savepath
    from calm.viz.pareto import plot_pareto_2d

    assert "plot_pareto_2d" not in api.PUBLIC_EXPORTS
    assert "viz" not in api.PUBLIC_EXPORTS

    parameters = inspect.signature(plot_pareto_2d).parameters
    assert "save" not in parameters
    assert "filename" not in parameters
    assert "front_line" not in parameters
    assert "group_front_color" not in parameters

    assert set(inspect.signature(coerce_savepath).parameters) == {"savepath"}

    savepath_out = tmp_path / "pareto_savepath.png"
    fig, _ax = plot_pareto_2d(
        _pareto_points(),
        pareto=None,
        x="n_atoms_interface",
        y="d_cell",
        savepath=savepath_out,
        show=False,
    )
    assert savepath_out.exists()
    fig.clear()
