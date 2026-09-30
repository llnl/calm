from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import FrozenInstanceError, dataclass

import numpy as np
import pytest

import calm.interface.matching._orchestrator as orchestrator
from calm.interface.matching._audit_trace import (
    _AdmittedMatchTraceRecord,
    _capture_admitted_match_records,
    _capture_coupled_match_trace,
    _observe_admitted_match_records,
)
from calm.interface.matching.audit import CoupledMatchEnumerationAudit


@dataclass(frozen=True)
class _Cell:
    array: np.ndarray


@dataclass(frozen=True)
class _AtomsLike:
    cell: _Cell


@dataclass(frozen=True)
class _Slab:
    atoms: _AtomsLike
    n_atoms: int = 1


def _square_slab() -> _Slab:
    return _Slab(atoms=_AtomsLike(cell=_Cell(np.diag([1.0, 1.0, 10.0]))))


def _run_square(
    *,
    k_max: int = 1,
    strain_limit: float = 1.0e-10,
    audit: CoupledMatchEnumerationAudit | None = None,
):
    identity_group = (np.eye(2, dtype=int),)
    return orchestrator.enumerate_coupled_match_classes_core(
        _square_slab(),
        _square_slab(),
        k_max=k_max,
        cond_max=1.0e9,
        w_match=1.0,
        eps_principal_max=strain_limit,
        N_at_max=100,
        surface_metric_tolerance=1.0e-10,
        pair_symmetry_policy="full",
        correspondence_orientation="proper",
        correspondence_entry_limit=100,
        point_group_A=identity_group,
        point_group_B=identity_group,
        audit=audit,
    )


def _as_array(matrix) -> np.ndarray:
    return np.asarray(matrix)


def test_trace_captures_every_admitted_source_as_an_immutable_payload() -> None:
    audit = CoupledMatchEnumerationAudit.empty(k_max=2)
    with _capture_admitted_match_records() as records:
        classes = _run_square(k_max=2, audit=audit)

    assert len(records) == audit.pairs.totals()["candidates_admitted"]
    assert [record.audit_index for record in records] == list(range(len(records)))
    assert {record.final_pair_key for record in records} == {
        match_class.pair_key for match_class in classes
    }

    record = records[-1]
    assert isinstance(record, _AdmittedMatchTraceRecord)
    payload = record.to_dict()
    json.dumps(payload, allow_nan=False)
    assert isinstance(payload["source_pair_matrix"], list)
    with pytest.raises(FrozenInstanceError):
        record.audit_index = -1  # type: ignore[misc]

    source = _as_array(record.source_pair_matrix)
    primitive = _as_array(record.primitive_pair_matrix)
    right_factor = _as_array(record.source_right_factor)
    assert np.array_equal(primitive @ right_factor, source)
    assert np.array_equal(source[:2, :], _as_array(record.source_N_A))
    assert np.array_equal(
        source[2:, :],
        _as_array(record.source_N_B) @ _as_array(record.correspondence_U_B),
    )
    assert tuple(_as_array(record.canonical_pair_matrix).ravel()) == (
        record.final_pair_key
    )

    for basis_name, gram_name in (
        ("source_basis_A", "source_gram_A"),
        ("source_basis_B", "source_gram_B"),
        ("primitive_basis_A", "primitive_gram_A"),
        ("primitive_basis_B", "primitive_gram_B"),
    ):
        basis = _as_array(getattr(record, basis_name))
        gram = _as_array(getattr(record, gram_name))
        assert gram == pytest.approx(basis.T @ basis)

    assert record.source_condition_number_A == pytest.approx(
        np.linalg.cond(_as_array(record.source_basis_A))
    )
    assert record.source_condition_number_B == pytest.approx(
        np.linalg.cond(_as_array(record.source_basis_B))
    )

    source_atoms = (
        abs(round(np.linalg.det(source[:2, :])))
        + abs(round(np.linalg.det(source[2:, :])))
    )
    primitive_atoms = (
        abs(round(np.linalg.det(primitive[:2, :])))
        + abs(round(np.linalg.det(primitive[2:, :])))
    )
    assert record.source_atom_count == source_atoms
    assert record.primitive_atom_count == primitive_atoms
    assert record.atom_count == primitive_atoms


def test_source_condition_number_includes_the_b_side_correspondence() -> None:
    with _capture_admitted_match_records() as records:
        _run_square(strain_limit=0.5)

    transformed = next(
        record
        for record in records
        if not np.isclose(
            record.member_condition_number_B,
            record.source_condition_number_B,
        )
    )
    assert transformed.source_condition_number_B == pytest.approx(
        np.linalg.cond(_as_array(transformed.source_basis_B))
    )


def test_combined_capture_includes_full_search_context_and_is_repeatable() -> None:
    payloads = []
    for _ in range(2):
        with _capture_coupled_match_trace() as capture:
            _run_square(k_max=2)
        assert len(capture.search_contexts) == 1
        assert capture.search_contexts[0].surface_point_group_A == (
            ((1, 0), (0, 1)),
        )
        assert capture.search_contexts[0].surface_point_group_B == (
            ((1, 0), (0, 1)),
        )
        assert capture.search_contexts[0].area_admissible_index_pairs
        payload = {
            "search_context": capture.search_contexts[0].to_dict(),
            "records": [record.to_dict() for record in capture.records],
        }
        encoded = json.dumps(
            payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payloads.append((len(capture.records), sha256(encoded).hexdigest()))

    assert payloads[0][0] > 0
    assert payloads[0] == payloads[1]


def test_trace_scope_is_nested_and_does_not_leak() -> None:
    outer: list[_AdmittedMatchTraceRecord] = []
    inner: list[_AdmittedMatchTraceRecord] = []

    with _observe_admitted_match_records(outer.append):
        _run_square()
        first_count = len(outer)
        with _observe_admitted_match_records(inner.append):
            _run_square()

    assert first_count > 0
    assert len(outer) == 2 * first_count
    assert len(inner) == first_count

    _run_square()
    assert len(outer) == 2 * first_count
    assert len(inner) == first_count


def test_trace_is_emitted_immediately_before_candidate_aggregation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, tuple[int, ...]]] = []
    original = orchestrator._consider_candidate

    def wrapped(*args, pair_canonicalization, **kwargs):
        events.append(("consider", pair_canonicalization.key))
        return original(
            *args,
            pair_canonicalization=pair_canonicalization,
            **kwargs,
        )

    monkeypatch.setattr(orchestrator, "_consider_candidate", wrapped)
    with _observe_admitted_match_records(
        lambda record: events.append(("trace", record.final_pair_key))
    ):
        _run_square()

    assert events
    assert len(events) % 2 == 0
    for index in range(0, len(events), 2):
        assert events[index][0] == "trace"
        assert events[index + 1][0] == "consider"
        assert events[index][1] == events[index + 1][1]
