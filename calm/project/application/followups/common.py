"""Common utilities for followup operations."""

from __future__ import annotations

from typing import Sequence

from ...ports.uow import UnitOfWork


class FollowupTargetNotFoundError(KeyError):
    """Requested follow-up target does not exist in authoritative storage."""


class InvalidFollowupTargetError(ValueError):
    """Resolved identifier names an unsupported follow-up target kind."""


def _resolved_followup_target(
    uow: UnitOfWork,
    *,
    identifier: str,
    target_uid_full: str,
) -> dict[str, str]:
    """Return one exact follow-up target after authoritative ID resolution."""

    if target_uid_full.startswith("proto:"):
        prototype = uow.prototypes.get_by_uid_full(target_uid_full)
        if prototype is None:
            raise FollowupTargetNotFoundError(
                f"No prototype found for identifier {identifier!r}"
            )
        return {
            "target_uid_full": target_uid_full,
            "target_kind": "prototype",
            "prototype_uid_full": target_uid_full,
        }

    if target_uid_full.startswith("iface:"):
        interface = uow.derived_interfaces.get_by_uid_full(target_uid_full)
        if interface is None:
            raise FollowupTargetNotFoundError(
                f"No derived interface found for identifier {identifier!r}"
            )
        return {
            "target_uid_full": target_uid_full,
            "target_kind": "interface",
            "prototype_uid_full": interface.prototype_uid_full,
        }

    raise InvalidFollowupTargetError(
        "Followups currently accept prototype or derived-interface identifiers only. "
        f"Got {identifier!r}."
    )


def resolve_followup_targets(
    uow: UnitOfWork, identifiers: Sequence[str]
) -> list[dict[str, str]]:
    """Resolve prototype or derived-interface identifiers exactly.

    Missing, ambiguous, wrong-kind, and infrastructure failures all propagate.
    Call :func:`resolve_followup_targets_as_results` only when per-target
    user-input failures should be represented as skipped results.
    """

    resolved: list[dict[str, str]] = []
    for identifier in identifiers:
        target_uid_full = uow.ids.resolve(identifier)
        resolved.append(
            _resolved_followup_target(
                uow,
                identifier=identifier,
                target_uid_full=target_uid_full,
            )
        )
    return resolved


def resolve_followup_targets_as_results(
    uow: UnitOfWork,
    identifiers: Sequence[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Resolve targets while representing only expected input errors as skipped.

    ``KeyError`` and ``ValueError`` from authoritative identifier resolution are
    user-addressable target-selection errors. Database, transaction, and other
    operational failures are not equivalent to skipped science and therefore
    propagate unchanged.
    """

    resolved_targets: list[dict[str, str]] = []
    unresolved_results: list[dict[str, str]] = []

    for identifier in identifiers:
        try:
            target_uid_full = uow.ids.resolve(identifier)
        except KeyError as exc:
            unresolved_results.append(
                {
                    "target_uid": identifier,
                    "target_kind": "unknown",
                    "prototype_uid": "",
                    "status": "skipped",
                    "reason": "target_not_found",
                    "message": str(exc),
                }
            )
            continue
        except ValueError as exc:
            unresolved_results.append(
                {
                    "target_uid": identifier,
                    "target_kind": "unknown",
                    "prototype_uid": "",
                    "status": "skipped",
                    "reason": "invalid_identifier",
                    "message": str(exc),
                }
            )
            continue

        try:
            target = _resolved_followup_target(
                uow,
                identifier=identifier,
                target_uid_full=target_uid_full,
            )
        except FollowupTargetNotFoundError as exc:
            unresolved_results.append(
                {
                    "target_uid": identifier,
                    "target_kind": "unknown",
                    "prototype_uid": "",
                    "status": "skipped",
                    "reason": "target_not_found",
                    "message": str(exc),
                }
            )
            continue
        except InvalidFollowupTargetError as exc:
            unresolved_results.append(
                {
                    "target_uid": identifier,
                    "target_kind": "unknown",
                    "prototype_uid": "",
                    "status": "skipped",
                    "reason": "invalid_identifier",
                    "message": str(exc),
                }
            )
            continue

        resolved_targets.append(target)

    return resolved_targets, unresolved_results


def persisted_followup_uid(
    *,
    run_uid_full: str,
    prototype_uid_full: str,
    target_uid_full: str | None,
    target_kind: str | None,
    kind: str,
    qualifiers: dict | None = None,
) -> str:
    """Return the canonical persisted follow-up identity."""

    from calm.project.domain.identity_v2 import (
        followup_identity_payload,
        persisted_entity_uid_v2,
    )

    return persisted_entity_uid_v2(
        "followup_result",
        followup_identity_payload(
            run_uid_full=run_uid_full,
            prototype_uid_full=prototype_uid_full,
            target_uid_full=target_uid_full,
            target_kind=target_kind,
            kind=kind,
            qualifiers=qualifiers,
        ),
    )
