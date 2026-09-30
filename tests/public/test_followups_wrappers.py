from types import SimpleNamespace

import pytest

from calm.public.records.followups import RegistrySearchRun, StrainPartitionScan
from test_helpers import (
    make_current_registry_result_payload,
    make_current_strain_result_payload,
)


class FakeFollowup:
    def __init__(
        self,
        id_short,
        prototype_id_short,
        *,
        run_id_short="r1",
        payload=None,
        best_energy=None,
        param1=None,
        param2=None,
        n_points=None,
    ):
        self.id_short = id_short
        self.run_id_short = run_id_short
        self.prototype_id_short = prototype_id_short
        self.payload = payload or {}
        self.target_kind = "prototype"
        self.best_energy = best_energy
        self.param1 = param1
        self.param2 = param2
        self.n_points = n_points


class FakeProject:
    def __init__(self, results):
        self._results = results

    def followups(self, *, run, kind):
        del kind
        return [r for r in self._results if r.run_id_short == run]


def _strain_payload() -> dict:
    return make_current_strain_result_payload(
        alpha=0.0,
        value=0.1,
        metric="gamma_eV_per_A2",
    )


def _registry_payload() -> dict:
    return make_current_registry_result_payload()


def test_strain_partition_scan_to_rows_and_write(tmp_path):
    f = FakeFollowup(
        "f1",
        "p1",
        payload=_strain_payload(),
    )
    proj = FakeProject([f])
    scan = StrainPartitionScan(project=proj, run=SimpleNamespace(id_short="r1"))
    rows = scan.to_rows()
    assert any(r.get("gamma_eV_per_A2") == 0.1 for r in rows)
    assert rows[0]["is_selected"] is True

    full = scan.to_rows(view="all")
    assert full[0]["interface_area_A2"] == pytest.approx(10.0)
    assert full[0]["side_a_principal_log_strains"] == (-0.0, 0.0)
    assert full[0]["side_b_principal_log_strains"] == (-0.04, 0.02)
    assert isinstance(full[0]["side_a_principal_log_strains"], tuple)

    payload_point = f.payload["points"][0]
    assert isinstance(payload_point["side_a_principal_log_strains"], list)
    full[0]["side_a_principal_log_strains"] = (99.0, 99.0)
    assert payload_point["side_a_principal_log_strains"] == [-0.0, 0.0]

    # write
    out = tmp_path / "strain.csv"
    scan.write_table(out)
    assert out.exists()


def test_strain_partition_scan_rejects_nonmapping_points() -> None:
    followup = FakeFollowup(
        "f1",
        "p1",
        payload={
            "selection": {
                "metric": "potential_energy_density_eV_per_A2",
                "alpha": 0.0,
                "value": 1.0,
            },
            "points": [[0.0, 1.0]],
        },
    )

    with pytest.raises(TypeError, match="mapping rows"):
        StrainPartitionScan(
            project=FakeProject([followup]),
            run=SimpleNamespace(id_short="r1"),
        ).to_rows()


def test_registry_search_to_rows_and_write(tmp_path):
    f = FakeFollowup(
        "f1",
        "p1",
        payload=_registry_payload(),
        best_energy=0.5,
        param1=1,
        n_points=10,
    )
    proj = FakeProject([f])
    reg = RegistrySearchRun(project=proj, run=SimpleNamespace(id_short="r1"))
    rows = reg.to_rows()
    assert isinstance(rows, list)
    trace = reg.trace_rows()
    assert len(trace) == 2
    assert trace[0]["step"] == 1
    assert isinstance(trace[0]["proposed_translation"], tuple)
    assert isinstance(trace[0]["best_translation"], tuple)

    payload_trace = f.payload["proposal_trace"]
    trace[0]["proposed_translation"] = (99.0, 99.0)
    assert payload_trace[0]["proposed_translation"] != [99.0, 99.0]

    out = tmp_path / "reg.csv"
    trace_out = tmp_path / "reg-trace.csv"
    reg.write_table(out)
    reg.write_trace(trace_out)
    assert out.exists()
    assert trace_out.exists()


def test_registry_search_rows_reject_noncurrent_provenance() -> None:
    result = FakeFollowup(
        "f1",
        "p1",
        payload={
            **_registry_payload(),
            "provenance": {"temperature": 0.03},
        },
        best_energy=0.5,
        param1=0.1,
        param2=0.2,
        n_points=10,
    )
    with pytest.raises(ValueError, match="not exact-current"):
        RegistrySearchRun(
            project=FakeProject([result]),
            run=SimpleNamespace(id_short="r1"),
        ).to_rows()
