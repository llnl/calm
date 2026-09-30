import numpy as np

from test_helpers import coupled_pair_metadata


def _make_proto(uid: str, *, d_cell: float, n_atoms: int):
    from calm.interface.model import InterfacePrototype, SupercellRecipe2D

    I = np.eye(2, dtype=int)

    sc_a = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 2), cond=1.0)
    sc_b = SupercellRecipe2D(k=1, N_tot=I, R_sup=I, hnf_key_pg=(1, 0, 0, 3), cond=1.5)

    pair_identity, source_provenance = coupled_pair_metadata(sc_a, sc_b)

    return InterfacePrototype(
        prototype_uid=uid,
        slab_a_uid="slab:A",
        slab_b_uid="slab:B",
        miller_a=(1, 1, 1),
        miller_b=(1, 1, 1),
        supercell_a=sc_a,
        supercell_b=sc_b,
        pair_identity=pair_identity,
        source_provenance=source_provenance,
        slab_a=None,  # type: ignore[arg-type]
        slab_b=None,  # type: ignore[arg-type]
        match_score=0.1,
        d_size=0.0,
        d_cell=float(d_cell),
        d_area=0.3,
        d_shape=0.4,
        rel_da=0.1,
        rel_db=0.2,
        d_gamma_deg=0.0,
        n_atoms_interface=int(n_atoms),
    )


def test_plot_pareto_2d_draws_front_line_segments() -> None:
    """The front should be drawn as connected line segments in sorted x order."""

    import inspect

    from calm.viz.pareto import plot_pareto_2d

    assert "front_line" not in inspect.signature(plot_pareto_2d).parameters

    # Candidates and Pareto points (already non-dominated).
    cands = [_make_proto(f"c{i}", d_cell=0.1 + 0.01 * i, n_atoms=100 + i) for i in range(5)]
    pareto = [_make_proto("p1", d_cell=0.2, n_atoms=200), _make_proto("p2", d_cell=0.1, n_atoms=300)]

    fig, ax = plot_pareto_2d(
        cands,
        pareto=pareto,
        x="n_atoms_interface",
        y="d_cell",
        front_style="line",
        show=False,
    )

    # There should be a single line (front) when front_style is line.
    assert len(ax.lines) == 1

    xs = ax.lines[0].get_xdata()
    # Sorted by x (n_atoms_interface).
    assert np.all(xs[:-1] <= xs[1:])

    # Labels should be human-friendly by default.
    assert ax.get_xlabel() == r"Interface cell atoms, $N_\mathrm{interface}$"
    # Axis label should include a descriptive phrase followed by the math
    # symbol rendered with LaTeX mathtext.
    assert ax.get_ylabel() == r"Cell similarity metric, $d_\mathrm{cell}$"


def test_plot_pareto_2d_draws_axis_aligned_step_front() -> None:
    """The step style should draw horizontal and vertical Pareto segments."""
    from calm.viz.pareto import plot_pareto_2d

    candidates = [
        _make_proto("p1", d_cell=0.30, n_atoms=100),
        _make_proto("p2", d_cell=0.20, n_atoms=200),
        _make_proto("p3", d_cell=0.10, n_atoms=300),
    ]

    _fig, ax = plot_pareto_2d(
        candidates,
        pareto=candidates,
        x="n_atoms_interface",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        show=False,
    )

    assert len(ax.lines) == 1
    np.testing.assert_allclose(
        ax.lines[0].get_xdata(),
        np.asarray([100.0, 200.0, 200.0, 300.0, 300.0]),
    )
    np.testing.assert_allclose(
        ax.lines[0].get_ydata(),
        np.asarray([0.30, 0.30, 0.20, 0.20, 0.10]),
    )

    # The staircase corners are a visual envelope, not additional candidates.
    # Pareto markers must therefore remain at the three attainable points.
    np.testing.assert_allclose(
        ax.collections[-1].get_offsets(),
        np.asarray(
            [
                [100.0, 0.30],
                [200.0, 0.20],
                [300.0, 0.10],
            ]
        ),
    )


def test_step_front_collapses_equal_x_objective_representatives() -> None:
    """Quantized-equal candidates must not create vertical plot artifacts."""
    from calm.viz.pareto import plot_pareto_2d

    candidates = [
        _make_proto("p1", d_cell=0.3000000000000, n_atoms=100),
        _make_proto("p1-equivalent", d_cell=0.3000000000001, n_atoms=100),
        _make_proto("p2", d_cell=0.20, n_atoms=200),
    ]

    _fig, ax = plot_pareto_2d(
        candidates,
        pareto=candidates,
        x="n_atoms_interface",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        show=False,
    )

    np.testing.assert_allclose(
        ax.lines[0].get_xdata(),
        np.asarray([100.0, 200.0, 200.0]),
    )
    np.testing.assert_allclose(
        ax.lines[0].get_ydata(),
        np.asarray([0.30, 0.30, 0.20]),
    )
    np.testing.assert_allclose(
        ax.collections[-1].get_offsets(),
        np.asarray([[100.0, 0.30], [200.0, 0.20]]),
    )


def test_step_front_draws_a_single_attainable_point() -> None:
    from calm.viz.pareto import plot_pareto_2d

    candidate = _make_proto("only", d_cell=0.15, n_atoms=120)
    _fig, ax = plot_pareto_2d(
        [candidate],
        pareto=[candidate],
        x="n_atoms_interface",
        y="d_cell",
        front_style="step",
        front_plot_style=None,
        show=False,
    )

    assert not ax.lines
    np.testing.assert_allclose(
        ax.collections[-1].get_offsets(),
        np.asarray([[120.0, 0.15]]),
    )
