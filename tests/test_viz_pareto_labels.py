from __future__ import annotations


import calm.viz.pareto as vp


def test_axis_label_mathtext_and_comma() -> None:
    # Check axis label definitions include descriptive text and a math expression
    labels = vp._AXIS_LABELS
    # Keys that should include descriptive text and mathtext
    checks = [
        ("d_cell", ", $"),
        ("d_size", ", $"),
        ("hencky_norm", ", $"),
        ("max_principal_strain", ", $"),
    ]
    for key, substr in checks:
        assert key in labels
        val = labels[key]
        assert isinstance(val, str)
        # must include a comma then a math expression starting with $
        assert substr in val, f"Expected '{substr}' in axis label for {key}: {val!r}"


def test_grouped_legend_mathtext_preserved() -> None:
    # Create a small synthetic dataset with two groups and verify legend labels
    rows = [
        {"uid": "a", "n_atoms_interface": 100, "d_cell": 0.2, "search_name": "s1", "material_a": "LiF_opt", "material_b": "Li2O_opt", "miller_a": (1, 0, 0), "miller_b": (1, 0, 0)},
        {"uid": "b", "n_atoms_interface": 200, "d_cell": 0.15, "search_name": "s1", "material_a": "LiF_opt", "material_b": "Li2O_opt", "miller_a": (1, 0, 0), "miller_b": (1, 0, 0)},
        {"uid": "c", "n_atoms_interface": 150, "d_cell": 0.18, "search_name": "s2", "material_a": "LiF_opt", "material_b": "Li2O_opt", "miller_a": (1, 1, 0), "miller_b": (1, 0, 0)},
        {"uid": "d", "n_atoms_interface": 300, "d_cell": 0.12, "search_name": "s2", "material_a": "LiF_opt", "material_b": "Li2O_opt", "miller_a": (1, 1, 0), "miller_b": (1, 0, 0)},
    ]

    fig, ax = vp.plot_pareto_2d(rows, x="n_atoms_interface", y="d_cell", group_by="search_name", front_scope="global", show=False, legend_outside=False)
    legend = ax.get_legend()
    assert legend is not None
    texts = [t.get_text() for t in legend.get_texts()]
    # Expect group labels to be mathtext strings (start and end with $) for the two groups
    group_texts = [t for t in texts if t != "Global Pareto"]
    assert len(group_texts) >= 2
    for gt in group_texts:
        assert gt.startswith("$") and gt.endswith("$"), f"Expected mathtext label, got: {gt!r}"
        # No truncated math fragments should appear
        assert "…" not in gt
