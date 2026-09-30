"""Shared exact persistence helpers for follow-up orchestrators."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from calm.serialization.regression import sha256_hex, deterministic_json
from ...domain.models import FollowupResult, Run
from ..artifacts import ArtifactsService
from ...ports.uow import UnitOfWork


def _require_entered_uow(uow: UnitOfWork) -> None:
    """Require callers to own the surrounding transaction scope."""

    depth = getattr(uow, "_depth", None)
    if depth is not None and int(depth) < 1:
        raise ValueError("Follow-up persistence helpers require an entered UnitOfWork.")


def load_existing_followups(
    uow: UnitOfWork,
    *,
    run_uid_full: str,
    kind: str,
    targets: Iterable[Mapping[str, Any]],
) -> dict[tuple[str, str], FollowupResult]:
    """Return completed current-run follow-ups keyed by prototype and target."""

    _require_entered_uow(uow)
    out: dict[tuple[str, str], FollowupResult] = {}
    seen_prototypes: set[str] = set()
    for target in targets:
        prototype_uid = str(target.get("prototype_uid_full") or "")
        if not prototype_uid or prototype_uid in seen_prototypes:
            continue
        seen_prototypes.add(prototype_uid)
        rows = uow.followups.list(
            run_uid_full=run_uid_full,
            prototype_uid_full=prototype_uid,
            kind=kind,
            limit=100000,
        )
        for row in rows:
            if str(row.status) not in {"done", "completed"}:
                continue
            target_uid = str(row.target_uid_full or "")
            if not target_uid:
                raise ValueError(
                    f"Persisted {kind} follow-up {row.uid_full!r} is missing "
                    "its target identity."
                )
            out[(str(row.prototype_uid_full), target_uid)] = row
    return out


def persist_artifact_payloads(
    uow: UnitOfWork,
    run_uid: str,
    proto_uid: str,
    target_uid: str,
    artifact_payloads: Iterable[Mapping[str, Any]],
    *,
    artifacts: ArtifactsService | None,
) -> list[str]:
    """Persist deterministic JSON artifacts through the current file owner."""

    _require_entered_uow(uow)
    payload_rows = list(artifact_payloads or ())
    if not payload_rows:
        return []
    if artifacts is None:
        raise RuntimeError(
            "Follow-up artifact payloads require an injected ArtifactsService."
        )

    out: list[str] = []
    for index, payload in enumerate(payload_rows):
        if not isinstance(payload, Mapping):
            raise TypeError("Follow-up artifact payloads must be mappings.")
        payload_obj = dict(payload)
        exact_content = deterministic_json(
            payload_obj,
            float_ndigits=12,
        ).encode("utf-8")
        content_sha = sha256_hex(exact_content)
        target_sha = sha256_hex(
            deterministic_json(
                {
                    "prototype_uid_full": str(proto_uid),
                    "target_uid_full": str(target_uid),
                }
            )
        )
        filename = f"followup_{target_sha[:12]}_{index}_{content_sha[:16]}.json"
        artifact = artifacts.put_bytes_in(
            uow,
            run_uid,
            category="data",
            kind="json",
            filename=filename,
            data=exact_content,
            metadata=payload_obj,
            lineage_payload={
                "prototype_uid_full": str(proto_uid),
                "target_uid_full": str(target_uid),
                "index": index,
            },
        )
        out.append(artifact.uid_full)
    return out


def persist_followups_with_edges(
    uow: UnitOfWork,
    followups: Iterable[FollowupResult],
) -> list[FollowupResult]:
    """Persist follow-ups and all mandatory lineage in the active transaction."""

    _require_entered_uow(uow)
    rows = list(followups)
    if not rows:
        return []
    stored = uow.followups.upsert_many(rows)
    if len(stored) != len(rows):
        raise RuntimeError(
            "Follow-up repository did not return one authoritative record per input."
        )
    for requested, persisted in zip(rows, stored, strict=True):
        if persisted.uid_full != requested.uid_full:
            raise RuntimeError(
                "Follow-up repository returned an unexpected persisted identity."
            )
        uow.edges.add(
            src_uid_full=persisted.run_uid_full,
            dst_uid_full=persisted.uid_full,
            kind="run_to_followup",
            payload={"kind": persisted.kind},
        )
        uow.edges.add(
            src_uid_full=persisted.prototype_uid_full,
            dst_uid_full=persisted.uid_full,
            kind="prototype_to_followup",
            payload={"kind": persisted.kind},
        )
        if persisted.target_kind == "interface":
            if not persisted.target_uid_full:
                raise ValueError(
                    f"Interface follow-up {persisted.uid_full!r} is missing "
                    "target_uid_full."
                )
            uow.edges.add(
                src_uid_full=persisted.target_uid_full,
                dst_uid_full=persisted.uid_full,
                kind="interface_to_followup",
                payload={"kind": persisted.kind},
            )
    return stored


def create_run_and_maybe_short_circuit(
    runs_service: Any,
    run_type: str,
    spec: dict[str, Any],
    targets: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
    resume: bool,
) -> tuple[Run, list[dict[str, Any]] | None]:
    """Create a run and return exact skipped rows for a completed run."""

    run = runs_service.create(run_type=run_type, spec=spec)
    if not (resume and run.status == "done"):
        return run, None

    results = [
        {
            "target_uid": target.get("target_uid_full")
            or target.get("prototype_uid_full"),
            "target_kind": target.get("target_kind") or "prototype",
            "prototype_uid": target.get("prototype_uid_full"),
            "status": "skipped",
            "reason": "run_already_done",
            "run_uid": run.uid_full,
        }
        for target in targets
    ]
    for unresolved_row in unresolved:
        row = dict(unresolved_row)
        row["run_uid"] = run.uid_full
        results.append(row)
    return runs_service.get(run.uid_full), results


def finalize_run_state_and_refresh(
    runs_service: Any,
    run: Run,
    results: list[Any],
    n_requested: int,
) -> Run:
    """Persist the exact terminal run state and return the refreshed record."""

    statuses = [
        getattr(result, "status", None)
        if not isinstance(result, Mapping)
        else result.get("status")
        for result in results
    ]
    n_failed = sum(status == "failed" for status in statuses)
    n_completed = sum(status == "completed" for status in statuses)
    if n_failed > 0 and n_completed == 0:
        runs_service.mark_failed(run.uid_full, error={"n_failed": n_failed})
    else:
        runs_service.mark_done(
            run.uid_full,
            progress={
                "n_requested": int(n_requested),
                "n_results": int(n_completed),
                "n_failed": int(n_failed),
            },
        )
    return runs_service.get(run.uid_full)
