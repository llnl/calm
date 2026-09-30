"""Authoritative prototype buildability checks.

The current checker operates only on typed project records and current
repository/identifier contracts.  It does not probe historical record shapes
or suppress repository defects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from ..domain.models import Prototype, Slab
from ..ports.uow import UnitOfWork

_SUPERCELL_FIELDS = frozenset({"k", "N_tot", "R_sup", "hnf_key_pg", "cond"})


@dataclass(frozen=True)
class PrototypeBuildability:
    prototype_uid_full: str | None
    prototype_id_short: str | None
    reconstructable: bool
    buildable: bool
    reasons: list[str]
    slab_a_uid_full: str | None
    slab_b_uid_full: str | None
    slab_a_id_short: str | None
    slab_b_id_short: str | None


def _resolve_prototype_identifier(uow: UnitOfWork, identifier: str) -> str:
    """Resolve a current prototype identifier.

    A missing identifier is a normal buildability outcome, so ``KeyError`` is
    converted to a lookup of the supplied value.  Wrong-kind and ambiguous
    identifiers remain hard errors.
    """

    try:
        return uow.ids.resolve_prototype(identifier)
    except KeyError:
        return identifier


def _slab_has_atoms(slab: Slab | None) -> bool:
    if slab is None or not isinstance(slab.payload, Mapping):
        return False
    structure = slab.payload.get("structure")
    return isinstance(structure, Mapping) and structure.get("atoms") is not None


def _prototype_has_supercells(prototype: Prototype) -> bool:
    payload = prototype.payload
    if not isinstance(payload, Mapping):
        return False
    for key in ("supercell_a", "supercell_b"):
        recipe = payload.get(key)
        if not isinstance(recipe, Mapping) or not _SUPERCELL_FIELDS <= set(recipe):
            return False
    return True


def _missing_prototype(uid_full: str) -> PrototypeBuildability:
    return PrototypeBuildability(
        prototype_uid_full=uid_full,
        prototype_id_short=None,
        reconstructable=False,
        buildable=False,
        reasons=["prototype_not_found"],
        slab_a_uid_full=None,
        slab_b_uid_full=None,
        slab_a_id_short=None,
        slab_b_id_short=None,
    )


def _evaluate_prototype(
    prototype: Prototype,
    slabs: Mapping[str, Slab],
) -> PrototypeBuildability:
    slab_a_uid = prototype.slab_a_uid_full
    slab_b_uid = prototype.slab_b_uid_full
    slab_a = slabs.get(slab_a_uid)
    slab_b = slabs.get(slab_b_uid)

    reasons: list[str] = []
    if slab_a is None:
        reasons.append("slab_a_not_found")
    if slab_b is None:
        reasons.append("slab_b_not_found")

    reconstructable = slab_a is not None and slab_b is not None

    if not _slab_has_atoms(slab_a):
        reasons.append("slab_a_missing_atoms")
    if not _slab_has_atoms(slab_b):
        reasons.append("slab_b_missing_atoms")
    if not _prototype_has_supercells(prototype):
        reasons.append("missing_supercell")

    buildable = not reasons
    return PrototypeBuildability(
        prototype_uid_full=prototype.uid_full,
        prototype_id_short=prototype.id_short,
        reconstructable=reconstructable,
        buildable=buildable,
        reasons=["ok"] if buildable else reasons,
        slab_a_uid_full=slab_a_uid,
        slab_b_uid_full=slab_b_uid,
        slab_a_id_short=slab_a.id_short if slab_a is not None else None,
        slab_b_id_short=slab_b.id_short if slab_b is not None else None,
    )


def check_prototype_buildability(
    uow: UnitOfWork,
    prototype: str,
) -> PrototypeBuildability:
    """Check one persisted prototype through current authoritative records."""

    return check_prototypes_buildability(uow, [prototype])[prototype]


def check_prototypes_buildability(
    uow: UnitOfWork,
    prototype_identifiers: Sequence[str],
) -> dict[str, PrototypeBuildability]:
    """Check persisted prototypes in one batch.

    The returned mapping is keyed by each requested identifier.  Every result
    carries the resolved canonical prototype UID when the record exists.
    """

    requested = list(prototype_identifiers)
    if not requested:
        return {}

    resolved = [
        _resolve_prototype_identifier(uow, identifier) for identifier in requested
    ]
    prototypes = uow.prototypes.get_many_by_uid_full(resolved)
    prototype_by_uid = {prototype.uid_full: prototype for prototype in prototypes}

    slab_uids = {
        uid
        for prototype in prototypes
        for uid in (
            prototype.slab_a_uid_full,
            prototype.slab_b_uid_full,
        )
    }
    slabs = uow.slabs.get_many_by_uid_full(sorted(slab_uids))
    slab_by_uid = {slab.uid_full: slab for slab in slabs}

    results: dict[str, PrototypeBuildability] = {}
    for identifier, uid_full in zip(requested, resolved, strict=True):
        prototype = prototype_by_uid.get(uid_full)
        results[identifier] = (
            _missing_prototype(uid_full)
            if prototype is None
            else _evaluate_prototype(prototype, slab_by_uid)
        )
    return results
