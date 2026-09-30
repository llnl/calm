"""Dependency-light transaction tests for project application graph services."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from calm.project.application.artifacts import ArtifactsService
from calm.project.application.derived_interfaces import DerivedInterfaceService
from calm.project.application.interface_derivation import InterfaceDerivationService
from calm.project.domain.models import FollowupResult, Prototype, Run


class _Store:
    def ensure_run_layout(self, *, run_id_short: str) -> None:
        assert run_id_short == "r_test"

    def put_bytes(
        self,
        *,
        run_id_short: str,
        category: str,
        filename: str,
        data: bytes,
    ) -> Path:
        assert run_id_short == "r_test"
        assert category
        assert filename
        assert data
        return Path("/tmp") / filename

    @staticmethod
    def uri_for(path: Path) -> str:
        return path.as_uri()


class _Ids:
    def resolve_run(self, value: str) -> str:
        return "run:test" if value in {"run:test", "r_test"} else value

    def resolve_prototype(self, value: str) -> str:
        return value

    def ensure_artifact_id(self, _uid: str) -> str:
        return "a_test"

    def ensure_short_id(self, *, tag: str, uid_full: str) -> str:
        assert tag == "i"
        assert uid_full.startswith("iface:")
        return "i_test"


class _Rows:
    def __init__(self, values=()) -> None:
        self.values = {value.uid_full: value for value in values}
        self.saved = []

    def get_by_uid_full(self, uid: str):
        return self.values.get(uid)

    def add(self, value):
        self.saved.append(value)
        return value

    def upsert(self, value):
        self.saved.append(value)
        self.values[value.uid_full] = value
        return value

    def list(self, **_kwargs):
        return list(self.values.values())


class _Edges:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.records: list[dict[str, object]] = []

    def add(self, **record):
        if self.fail:
            raise RuntimeError("edge write failed")
        self.records.append(record)
        return SimpleNamespace(**record)


class _ActiveUow:
    def __init__(self, *, edges: _Edges | None = None) -> None:
        self._depth = 1
        self.ids = _Ids()
        run = Run(
            uid_full="run:test",
            id_short="r_test",
            run_type="unit_test",
            status="done",
            spec={},
        )
        prototype = Prototype(
            uid_full="proto:test",
            id_short="p_test",
            run_uid_full="run:test",
            run_id_short="r_test",
            slab_a_uid_full="slab:a",
            slab_b_uid_full="slab:b",
            match_score=0.0,
            hencky_norm=0.0,
            interface_area=1.0,
            natoms=2,
            is_pareto=True,
            pareto_rank=0,
            payload={},
        )
        self.runs = _Rows([run])
        self.prototypes = _Rows([prototype])
        self.artifacts = _Rows()
        self.derived_interfaces = _Rows()
        self.edges = edges or _Edges()


def test_artifact_edge_failure_is_not_suppressed() -> None:
    uow = _ActiveUow(edges=_Edges(fail=True))
    service = ArtifactsService(uow_factory=lambda: uow, store=_Store())

    with pytest.raises(RuntimeError, match="edge write failed"):
        service.put_bytes_in(
            uow,
            "run:test",
            category="data",
            kind="json",
            filename="data.json",
            data=b"{}\n",
        )

    assert len(uow.artifacts.saved) == 1


def test_derived_interface_create_in_writes_required_parent_edge() -> None:
    uow = _ActiveUow()
    service = DerivedInterfaceService(uow_factory=lambda: uow)

    interface = service.create_in(
        uow,
        prototype="proto:test",
        strain_alpha=0.5,
    )

    assert uow.derived_interfaces.saved == [interface]
    assert [record["kind"] for record in uow.edges.records] == [
        "prototype_to_interface"
    ]


class _DerivationUow(_ActiveUow):
    def __init__(self) -> None:
        super().__init__()
        self._depth = 0
        self.enter_count = 0
        self.followups = _Rows(
            [
                FollowupResult(
                    uid_full="followup:test",
                    id_short="f_test",
                    run_uid_full="run:test",
                    run_id_short="r_test",
                    prototype_uid_full="proto:test",
                    prototype_id_short="p_test",
                    target_kind="prototype",
                    target_uid_full="proto:test",
                    kind="strain_partition_scan",
                    status="done",
                    best_energy=0.2,
                    param1=0.4,
                    n_points=1,
                    payload={
                        "selection": {
                            "metric": "potential_energy_density_eV_per_A2",
                            "alpha": 0.4,
                            "value": 0.2,
                        }
                    },
                )
            ]
        )
        self.runs.values["run:test"] = Run(
            uid_full="run:test",
            id_short="r_test",
            run_type="strain_partition_scan",
            status="done",
            spec={"targets": []},
        )

    def __enter__(self):
        self.enter_count += 1
        self._depth = 1
        return self

    def __exit__(self, *_args):
        self._depth = 0
        return None


def test_followup_derivation_writes_interface_and_lineage_in_one_uow() -> None:
    uow = _DerivationUow()
    service = InterfaceDerivationService(uow_factory=lambda: uow)

    interfaces = service.derive_from_strain_scan("run:test")

    assert len(interfaces) == 1
    assert uow.enter_count == 1
    assert [record["kind"] for record in uow.edges.records] == [
        "prototype_to_interface",
        "followup_to_interface",
    ]
