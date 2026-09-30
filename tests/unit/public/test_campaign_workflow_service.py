from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.public.workflows.campaigns import ProjectCampaignWorkflowService
from calm.public.inputs.campaigns import (
    CampaignCase,
    CampaignCaseResult,
    CampaignSettings,
    CampaignWorkflowResult,
)
from calm.public.records.followups import InterfaceRefinementResult
from calm.public.inputs.settings import (
    BuildSettings,
    DatasetSettings,
    EnergyConvention,
    EnergySettings,
    RelaxSettings,
    ReferenceEnergySettings,
    SearchSettings,
)


def _service(project, *, dataset_workflows=None):
    adapter = getattr(
        project,
        "_adapter",
        SimpleNamespace(add_provenance_edge=lambda **kwargs: None),
    )
    repository = getattr(project, "_repo", SimpleNamespace())

    def _missing(name):
        def _call(*args, **kwargs):
            raise AssertionError(f"Unexpected campaign workflow call: {name}")
        return _call

    search_workflows = SimpleNamespace(
        search=getattr(project, "search", _missing("search")),
        search_interfaces=getattr(
            project,
            "search_interfaces",
            _missing("search_interfaces"),
        ),
    )
    interface_builds = SimpleNamespace(
        build_interfaces=getattr(
            project,
            "build_interfaces",
            _missing("build_interfaces"),
        )
    )
    interface_refinements = SimpleNamespace(
        refine_interfaces=getattr(
            project,
            "refine_interfaces",
            _missing("refine_interfaces"),
        )
    )
    relaxation_workflows = SimpleNamespace(
        relax_interfaces=getattr(
            project,
            "relax_interfaces",
            _missing("relax_interfaces"),
        )
    )
    energy_workflows = SimpleNamespace(
        evaluate_reference_energies=getattr(
            project,
            "evaluate_reference_energies",
            _missing("evaluate_reference_energies"),
        ),
        evaluate_energies=getattr(
            project,
            "evaluate_energies",
            _missing("evaluate_energies"),
        ),
    )
    if dataset_workflows is None:
        dataset_workflows = SimpleNamespace(
            create_dataset=getattr(
                project,
                "create_dataset",
                _missing("create_dataset"),
            )
        )
    return ProjectCampaignWorkflowService(
        project=project,
        workspace=adapter,
        repository=repository,
        search_workflows=search_workflows,
        interface_builds=interface_builds,
        interface_refinements=interface_refinements,
        relaxation_workflows=relaxation_workflows,
        energy_workflows=energy_workflows,
        dataset_workflows=dataset_workflows,
    )


def test_campaign_case_overrides_roundtrip_and_resolve() -> None:
    case = CampaignCase(
        name="case",
        search_name="search",
        build_top=3,
        build_settings=BuildSettings(alpha=0.25),
        relax_settings=RelaxSettings(fmax=0.02, steps=100),
        energy_backend="mace",
        dataset_name="custom_dataset",
        dimensions={"alpha": "0.25"},
    )

    restored = CampaignCase.from_dict(case.to_dict())
    assert restored == case

    resolved = restored.resolved_settings(
        CampaignSettings(stages=("build", "relax", "energy", "dataset"))
    )
    assert resolved.build_top == 3
    assert resolved.build_settings.alpha == 0.25
    assert resolved.relax_settings.fmax == 0.02
    assert resolved.energy_backend == "mace"


def test_campaign_grid_shares_downstream_search_and_records_dimensions() -> None:
    base = CampaignCase(name="base", search_name="persisted_search")
    cases = CampaignCase.grid(
        base,
        axes={
            "backend": (
                CampaignCase.variant("a", energy_backend="backend-a"),
                CampaignCase.variant("b", energy_backend="backend-b"),
            ),
            "build": (
                CampaignCase.variant("one", build_top=1),
                CampaignCase.variant("two", build_top=2),
            ),
        },
    )

    assert len(cases) == 4
    assert {case.search_name for case in cases} == {"persisted_search"}
    assert len({case.name for case in cases}) == 4
    assert {tuple(sorted(case.dimensions.items())) for case in cases} == {
        (("backend", "a"), ("build", "one")),
        (("backend", "a"), ("build", "two")),
        (("backend", "b"), ("build", "one")),
        (("backend", "b"), ("build", "two")),
    }


