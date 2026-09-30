from pathlib import Path

import pytest

from calm.interface.refinement.contract import stable_registry_seed
from calm.calculators.exceptions import CalculatorExecutionError
from calm.calculators.spec import CalculatorSpec
from calm.interface.refinement.registry import (
    PERSISTED_REGISTRY_SCORE_UNITS,
    monte_carlo_registry_search,
)
from calm.project.bootstrap import open_workspace


def _finite_registry_trace(
    _self,
    *,
    base,
    n_steps,
    prototype_uid_full,
    calc_spec,
    alpha=0.5,
    translation0=(0.0, 0.0),
    z_padding=1.5,
    vacuum_padding=None,
    step_scale=0.08,
    temperature=0.03,
    seed=None,
):
    del prototype_uid_full, calc_spec, alpha, z_padding, vacuum_padding
    actual_seed = stable_registry_seed(base) if seed is None else int(seed)
    return monte_carlo_registry_search(
        lambda _translation: -2.5,
        x0=translation0,
        n_steps=int(n_steps),
        step_scale=float(step_scale),
        temperature=float(temperature),
        seed=actual_seed,
        keep_trace=True,
        score_units=PERSISTED_REGISTRY_SCORE_UNITS,
    )


@pytest.mark.filterwarnings("error:Calculator resolution failed.*:UserWarning")
def test_workspace_registry_stage_persists_authoritative_result(
    tmp_path: Path,
    prototype_graph_factory,
    stub_authoritative_registry_evaluator,
    persisted_test_uid,
):
    prototype_uid = persisted_test_uid(
        "prototype",
        "proto:public-registry-stage",
    )
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:public-registry-stage",
        bulk_id_short="b_public_registry_stage",
        slab_a_uid_full="slab:public-registry-a",
        slab_a_id_short="s_public_registry_a",
        slab_b_uid_full="slab:public-registry-b",
        slab_b_id_short="s_public_registry_b",
        run_uid_full="run:public-registry-seed",
        run_id_short="r_public_registry_seed",
        prototype_uid_full=prototype_uid,
        prototype_id_short="p_public_registry_stage",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.3,
            "n_atoms_interface": 1,
        },
    )

    workspace = open_workspace(root=tmp_path)
    results = workspace.run_registry_stage(
        [prototype_uid],
        n_steps=1,
        resume=False,
    )

    assert len(results) == 1
    result = results[0]
    assert result["prototype_uid"] == prototype_uid
    assert result["status"] == "completed"
    assert result["reason"] is None
    assert result["run_uid"] is not None
    assert result["followup_uid"] is not None

    workspace = open_workspace(root=tmp_path)
    persisted = workspace.list_followup_results(
        run=result["run_uid"],
        kind="registry_search",
    )
    assert len(persisted) == 1
    assert persisted[0].uid_full == result["followup_uid"]
    assert persisted[0].prototype_uid_full == prototype_uid
    assert persisted[0].target_uid_full == prototype_uid
    assert persisted[0].target_kind == "prototype"
    assert persisted[0].n_points == 1
    assert persisted[0].best_energy == -2.5
    assert persisted[0].payload["objective"] == (
        "unrelaxed_total_energy_density_eV_per_A2"
    )
    assert persisted[0].payload["calculator"]["family"] == "test"
    assert persisted[0].payload["calculator_fingerprint"]
    assert persisted[0].payload["z_padding"] == 1.5
    assert persisted[0].payload["vacuum"] is None
    provenance = persisted[0].payload["provenance"]
    assert provenance["z_search_enabled"] is False
    assert provenance["fixed_z_padding"] == 1.5
    assert provenance["protocol"] == (
        "fractional_translation_torus_metropolis"
    )
    assert provenance["protocol_version"] == 1
    assert provenance["rng"]["bit_generator"] == (
        "numpy.random.PCG64"
    )
    assert provenance["temperature"] == 0.03
    assert provenance["temperature_units"] == "eV_per_A2"
    assert provenance["seed_derivation"] == (
        "sha256_utf8_prefix64_mod_2pow31"
    )
    assert len(persisted[0].payload["proposal_trace"]) == 1



def test_registry_stage_requires_authoritative_calculator_provenance(
    tmp_path: Path,
    prototype_graph_factory,
    persisted_test_uid,
):
    prototype_uid = persisted_test_uid(
        "prototype",
        "proto:registry-no-calculator",
    )
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:registry-no-calculator",
        bulk_id_short="b_registry_no_calculator",
        slab_a_uid_full="slab:registry-no-calculator-a",
        slab_a_id_short="s_registry_no_calculator_a",
        slab_b_uid_full="slab:registry-no-calculator-b",
        slab_b_id_short="s_registry_no_calculator_b",
        run_uid_full="run:registry-no-calculator-seed",
        run_id_short="r_registry_no_calculator_seed",
        prototype_uid_full=prototype_uid,
        prototype_id_short="p_registry_no_calculator",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.3,
            "n_atoms_interface": 1,
        },
    )

    workspace = open_workspace(root=tmp_path)
    with pytest.raises(
        RuntimeError,
        match="requires authoritative calculator provenance",
    ):
        workspace.run_registry_stage(
            [prototype_uid],
            n_steps=1,
            resume=False,
        )


