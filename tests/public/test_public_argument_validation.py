from __future__ import annotations

import pytest


def test_plot_pareto_rejects_unsupported_front_and_unknown_keywords() -> None:
    from calm.public.presentation.plotting import plot_pareto

    with pytest.raises(ValueError, match="front must be"):
        plot_pareto([], front="unsupported")
    with pytest.raises(TypeError, match="Unexpected plot_pareto"):
        plot_pareto([], misspelled_option=True)
    with pytest.raises(TypeError, match="Unexpected plot_pareto"):
        plot_pareto([], front_line=True)
    with pytest.raises(TypeError, match="Unexpected plot_pareto"):
        plot_pareto([], group_front_color="C2")
    with pytest.raises(ValueError, match="Retired metric shorthand"):
        plot_pareto([], x="atoms")
    with pytest.raises(ValueError, match="Retired metric shorthand"):
        plot_pareto([], y="mismatch")


def test_plot_pareto_forwards_supported_example_styling(monkeypatch) -> None:
    from calm.public.presentation import plotting

    captured: dict[str, object] = {}
    sentinel = (object(), object())

    def fake_plot_pareto_2d(rows, **kwargs):
        captured["rows"] = rows
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(plotting, "plot_pareto_2d", fake_plot_pareto_2d)

    result = plotting.plot_pareto(
        [{"candidate_id": "C0000", "n_atoms_estimate": 10, "d_cell": 0.1}],
        x="n_atoms_estimate",
        y="d_cell",
        group_by="search_name",
        front_scope="both",
        front_plot_style="-x",
        global_front_color="k",
        legend_outside=True,
        show_title=False,
    )

    assert result is sentinel
    assert captured["x"] == "n_atoms_estimate"
    assert captured["y"] == "d_cell"
    assert captured["show_front"] is True
    assert captured["group_by"] == "search_name"
    assert captured["front_scope"] == "both"
    assert captured["front_plot_style"] == "-x"
    assert captured["global_front_color"] == "k"
    assert captured["legend_outside"] is True
    assert captured["show_title"] is False


def test_candidate_collection_rejects_unsupported_pareto_scope() -> None:
    from calm.public.collections.candidates import CandidateCollection

    collection = CandidateCollection(items=[])
    with pytest.raises(ValueError, match="authoritative"):
        collection.pareto(scope="stored")


def test_candidate_does_not_execute_registry_search() -> None:
    from calm.public.records.interfaces import InterfaceCandidate

    assert not hasattr(InterfaceCandidate, "_search_registry")

def test_collection_strain_filter_errors_are_not_silently_accepted() -> None:
    from calm.public.collections.candidates import CandidateCollection

    class BrokenFilter:
        def matches(self, row):
            raise RuntimeError("broken strain filter")

    collection = CandidateCollection(
        items=[{"candidate_id": "C0000", "d_cell": 0.01, "n_atoms_estimate": 4}]
    )
    with pytest.raises(RuntimeError, match="broken strain filter"):
        collection.strain(BrokenFilter())


def test_collection_table_rejects_retired_columns_alias() -> None:
    from calm.public.collections.candidates import CandidateCollection

    with pytest.raises(TypeError, match="columns"):
        CandidateCollection(items=[]).to_table(columns=["candidate_id"])


def test_search_interfaces_rejects_retired_direct_setting_keywords() -> None:
    from calm.public.workflows.search import search_interfaces

    with pytest.raises(TypeError, match="max_atoms"):
        search_interfaces(object(), object(), max_atoms=100)


def test_interface_model_does_not_execute_followup_workflows() -> None:
    from calm.public.records.interfaces import InterfaceModel

    assert not hasattr(InterfaceModel, "_energy")
    assert not hasattr(InterfaceModel, "_relax")


def test_candidate_ranking_rejects_retired_metric_shorthand() -> None:
    from calm.public.collections.candidates import CandidateCollection

    collection = CandidateCollection(
        prototypes=[{"candidate_id": "c1", "n_atoms_estimate": 10, "d_cell": 0.1}]
    )
    with pytest.raises(ValueError, match="Retired metric shorthand"):
        collection.select_top(1, by="atoms")