def test_campaign_grid_search_axis_gets_unique_search_names() -> None:
    base = CampaignCase(
        name="base",
        search_name="search",
        surface_a="surface:a",
        surface_b="surface:b",
    )
    cases = CampaignCase.grid(
        base,
        axes={
            "strain": (
                CampaignCase.variant(
                    "low",
                    search_settings=SearchSettings(max_principal_strain=0.03),
                ),
                CampaignCase.variant(
                    "high",
                    search_settings=SearchSettings(max_principal_strain=0.08),
                ),
            )
        },
    )

    assert [case.search_name for case in cases] == [
        "search__strain-low",
        "search__strain-high",
    ]
    assert [case.search_settings.max_principal_strain for case in cases] == [0.03, 0.08]


def test_mixed_grid_reuses_each_search_across_downstream_variants() -> None:
    base = CampaignCase(
        name="base",
        search_name="search",
        surface_a="surface:a",
        surface_b="surface:b",
    )
    cases = CampaignCase.grid(
        base,
        axes={
            "strain": (
                CampaignCase.variant(
                    "low",
                    search_settings=SearchSettings(max_principal_strain=0.03),
                ),
                CampaignCase.variant(
                    "high",
                    search_settings=SearchSettings(max_principal_strain=0.08),
                ),
            ),
            "backend": (
                CampaignCase.variant("a", energy_backend="backend-a"),
                CampaignCase.variant("b", energy_backend="backend-b"),
            ),
        },
    )

    assert [case.search_name for case in cases] == [
        "search__strain-low",
        "search__strain-low",
        "search__strain-high",
        "search__strain-high",
    ]


def test_campaign_grid_search_axis_requires_exact_surfaces() -> None:
    base = CampaignCase(name="base", search_name="search")
    with pytest.raises(ValueError, match="require exact surface_a and surface_b"):
        CampaignCase.grid(
            base,
            axes={
                "strain": (
                    CampaignCase.variant(
                        "low",
                        search_settings=SearchSettings(max_principal_strain=0.03),
                    ),
                )
            },
        )


def test_campaign_grid_rejects_conflicting_axes() -> None:
    base = CampaignCase(name="base", search_name="search")
    with pytest.raises(ValueError, match="conflict on 'build_settings'"):
        CampaignCase.grid(
            base,
            axes={
                "alpha": (
                    CampaignCase.variant(
                        "low",
                        build_settings=BuildSettings(alpha=0.2),
                    ),
                ),
                "gap": (
                    CampaignCase.variant("wide", build_settings=BuildSettings(gap=3.0)),
                ),
            },
        )


def test_case_convention_override_clears_campaign_scalar_references() -> None:
    global_convention = EnergyConvention(
        formula="interface_excess_strained_bulk",
        n_interfaces=2,
    )
    manual_references = ReferenceEnergySettings(
        bulk_a_eV_per_formula_unit=-1.0,
        bulk_b_eV_per_formula_unit=-2.0,
        n_formula_units_a=1,
        n_formula_units_b=1,
    )
    case_convention = EnergyConvention(
        formula="work_of_separation_unrelaxed_surfaces",
        n_interfaces=2,
    )
    case = CampaignCase(
        name="case",
        search_name="search",
        energy_convention=case_convention,
    )

    resolved = case.resolved_settings(
        CampaignSettings(
            stages=("energy",),
            energy_convention=global_convention,
            energy_references=manual_references,
        )
    )

    assert resolved.energy_convention == case_convention
    assert resolved.energy_references is None


def test_campaign_settings_calculate_references_without_scalars() -> None:
    settings = CampaignSettings(
        stages=("energy",),
        energy_convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=2,
        ),
    )
    settings.validate()
    restored = CampaignSettings.from_dict(settings.to_dict())
    assert restored.energy_convention == settings.energy_convention
    assert restored.energy_references is None


