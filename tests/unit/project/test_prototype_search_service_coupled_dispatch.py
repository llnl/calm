from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import calm.interface.pipeline as pipeline
import calm.project.application.prototypes as prototypes_module


class _Ids:
    def resolve_slab(self, value: str) -> str:
        return f"slab:{value}"


class _RunsRepo:
    def upsert(self, run) -> None:
        self.run = run


class _SlabsRepo:
    def get_by_uid_full(self, uid: str):
        return SimpleNamespace(uid=uid)


class _EdgesRepo:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def add(self, **record) -> None:
        self.records.append(record)


class _UnitOfWork:
    def __init__(self) -> None:
        self.ids = _Ids()
        self.runs = _RunsRepo()
        self.slabs = _SlabsRepo()
        self.edges = _EdgesRepo()

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class _RunsService:
    created = None

    def __init__(self, _uow) -> None:
        pass

    def create(self, *, run_type: str, spec: dict):
        self.__class__.created = SimpleNamespace(
            uid_full="run:1",
            id_short="r_1",
            run_type=run_type,
            status="queued",
            spec=spec,
        )
        return self.__class__.created

    def get(self, _identifier: str):
        return self.__class__.created

    def mark_running(self, _identifier: str, *, progress: dict):
        self.__class__.created.status = "running"
        self.__class__.created.progress = progress
        return self.__class__.created

    def mark_done(self, _identifier: str, *, progress: dict):
        return SimpleNamespace(
            uid_full="run:1",
            id_short="r_1",
            spec=self.__class__.created.spec,
            progress=progress,
        )

    def mark_failed(self, _identifier: str, *, error: dict):
        raise AssertionError(error)


@dataclass(frozen=True)
class _PairIdentity:
    primitive_pair_key: tuple[int, ...]
    key_version: int = 1
    pair_symmetry_policy: str = "full"
    correspondence_orientation: str = "proper"
    material_exchange_identified: bool = False


@dataclass(frozen=True)
class _Prototype:
    prototype_uid: str
    slab_a_uid: str
    slab_b_uid: str
    pair_identity: _PairIdentity


class _PersistenceService:
    persisted: list[_Prototype] = []

    def __init__(self, *, uow_factory) -> None:
        del uow_factory

    def persist_interface_prototypes(self, prototypes, *, run_uid_full: str):
        self.__class__.persisted = list(prototypes)
        assert run_uid_full == "run:1"
        return {
            prototype.prototype_uid: {
                "uid_full": f"stored:{index}",
                "id_short": f"p_{index}",
            }
            for index, prototype in enumerate(prototypes)
        }


class _Provenance:
    def __init__(self, side: str) -> None:
        self.side = side

    def to_dict(self) -> dict[str, str]:
        return {"side": self.side}


def test_project_search_uses_coupled_result_and_versioned_run_spec(
    monkeypatch,
) -> None:
    monkeypatch.setattr(prototypes_module, "RunsService", _RunsService)
    original_service = prototypes_module.PrototypesService
    monkeypatch.setattr(
        prototypes_module,
        "PrototypesService",
        _PersistenceService,
    )
    uow = _UnitOfWork()
    service = prototypes_module.PrototypeSearchService(
        uow_factory=lambda: uow
    )

    pair_keys = ((1,) * 8, (2,) * 8)
    source = [
        _Prototype(
            prototype_uid=f"source:{index}",
            slab_a_uid="source:a",
            slab_b_uid="source:b",
            pair_identity=_PairIdentity(
                key,
                pair_symmetry_policy="proper",
                correspondence_orientation="all",
                material_exchange_identified=True,
            ),
        )
        for index, key in enumerate(pair_keys)
    ]
    captured = {}

    def _find(_slab_a, _slab_b, config):
        captured["config"] = config
        return SimpleNamespace(
            prototypes=source,
            surface_symmetry_a=_Provenance("a"),
            surface_symmetry_b=_Provenance("b"),
            pareto_population_size=7,
        )

    monkeypatch.setattr(pipeline, "find_prototypes", _find)

    run = service.start_search(
        slab_a="a",
        slab_b="b",
        n_candidates=2,
        k_max=5,
        surface_symmetry_mode="identity_only",
        pair_symmetry_policy="proper",
        correspondence_orientation="all",
        identify_material_exchange=True,
        correspondence_entry_limit=37,
    )

    assert captured["config"].max_results == 2
    assert captured["config"].pair_symmetry_policy == "proper"
    assert captured["config"].correspondence_orientation == "all"
    assert captured["config"].identify_material_exchange is True
    assert captured["config"].correspondence_entry_limit == 37
    assert run.spec["impl"] == "primitive_coupled_pair_v2"
    assert run.spec["pair_symmetry_policy"] == "proper"
    assert run.spec["correspondence_orientation"] == "all"
    assert run.spec["identify_material_exchange"] is True
    assert run.spec["correspondence_entry_limit"] == 37
    assert run.progress["primitive_pair_keys"] == [
        list(key) for key in pair_keys
    ]
    assert run.progress["pareto_population_size"] == 7
    assert [
        prototype.pair_identity.primitive_pair_key
        for prototype in _PersistenceService.persisted
    ] == list(pair_keys)

    monkeypatch.setattr(
        prototypes_module,
        "PrototypesService",
        original_service,
    )
