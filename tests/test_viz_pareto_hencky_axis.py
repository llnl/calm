import numpy as np

from test_helpers import coupled_pair_metadata


def _make_proto(uid: str, *, d_cell: float = 0.2, n_atoms: int = 10):
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


def test_plot_pareto_2d_can_plot_hencky_norm_instead_of_d_cell() -> None:
    """Hencky strain norm is a derived metric: ||E_H||_F = 1/2 * d_cell."""

    from calm.viz.pareto import plot_pareto_2d

    p1 = _make_proto("proto:1", d_cell=0.2, n_atoms=10)
    p2 = _make_proto("proto:2", d_cell=0.4, n_atoms=20)

    fig, ax = plot_pareto_2d(
        [p1, p2],
        pareto=None,
        x="n_atoms_interface",
        y="hencky_norm",
        show=False,
    )

    # First collection is the candidates scatter.
    offsets = ax.collections[0].get_offsets()
    ys = np.asarray(offsets)[:, 1]

    assert np.allclose(ys, np.array([0.1, 0.2]))

    # Default axis labels are human-readable and include mathtext where
    # appropriate.
    assert ax.get_xlabel() == r"Interface cell atoms, $N_\mathrm{interface}$"
    assert ax.get_ylabel() == r"Hencky strain norm, $\|E_H\|_F$"


def test_plot_pareto_2d_title_is_optional() -> None:
    from calm.viz.pareto import plot_pareto_2d

    p = _make_proto("proto:1")

    # Explicit title, but suppressed.
    _, ax0 = plot_pareto_2d(
        [p],
        pareto=None,
        x="n_atoms_interface",
        y="d_cell",
        title="My title",
        show_title=False,
        show=False,
    )
    assert ax0.get_title() == ""

    # Explicit title, enabled.
    _, ax1 = plot_pareto_2d(
        [p],
        pareto=None,
        x="n_atoms_interface",
        y="d_cell",
        title="My title",
        show_title=True,
        show=False,
    )
    assert ax1.get_title() == "My title"
