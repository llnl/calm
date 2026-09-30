"""Repository for refinement and energy follow-up results."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import Connection, insert, select

from calm.project.domain.contracts.energy_result import (
    ENERGY_RESULT_KINDS,
    canonical_energy_result_payload,
    energy_result_identity_qualifiers,
)
from calm.project.domain.contracts.refinement_result import (
    REFINEMENT_RESULT_KINDS,
    canonical_refinement_result_payload,
)
from calm.project.domain.identity_v2 import (
    followup_identity_payload,
    persisted_entity_uid_v2,
)
from ....domain.models import FollowupResult
from ....ports.repos import FollowupResultRepository
from ..tables import followup_results as followup_results_t
from ..tables import prototypes as prototypes_t
from ..tables import runs as runs_t


_FOLLOWUP_STATUS_PAYLOAD_KEY = "_calm_followup_status"


class SqlAlchemyFollowupResultRepository(FollowupResultRepository):
    """SQLAlchemy repository for follow-up result summaries."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def upsert_many(self, results: Sequence[FollowupResult]) -> list[FollowupResult]:
        saved: list[FollowupResult] = []
        for res in results:
            payload = dict(res.payload or {})
            if res.kind in REFINEMENT_RESULT_KINDS:
                payload = canonical_refinement_result_payload(
                    kind=res.kind,
                    payload=payload,
                    prototype_uid_full=res.prototype_uid_full,
                    target_uid_full=res.target_uid_full,
                    target_kind=res.target_kind,
                    best_energy=res.best_energy,
                    param1=res.param1,
                    param2=res.param2,
                    n_points=res.n_points,
                )
                expected_uid = persisted_entity_uid_v2(
                    "followup_result",
                    followup_identity_payload(
                        run_uid_full=str(res.run_uid_full),
                        prototype_uid_full=str(res.prototype_uid_full),
                        target_uid_full=res.target_uid_full,
                        target_kind=res.target_kind,
                        kind=res.kind,
                    ),
                )
                if res.uid_full != expected_uid:
                    raise ValueError(
                        "Refinement follow-up identity does not match its "
                        "authoritative run and target columns."
                    )
            elif res.kind in ENERGY_RESULT_KINDS:
                payload = canonical_energy_result_payload(
                    kind=res.kind,
                    status=str(res.status or "done"),
                    payload=payload,
                    prototype_uid_full=res.prototype_uid_full,
                    target_uid_full=res.target_uid_full,
                    target_kind=res.target_kind,
                    best_energy=res.best_energy,
                    param1=res.param1,
                    param2=res.param2,
                    n_points=res.n_points,
                )
                expected_uid = persisted_entity_uid_v2(
                    "followup_result",
                    followup_identity_payload(
                        run_uid_full=str(res.run_uid_full),
                        prototype_uid_full=str(res.prototype_uid_full),
                        target_uid_full=res.target_uid_full,
                        target_kind=res.target_kind,
                        kind=res.kind,
                        qualifiers=energy_result_identity_qualifiers(
                            kind=res.kind,
                            payload=payload,
                        ),
                    ),
                )
                if res.uid_full != expected_uid:
                    raise ValueError(
                        "Energy follow-up identity does not match its authoritative "
                        "run, target, and result qualifier columns."
                    )

            existing = self.get_by_uid_full(res.uid_full)
            if existing is not None:
                if res.kind in REFINEMENT_RESULT_KINDS | ENERGY_RESULT_KINDS:
                    if (
                        existing.status != str(res.status or "done")
                        or existing.payload != payload
                        or existing.best_energy != res.best_energy
                        or existing.param1 != res.param1
                        or existing.param2 != res.param2
                        or existing.n_points != res.n_points
                    ):
                        category = (
                            "refinement"
                            if res.kind in REFINEMENT_RESULT_KINDS
                            else "energy"
                        )
                        raise ValueError(
                            f"A {category} follow-up already exists for this run "
                            "and target with different scientific results."
                        )
                saved.append(existing)
                continue

            payload[_FOLLOWUP_STATUS_PAYLOAD_KEY] = str(res.status or "done")
            self._conn.execute(
                insert(followup_results_t).values(
                    uid_full=res.uid_full,
                    id_short=res.id_short,
                    run_uid_full=res.run_uid_full,
                    prototype_uid_full=res.prototype_uid_full,
                    target_uid_full=res.target_uid_full,
                    target_kind=res.target_kind,
                    kind=res.kind,
                    best_energy=res.best_energy,
                    param1=res.param1,
                    param2=res.param2,
                    n_points=res.n_points,
                    payload_json=json.dumps(
                        payload,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                )
            )
            saved.append(res)

        return saved

    def get_by_uid_full(self, uid_full: str) -> Optional[FollowupResult]:
        cond_run = runs_t.c.uid_full == followup_results_t.c.run_uid_full
        cond_proto = prototypes_t.c.uid_full == followup_results_t.c.prototype_uid_full

        join_expr = followup_results_t.join(runs_t, cond_run).join(
            prototypes_t, cond_proto
        )

        stmt = (
            select(
                followup_results_t,
                runs_t.c.id_short.label("run_id_short"),
                prototypes_t.c.id_short.label("prototype_id_short"),
            )
            .select_from(join_expr)
            .where(followup_results_t.c.uid_full == uid_full)
        )
        row = self._conn.execute(stmt).mappings().first()
        return _followup_from_row(row) if row else None

    def list(
        self,
        *,
        run_uid_full: Optional[str] = None,
        prototype_uid_full: Optional[str] = None,
        target_uid_full: Optional[str] = None,
        target_kind: Optional[str] = None,
        kind: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[FollowupResult]:
        stmt = select(
            followup_results_t,
            runs_t.c.id_short.label("run_id_short"),
            prototypes_t.c.id_short.label("prototype_id_short"),
        )
        j = followup_results_t.join(
            runs_t,
            runs_t.c.uid_full == followup_results_t.c.run_uid_full,
        ).join(
            prototypes_t,
            prototypes_t.c.uid_full == followup_results_t.c.prototype_uid_full,
        )
        stmt = stmt.select_from(j)

        if run_uid_full is not None:
            stmt = stmt.where(followup_results_t.c.run_uid_full == run_uid_full)
        if prototype_uid_full is not None:
            stmt = stmt.where(
                followup_results_t.c.prototype_uid_full == prototype_uid_full
            )
        if target_uid_full is not None:
            stmt = stmt.where(followup_results_t.c.target_uid_full == target_uid_full)
        if target_kind is not None:
            stmt = stmt.where(followup_results_t.c.target_kind == target_kind)
        if kind is not None:
            stmt = stmt.where(followup_results_t.c.kind == kind)

        stmt = stmt.order_by(followup_results_t.c.created_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        rows = self._conn.execute(stmt).mappings().all()
        return [_followup_from_row(r) for r in rows]


def _followup_from_row(row: Mapping[str, object]) -> FollowupResult:
    payload_json = row.get("payload_json")
    payload: dict[str, Any]
    if isinstance(payload_json, str) and payload_json:
        decoded = json.loads(payload_json)
        if not isinstance(decoded, dict):
            raise ValueError("Current follow-up payload_json must decode to a mapping.")
        payload = decoded
    else:
        payload = {}

    try:
        status = str(payload.pop(_FOLLOWUP_STATUS_PAYLOAD_KEY))
    except KeyError as exc:
        raise ValueError(
            "Persisted follow-up payload is missing the required status marker."
        ) from exc

    run_id_short_val = (
        str(row.get("run_id_short")) if row.get("run_id_short") is not None else None
    )
    prototype_id_short_val = (
        str(row.get("prototype_id_short"))
        if row.get("prototype_id_short") is not None
        else None
    )
    target_uid_full_val = (
        str(row.get("target_uid_full"))
        if row.get("target_uid_full") is not None
        else None
    )
    target_kind_val = (
        str(row.get("target_kind")) if row.get("target_kind") is not None else None
    )
    kind = str(row["kind"])
    prototype_uid_full = str(row["prototype_uid_full"])
    if kind in REFINEMENT_RESULT_KINDS:
        payload = canonical_refinement_result_payload(
            kind=kind,
            payload=payload,
            prototype_uid_full=prototype_uid_full,
            target_uid_full=target_uid_full_val,
            target_kind=target_kind_val,
            best_energy=(
                float(row["best_energy"])
                if row.get("best_energy") is not None
                else None
            ),
            param1=(float(row["param1"]) if row.get("param1") is not None else None),
            param2=(float(row["param2"]) if row.get("param2") is not None else None),
            n_points=(
                int(row["n_points"]) if row.get("n_points") is not None else None
            ),
        )
        expected_uid = persisted_entity_uid_v2(
            "followup_result",
            followup_identity_payload(
                run_uid_full=str(row["run_uid_full"]),
                prototype_uid_full=prototype_uid_full,
                target_uid_full=target_uid_full_val,
                target_kind=target_kind_val,
                kind=kind,
            ),
        )
        if str(row["uid_full"]) != expected_uid:
            raise ValueError(
                "Persisted refinement follow-up identity does not match its "
                "authoritative run and target columns."
            )
    elif kind in ENERGY_RESULT_KINDS:
        payload = canonical_energy_result_payload(
            kind=kind,
            status=status,
            payload=payload,
            prototype_uid_full=prototype_uid_full,
            target_uid_full=target_uid_full_val,
            target_kind=target_kind_val,
            best_energy=(
                float(row["best_energy"])
                if row.get("best_energy") is not None
                else None
            ),
            param1=(float(row["param1"]) if row.get("param1") is not None else None),
            param2=(float(row["param2"]) if row.get("param2") is not None else None),
            n_points=(
                int(row["n_points"]) if row.get("n_points") is not None else None
            ),
        )
        expected_uid = persisted_entity_uid_v2(
            "followup_result",
            followup_identity_payload(
                run_uid_full=str(row["run_uid_full"]),
                prototype_uid_full=prototype_uid_full,
                target_uid_full=target_uid_full_val,
                target_kind=target_kind_val,
                kind=kind,
                qualifiers=energy_result_identity_qualifiers(
                    kind=kind,
                    payload=payload,
                ),
            ),
        )
        if str(row["uid_full"]) != expected_uid:
            raise ValueError(
                "Persisted energy follow-up identity does not match its "
                "authoritative run, target, and result qualifiers."
            )

    return FollowupResult(
        uid_full=str(row["uid_full"]),
        id_short=str(row["id_short"]),
        run_uid_full=str(row["run_uid_full"]),
        run_id_short=run_id_short_val,
        prototype_uid_full=prototype_uid_full,
        prototype_id_short=prototype_id_short_val,
        target_uid_full=target_uid_full_val,
        target_kind=target_kind_val,
        kind=kind,
        status=status,
        best_energy=(
            float(row["best_energy"]) if row.get("best_energy") is not None else None
        ),
        param1=float(row["param1"]) if row.get("param1") is not None else None,
        param2=float(row["param2"]) if row.get("param2") is not None else None,
        n_points=int(row["n_points"]) if row.get("n_points") is not None else None,
        payload=payload,
        created_at=(
            str(row.get("created_at")) if row.get("created_at") is not None else None
        ),
    )