def test_registry_run_identity_changes_with_calculator_spec(
    tmp_path: Path,
    prototype_graph_factory,
    persisted_test_uid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.project.application.followups import registry_search as module

    prototype_uid = persisted_test_uid(
        "prototype",
        "proto:registry-calculator-identity",
    )
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:registry-calculator-identity",
        bulk_id_short="b_registry_calculator_identity",
        slab_a_uid_full="slab:registry-calculator-identity-a",
        slab_a_id_short="s_registry_calculator_identity_a",
        slab_b_uid_full="slab:registry-calculator-identity-b",
        slab_b_id_short="s_registry_calculator_identity_b",
        run_uid_full="run:registry-calculator-identity-seed",
        run_id_short="r_registry_calculator_identity_seed",
        prototype_uid_full=prototype_uid,
        prototype_id_short="p_registry_calculator_identity",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.3,
            "n_atoms_interface": 1,
        },
    )

    selected = {
        "spec": CalculatorSpec(family="test", model="model-one")
    }
    monkeypatch.setattr(
        module,
        "require_calculator_from_prototype",
        lambda _uow, _prototype_uid: selected["spec"],
    )
    monkeypatch.setattr(
        module.RegistrySearchOrchestrator,
        "_compute_monte_carlo_trace",
        _finite_registry_trace,
    )

    workspace = open_workspace(root=tmp_path)
    first = workspace.run_registry_stage(
        [prototype_uid],
        n_steps=1,
        resume=True,
    )
    selected["spec"] = CalculatorSpec(family="test", model="model-two")
    second = workspace.run_registry_stage(
        [prototype_uid],
        n_steps=1,
        resume=True,
    )

    assert first[0]["run_uid"] != second[0]["run_uid"]
    runs = workspace.list_runs(run_type="registry_search")
    assert len(runs) == 2
    models = {
        run.spec["calculator_specs"][prototype_uid]["model"] for run in runs
    }
    assert models == {"model-one", "model-two"}


def test_registry_execution_failure_marks_run_failed(
    tmp_path: Path,
    prototype_graph_factory,
    persisted_test_uid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from calm.project.application.followups import registry_search as module

    prototype_uid = persisted_test_uid(
        "prototype",
        "proto:registry-execution-failure",
    )
    prototype_graph_factory(
        filename="calm.sqlite",
        bulk_uid_full="bulk:registry-execution-failure",
        bulk_id_short="b_registry_execution_failure",
        slab_a_uid_full="slab:registry-execution-failure-a",
        slab_a_id_short="s_registry_execution_failure_a",
        slab_b_uid_full="slab:registry-execution-failure-b",
        slab_b_id_short="s_registry_execution_failure_b",
        run_uid_full="run:registry-execution-failure-seed",
        run_id_short="r_registry_execution_failure_seed",
        prototype_uid_full=prototype_uid,
        prototype_id_short="p_registry_execution_failure",
        prototype_payload={
            "miller_a": [0],
            "miller_b": [0],
            "match_score": 0.3,
            "n_atoms_interface": 1,
        },
    )

    monkeypatch.setattr(
        module,
        "require_calculator_from_prototype",
        lambda _uow, _prototype_uid: CalculatorSpec(
            family="test",
            model="failing-model",
        ),
    )

    def fail_trace(*args, **kwargs):
        del args, kwargs
        raise CalculatorExecutionError("calculator evaluation failed")

    monkeypatch.setattr(
        module.RegistrySearchOrchestrator,
        "_compute_monte_carlo_trace",
        fail_trace,
    )

    workspace = open_workspace(root=tmp_path)
    with pytest.raises(
        CalculatorExecutionError,
        match="calculator evaluation failed",
    ):
        workspace.run_registry_stage(
            [prototype_uid],
            n_steps=1,
            resume=False,
        )

    runs = workspace.list_runs(run_type="registry_search")
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert runs[0].error == {
        "exception_type": "CalculatorExecutionError",
        "module": "calm.calculators.exceptions",
        "message": "calculator evaluation failed",
    }
    assert workspace.list_followup_results(
        run=runs[0].uid_full,
        kind="registry_search",
    ) == []