def test_campaign_comparison_groups_and_dense_ranks(tmp_path: Path) -> None:
    campaign = SimpleNamespace(
        name="campaign",
        uid_full="campaign:one",
        id_short="y_one",
    )
    run = SimpleNamespace(uid_full="campaign_run:one", id_short="x_one")
    cases = (
        CampaignCaseResult(
            case=CampaignCase(
                name="a",
                search_name="shared",
                dimensions={"backend": "mace"},
            ),
            status="completed",
            stages={"energy": {"raw_eV_mean": -3.0}},
        ),
        CampaignCaseResult(
            case=CampaignCase(
                name="b",
                search_name="shared",
                dimensions={"backend": "mace"},
            ),
            status="completed",
            stages={"energy": {"raw_eV_mean": -3.0}},
        ),
        CampaignCaseResult(
            case=CampaignCase(
                name="c",
                search_name="shared",
                dimensions={"backend": "chgnet"},
            ),
            status="completed",
            stages={"energy": {"raw_eV_mean": -1.0}},
        ),
    )
    result = CampaignWorkflowResult(
        campaign=campaign,
        run=run,
        cases=cases,
        status="completed",
    )

    comparison = result.comparison()
    assert {
        group.values["dimension_backend"]
        for group in comparison.group_by("dimension_backend")
    } == {
        "mace",
        "chgnet",
    }

    ranked = comparison.rank_by("energy_raw_eV_mean")
    rows = ranked.to_rows()
    assert [row["case_name"] for row in rows] == ["a", "b", "c"]
    assert [row["rank"] for row in rows] == [1, 1, 2]
    assert [
        row["case_name"]
        for row in comparison.best("energy_raw_eV_mean").to_rows()
    ] == [
        "a",
        "b",
    ]

    grouped_ranked = ranked.group_by("dimension_backend")
    assert all(
        group.comparison.rank_metric == "energy_raw_eV_mean"
        for group in grouped_ranked
    )

    output = tmp_path / "comparison.csv"
    ranked.write_table(output)
    assert "energy_raw_eV_mean" in output.read_text(encoding="utf-8")


def test_execute_campaign_calculates_references_and_persists_metrics() -> None:
    class Adapter:
        def __init__(self) -> None:
            self.edges: list[dict] = []

        def add_provenance_edge(self, **kwargs):
            self.edges.append(dict(kwargs))

    reference = SimpleNamespace(
        run=SimpleNamespace(uid_full="run:reference"),
        results=[
            SimpleNamespace(uid_full="reference:a"),
            SimpleNamespace(uid_full="reference:b"),
        ],
    )
    energy = SimpleNamespace(
        energy_run=SimpleNamespace(uid_full="run:energy"),
        energy_results=[
            SimpleNamespace(energy_eV=-2.0),
            SimpleNamespace(energy_eV=-4.0),
        ],
        thermodynamic_run=SimpleNamespace(uid_full="run:thermodynamic"),
        thermodynamic_results=[
            SimpleNamespace(value_eV_per_A2=0.2, value_J_per_m2=3.2),
            SimpleNamespace(value_eV_per_A2=0.4, value_J_per_m2=6.4),
        ],
    )

    class Search:
        pass

    class Project:
        def __init__(self) -> None:
            self._adapter = Adapter()

        def search(self, name):
            assert name == "existing"
            return Search()

        def evaluate_reference_energies(self, **kwargs):
            assert kwargs["search_name"] == "existing"
            assert kwargs["backend"] == "real"
            return reference

        def evaluate_energies(self, **kwargs):
            assert kwargs["search_name"] == "existing"
            assert kwargs["references"] is reference
            return energy

    case = CampaignCase(
        name="case",
        search_name="existing",
        dimensions={"model": "demo"},
    )
    settings = CampaignSettings(
        stages=("energy",),
        energy_settings=EnergySettings(),
        energy_convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=2,
        ),
    )
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()], "settings": settings.to_dict()},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo")
    project = Project()

    result = _service(project).execute_campaign(campaign, run)
    row = result.comparison().to_rows()[0]
    assert row["reference_energy_n_results"] == 2
    assert row["energy_raw_eV_mean"] == -3.0
    assert row["energy_thermodynamic_eV_per_A2_mean"] == pytest.approx(0.3)
    assert row["energy_thermodynamic_J_per_m2_mean"] == pytest.approx(4.8)
    assert any(
        edge["kind"] == "campaign_case_result"
        for edge in project._adapter.edges
    )


