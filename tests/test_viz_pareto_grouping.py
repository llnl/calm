from __future__ import annotations

import numpy as np

from calm.viz.pareto import plot_pareto_2d


def _make_row(uid: str, x: float, y: float, search: str):
    return {"uid": uid, "n_atoms_interface": x, "d_cell": y, "search_name": search}


def test_grouped_scatter_and_legend():
    rows = [
        _make_row("a", 100, 0.2, "s1"),
        _make_row("b", 200, 0.15, "s1"),
        _make_row("c", 150, 0.18, "s2"),
        _make_row("d", 300, 0.12, "s2"),
    ]

    fig, ax = plot_pareto_2d(rows, x="n_atoms_interface", y="d_cell", group_by="search_name", front_scope="global", show=False)

    # Exactly one scatter collection is created for each group.
    collections = [c for c in ax.collections if len(c.get_offsets()) > 0]
    assert len(collections) == 2

    # Legend should list group labels
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "s1" in labels or any("s1" in l for l in labels)
    assert "s2" in labels or any("s2" in l for l in labels)


def test_per_group_fronts_drawn():
    rows = [
        _make_row("a", 100, 0.2, "g1"),
        _make_row("b", 200, 0.15, "g1"),
        _make_row("c", 150, 0.18, "g2"),
        _make_row("d", 300, 0.12, "g2"),
    ]

    fig, ax = plot_pareto_2d(rows, x="n_atoms_interface", y="d_cell", group_by="search_name", front_scope="per_group", show=False)

    # lines correspond to front segments; expect at least one line per group
    assert len(ax.lines) >= 2


def test_group_order_preserves_unlisted_present_groups() -> None:
    rows = [
        _make_row("a", 100, 0.2, "s1"),
        _make_row("b", 200, 0.15, "s2"),
        _make_row("c", 150, 0.18, "s3"),
    ]

    _fig, ax = plot_pareto_2d(
        rows,
        x="n_atoms_interface",
        y="d_cell",
        group_by="search_name",
        group_order=("s2",),
        group_label_format="group_key",
        show_front=False,
        show=False,
    )

    labels = [text.get_text() for text in ax.get_legend().get_texts()]
    assert labels == ["s2", "s1", "s3"]


def test_grouped_plot_uses_explicit_global_front_and_legend_title() -> None:
    rows = [
        _make_row("a", 100, 0.30, "s1"),
        _make_row("b", 200, 0.20, "s1"),
        _make_row("c", 300, 0.10, "s2"),
    ]
    explicit = [rows[0], rows[2]]

    _fig, ax = plot_pareto_2d(
        rows,
        pareto=explicit,
        x="n_atoms_interface",
        y="d_cell",
        group_by="search_name",
        group_label_format="group_key",
        front_scope="global",
        legend_title="Search space",
        show=False,
    )

    assert len(ax.lines) == 1
    assert list(ax.lines[0].get_xdata()) == [100.0, 300.0]
    assert ax.get_legend().get_title().get_text() == "Search space"


def test_both_scope_draws_group_steps_then_global_step() -> None:
    rows = [
        _make_row("a", 100, 0.30, "s1"),
        _make_row("b", 200, 0.20, "s1"),
        _make_row("c", 150, 0.25, "s2"),
        _make_row("d", 300, 0.10, "s2"),
    ]

    _fig, ax = plot_pareto_2d(
        rows,
        pareto=rows,
        x="n_atoms_interface",
        y="d_cell",
        group_by="search_name",
        group_order=("s1", "s2"),
        group_label_format="group_key",
        group_styles={
            "s1": {"color": "tab:blue"},
            "s2": {"color": "tab:orange"},
        },
        front_scope="both",
        front_style="step",
        front_plot_style=None,
        global_front_color="k",
        show=False,
    )

    # One local staircase per search plus one aggregate staircase.
    assert len(ax.lines) == 3
    assert [line.get_color() for line in ax.lines] == [
        "tab:blue",
        "tab:orange",
        "k",
    ]

    # The aggregate front is deliberately drawn last so it remains visible
    # where local and global envelopes coincide.
    np.testing.assert_allclose(
        ax.lines[-1].get_xdata(),
        np.asarray([100.0, 150.0, 150.0, 200.0, 200.0, 300.0, 300.0]),
    )
    np.testing.assert_allclose(
        ax.lines[-1].get_ydata(),
        np.asarray([0.30, 0.30, 0.25, 0.25, 0.20, 0.20, 0.10]),
    )