def test_execute_campaign_threads_case_specific_stage_targets() -> None:
    built = (SimpleNamespace(uid_full="interface:built"),)
    refined = (SimpleNamespace(uid_full="interface:refined"),)
    relaxed = (SimpleNamespace(uid_full="interface:relaxed"),)

    class EmptyInterfaces:
        def one_or_none(self, **filters):
            return None

        def where(self, **filters):
            return self

        def __len__(self):
            return 0

    class Search:
        def interfaces(self):
            return EmptyInterfaces()

    energy = SimpleNamespace(
        energy_run=SimpleNamespace(uid_full="run:energy"),
        energy_results=[SimpleNamespace(energy_eV=-3.0)],
        thermodynamic_run=None,
        thermodynamic_results=None,
    )
    references = SimpleNamespace(
        run=SimpleNamespace(uid_full="run:references"),
        results=[SimpleNamespace(uid_full="result:reference")],
    )

    class Adapter:
        def __init__(self) -> None:
            self.edges: list[dict] = []

        def add_provenance_edge(self, **kwargs):
            self.edges.append(dict(kwargs))

    class Project:
        def __init__(self) -> None:
            self._adapter = Adapter()
            self.search_facade = Search()
            self.build_prefix = None
            self.refinement_targets = None
            self.relaxation_targets = None
            self.reference_targets = None
            self.energy_targets = None

        def search(self, name):
            return self.search_facade

        def refined_interfaces(self, **kwargs):
            return EmptyInterfaces()

        def build_interfaces(self, search_name, *, name_prefix, **kwargs):
            assert search_name == "existing"
            self.build_prefix = name_prefix
            return built

        def refine_interfaces(self, search_name, **kwargs):
            assert search_name == "existing"
            self.refinement_targets = kwargs.get("interfaces")
            return InterfaceRefinementResult(
                ok=True,
                issues=[],
                strain_scan=SimpleNamespace(
                    run=SimpleNamespace(uid_full="run:strain")
                ),
                registry_run=SimpleNamespace(
                    run=SimpleNamespace(uid_full="run:registry")
                ),
                registry_interfaces=list(refined),
            )

        def relax_interfaces(self, interfaces, **kwargs):
            self.relaxation_targets = tuple(interfaces)
            return SimpleNamespace(
                run=SimpleNamespace(uid_full="run:relax"),
                results=[SimpleNamespace(uid_full="result:relax")],
                relaxed_interfaces=relaxed,
            )

        def evaluate_energies(self, interfaces, **kwargs):
            self.energy_targets = tuple(interfaces)
            assert kwargs["references"] is references
            return energy

        def evaluate_reference_energies(self, interfaces, **kwargs):
            self.reference_targets = tuple(interfaces)
            return references

    case = CampaignCase(name="case", search_name="existing")
    settings = CampaignSettings(
        stages=("build", "refine", "relax", "energy"),
        energy_convention=EnergyConvention(
            formula="interface_excess_strained_bulk",
            n_interfaces=2,
        ),
    )
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()], "settings": settings.to_dict()},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo")
    project = Project()

    result = _service(project).execute_campaign(campaign, run)

    assert result.status == "completed"
    assert project.build_prefix == "demo__case_built"
    assert tuple(project.refinement_targets) == built
    assert [item.uid_full for item in project.relaxation_targets] == [
        "interface:refined"
    ]
    assert project.reference_targets == relaxed
    assert project.energy_targets == relaxed
    refine_run_edges = [
        edge
        for edge in project._adapter.edges
        if edge["kind"] == "run_of_campaign_execution"
        and edge["payload"] == {"case": "case", "stage": "refine"}
    ]
    assert {edge["src_uid_full"] for edge in refine_run_edges} == {
        "run:strain",
        "run:registry",
    }


def test_comparison_ignores_nonfinite_metrics() -> None:
    result = CampaignWorkflowResult(
        campaign=SimpleNamespace(name="campaign"),
        run=SimpleNamespace(uid_full="run"),
        cases=(
            CampaignCaseResult(
                case=CampaignCase(name="finite", search_name="search"),
                status="completed",
                stages={"energy": {"raw_eV_mean": -1.0}},
            ),
            CampaignCaseResult(
                case=CampaignCase(name="nan", search_name="search"),
                status="completed",
                stages={"energy": {"raw_eV_mean": float("nan")}},
            ),
        ),
        status="completed",
    )

    rows = result.comparison().rank_by("energy_raw_eV_mean").to_rows()
    assert [row["rank"] for row in rows] == [1, None]


def test_reused_campaign_result_restores_persisted_case_metrics() -> None:
    case = CampaignCase(
        name="case",
        search_name="existing",
        dimensions={"backend": "demo"},
    )
    persisted = CampaignCaseResult(
        case=case,
        status="completed",
        stages={"energy": {"raw_eV_mean": -2.5}},
        export_path=Path("exports/case"),
    ).to_persisted_payload()

    class Repo:
        def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
            if kind == "campaign_case_result":
                return [
                    SimpleNamespace(
                        src_uid_full="campaign:demo",
                        dst_uid_full="campaign_run:demo",
                        payload=persisted,
                    )
                ]
            return []

    project = SimpleNamespace(_repo=Repo())
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={
            "cases": [case.to_dict()],
            "settings": CampaignSettings(stages=("energy",)).to_dict(),
        },
    )
    run = SimpleNamespace(uid_full="campaign_run:demo", status="completed")

    restored = _service(project).reused_campaign_result(campaign, run)
    assert restored.reused is True
    assert restored.cases[0].stages["energy"]["raw_eV_mean"] == -2.5
    assert restored.cases[0].export_path == Path("exports/case")
    assert restored.comparison().to_rows()[0]["dimension_backend"] == "demo"


def test_reused_campaign_result_prefers_completed_retry_payload() -> None:
    case = CampaignCase(name="case", search_name="existing")
    failed = CampaignCaseResult(
        case=case,
        status="failed",
        stages={"energy": {"raw_eV_mean": -1.0}},
        failure={"type": "RuntimeError", "message": "first attempt"},
    ).to_persisted_payload()
    completed = CampaignCaseResult(
        case=case,
        status="completed",
        stages={"energy": {"raw_eV_mean": -2.0}},
    ).to_persisted_payload()

    class Repo:
        def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
            if kind == "campaign_case_result":
                return [
                    SimpleNamespace(payload=failed),
                    SimpleNamespace(payload=completed),
                ]
            return []

    project = SimpleNamespace(_repo=Repo())
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()]},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo", status="completed")

    restored = _service(project).reused_campaign_result(campaign, run)
    assert restored.cases[0].status == "completed"
    assert restored.cases[0].stages["energy"]["raw_eV_mean"] == -2.0


def test_reused_campaign_result_requires_current_case_result_edges() -> None:
    case = CampaignCase(name="case", search_name="existing")

    class Repo:
        def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
            del src, dst, kind, limit
            return []

    project = SimpleNamespace(_repo=Repo())
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()]},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo", status="completed")

    with pytest.raises(RuntimeError, match="missing persisted case results"):
        _service(project).reused_campaign_result(campaign, run)


def test_reused_campaign_result_rejects_unknown_case_result_contract() -> None:
    case = CampaignCase(name="case", search_name="existing")

    class Repo:
        def list_edges(self, *, src=None, dst=None, kind=None, limit=None):
            del src, dst, kind, limit
            return [
                SimpleNamespace(
                    payload={
                        "contract": "calm.campaign_case_result.v0",
                        "case": case.to_dict(),
                        "status": "completed",
                    }
                )
            ]

    project = SimpleNamespace(_repo=Repo())
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()]},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo", status="completed")

    with pytest.raises(RuntimeError, match="unsupported contract"):
        _service(project).reused_campaign_result(campaign, run)


def test_energy_dataset_campaign_aggregates_and_exports(tmp_path) -> None:
    class _Adapter:
        def __init__(self):
            self.edges = []

        def add_provenance_edge(self, **kwargs):
            self.edges.append(dict(kwargs))

    class _Dataset:
        uid_full = "dataset:case"

        def items(self):
            return [SimpleNamespace(uid_full="dataset_item:one")]

        def export(self, destination, **_kwargs):
            return SimpleNamespace(destination=destination)

        def to_dict(self):
            return {"uid_full": self.uid_full}

    class _Energy:
        energy_run = SimpleNamespace(uid_full="run:energy")
        energy_results = [SimpleNamespace(uid_full="followup:energy")]
        thermodynamic_run = None
        thermodynamic_results = None

    class _SearchWithEnergy:
        pass

    class _Project:
        def __init__(self):
            self._adapter = _Adapter()

        def search(self, name):
            assert name == "existing"
            return _SearchWithEnergy()

        def evaluate_energies(self, **kwargs):
            assert kwargs["search_name"] == "existing"
            return _Energy()

    class _DatasetWorkflows:
        def create_dataset(self, name, sources, **_kwargs):
            assert name == "demo_case_dataset"
            assert sources is _Energy.energy_results
            return _Dataset()

    case = CampaignCase(name="case", search_name="existing")
    settings = CampaignSettings(
        stages=("energy", "dataset"),
        dataset_name_template="{campaign}_{case}_dataset",
    )
    campaign = SimpleNamespace(
        uid_full="campaign:demo",
        name="demo",
        spec={"cases": [case.to_dict()], "settings": settings.to_dict()},
    )
    run = SimpleNamespace(uid_full="campaign_run:demo")
    project = _Project()

    result = _service(
        project,
        dataset_workflows=_DatasetWorkflows(),
    ).execute_campaign(
        campaign,
        run,
        export_root=tmp_path,
    )

    assert result.status == "completed"
    assert len(result.cases) == 1
    assert result.cases[0].dataset.uid_full == "dataset:case"
    assert result.cases[0].export_path == tmp_path / "demo_case_dataset"
    assert {edge["kind"] for edge in project._adapter.edges} == {
        "run_of_campaign_execution",
        "produced_by",
        "belonged_to_campaign",
        "campaign_case_result",
    }
