"""Canonical identities for persisted CALM project entities.

CALM stable writes one version-2 identity representation for every persisted
entity. This module owns the entity-specific payload schemas used by all current
writers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from calm.keys._canonical_v2 import (
    CanonicalIdentityDomain,
    canonical_identity_digest_v2,
)
from calm.keys.uid import _prototype_uid_v3_payload

PERSISTED_ENTITY_IDENTITY_SCHEMA = "calm.persisted_entity_identity"
PERSISTED_ENTITY_IDENTITY_VERSION = 2
ARTIFACT_IDENTITY_METADATA_KEY = "_calm_artifact_identity"

_ENTITY_PREFIXES: dict[str, str] = {
    "bulk": "bulk",
    "calculator": "calc",
    "slab": "slab",
    "run": "run",
    "artifact": "artifact",
    "prototype": "proto",
    "derived_interface": "iface",
    "followup_result": "followup",
    "dataset": "dataset",
    "dataset_item": "dataset_item",
    "campaign": "campaign",
    "campaign_run": "campaign_run",
}

_ENTITY_DOMAINS: dict[str, CanonicalIdentityDomain] = {
    "bulk": CanonicalIdentityDomain.SCIENTIFIC_IDENTITY,
    "calculator": CanonicalIdentityDomain.APPLICATION_IDENTITY,
    "slab": CanonicalIdentityDomain.SCIENTIFIC_IDENTITY,
    "run": CanonicalIdentityDomain.APPLICATION_IDENTITY,
    "artifact": CanonicalIdentityDomain.APPLICATION_IDENTITY,
    "prototype": CanonicalIdentityDomain.SCIENTIFIC_IDENTITY,
    "derived_interface": CanonicalIdentityDomain.SCIENTIFIC_IDENTITY,
    "followup_result": CanonicalIdentityDomain.APPLICATION_IDENTITY,
    "dataset": CanonicalIdentityDomain.DATASET_DECLARATION,
    "dataset_item": CanonicalIdentityDomain.APPLICATION_IDENTITY,
    "campaign": CanonicalIdentityDomain.CAMPAIGN_IDENTITY,
    "campaign_run": CanonicalIdentityDomain.APPLICATION_IDENTITY,
}

_V2_UID_RE = re.compile(r"^[a-z][a-z0-9_]*:v2:[0-9a-f]{64}$")


class PersistedEntityIdentityError(ValueError):
    """A persisted version-2 identity payload is malformed."""


def is_persisted_uid_v2(value: object, *, entity_kind: str | None = None) -> bool:
    if type(value) is not str or _V2_UID_RE.fullmatch(value) is None:
        return False
    if entity_kind is None:
        return True
    prefix = _ENTITY_PREFIXES.get(entity_kind)
    return prefix is not None and value.startswith(f"{prefix}:v2:")


def persisted_entity_uid_v2(entity_kind: str, identity_payload: Any) -> str:
    """Return one domain-separated, type-tagged persisted entity UID."""

    if entity_kind not in _ENTITY_PREFIXES:
        raise PersistedEntityIdentityError(
            f"Unsupported persisted entity kind {entity_kind!r}."
        )
    envelope = {
        "schema": PERSISTED_ENTITY_IDENTITY_SCHEMA,
        "version": PERSISTED_ENTITY_IDENTITY_VERSION,
        "entity_kind": entity_kind,
        "identity_payload": identity_payload,
    }
    digest = canonical_identity_digest_v2(
        envelope,
        domain=_ENTITY_DOMAINS[entity_kind],
    )
    return f"{_ENTITY_PREFIXES[entity_kind]}:v2:{digest}"


def calculator_identity_payload(*, spec: Mapping[str, Any]) -> dict[str, Any]:
    return {"calculator_spec": dict(spec)}


def bulk_structure_identity_payload(
    *, fingerprint: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "identity_mode": "structure_fingerprint",
        "fingerprint": dict(fingerprint),
    }


def bulk_metadata_identity_payload(*, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "identity_mode": "metadata_payload",
        "payload": dict(payload),
    }


def _exact_miller(miller: Sequence[Any]) -> list[int]:
    values = list(miller)
    if len(values) != 3:
        raise PersistedEntityIdentityError("A slab Miller index must have length 3.")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise PersistedEntityIdentityError(
            "A slab Miller index must contain exact integers."
        )
    return [int(value) for value in values]


def slab_identity_payload(
    *,
    bulk_uid_full: str,
    miller: Sequence[Any],
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact-current scientific identity of a persisted slab."""

    from calm.project.domain.contracts.slab_record import canonical_slab_record_payload

    canonical = canonical_slab_record_payload(
        payload,
        bulk_uid_full=bulk_uid_full,
        miller=miller,
    )
    result: dict[str, Any] = {
        "bulk_uid_full": str(bulk_uid_full),
        "miller": _exact_miller(miller),
        "params": canonical["params"],
        "user_payload": canonical["user_payload"],
        "termination": canonical["termination"],
    }
    atoms = canonical["structure"]["atoms"]
    if atoms is not None:
        result["realized_atoms"] = atoms
    return result


def run_identity_payload(*, run_type: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    return {"run_type": str(run_type), "spec": dict(spec)}


def artifact_storage_metadata(
    metadata: Mapping[str, Any] | None, *, content_sha256: str
) -> dict[str, Any]:
    user = dict(metadata or {})
    if ARTIFACT_IDENTITY_METADATA_KEY in user:
        raise PersistedEntityIdentityError(
            f"Artifact metadata key {ARTIFACT_IDENTITY_METADATA_KEY!r} is reserved."
        )
    digest = str(content_sha256)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise PersistedEntityIdentityError(
            "Artifact content_sha256 must contain 64 lowercase hexadecimal characters."
        )
    user[ARTIFACT_IDENTITY_METADATA_KEY] = {
        "schema": "calm.artifact_identity",
        "version": 2,
        "content_sha256": digest,
    }
    return user


def _artifact_identity_record(
    stored_metadata: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    record = dict(stored_metadata or {}).get(ARTIFACT_IDENTITY_METADATA_KEY)
    if record is None:
        return None
    if not isinstance(record, Mapping):
        raise PersistedEntityIdentityError(
            "Artifact identity metadata must be a mapping."
        )
    if record.get("schema") != "calm.artifact_identity" or record.get("version") != 2:
        raise PersistedEntityIdentityError(
            "Artifact identity metadata has an unsupported schema envelope."
        )
    value = record.get("content_sha256")
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise PersistedEntityIdentityError(
            "Artifact identity metadata contains an invalid content_sha256."
        )
    return record


def artifact_user_metadata(
    stored_metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    user = dict(stored_metadata or {})
    if _artifact_identity_record(stored_metadata) is not None:
        user.pop(ARTIFACT_IDENTITY_METADATA_KEY, None)
    return user


def artifact_content_sha256(
    stored_metadata: Mapping[str, Any] | None,
) -> str | None:
    record = _artifact_identity_record(stored_metadata)
    if record is None:
        return None
    return str(record["content_sha256"])


def artifact_identity_payload(
    *,
    run_uid_full: str,
    kind: str,
    uri: str,
    content_sha256: str,
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    digest = str(content_sha256)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise PersistedEntityIdentityError(
            "Artifact content_sha256 must contain 64 lowercase hexadecimal characters."
        )
    return {
        "run_uid_full": str(run_uid_full),
        "kind": str(kind),
        "uri": str(uri),
        "content_sha256": digest,
        "metadata": dict(metadata or {}),
    }


def prototype_identity_payload(
    *,
    run_uid_full: str,
    slab_a_uid_full: str,
    slab_b_uid_full: str,
    payload: Mapping[str, Any] | None,
    match_score: float | None,
    hencky_norm: float | None,
    interface_area: float | None,
    n_atoms: int | None,
) -> dict[str, Any]:
    stored = dict(payload or {})
    if stored.get("identity_algorithm") != "primitive_coupled_pair_v2":
        raise ValueError(
            "Prototype persistence requires primitive_coupled_pair_v2 identity"
        )
    pair_identity = stored.get("pair_identity")
    if not isinstance(pair_identity, Mapping):
        raise ValueError("primitive_coupled_pair_v2 payload requires pair_identity")
    return _prototype_uid_v3_payload(
        slab_uid_a=str(slab_a_uid_full),
        slab_uid_b=str(slab_b_uid_full),
        primitive_pair_key=pair_identity.get("primitive_pair_key", ()),
        pair_key_version=pair_identity.get("key_version"),
        pair_symmetry_policy=pair_identity.get("pair_symmetry_policy"),
        correspondence_orientation=pair_identity.get("correspondence_orientation"),
        material_exchange_identified=pair_identity.get("material_exchange_identified"),
    )


def derived_interface_identity_payload(
    *, prototype_uid_full: str, spec: Mapping[str, Any]
) -> dict[str, Any]:
    canonical_spec = dict(spec)
    for key in ("atoms", "atoms_artifact_uid", "artifact_refs"):
        canonical_spec.pop(key, None)
    return {
        "prototype_uid_full": str(prototype_uid_full),
        "spec": canonical_spec,
    }


def followup_identity_payload(
    *,
    run_uid_full: str,
    prototype_uid_full: str,
    target_uid_full: str | None,
    target_kind: str | None,
    kind: str,
    qualifiers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "run_uid_full": str(run_uid_full),
        "prototype_uid_full": str(prototype_uid_full),
        "target_uid_full": None if target_uid_full is None else str(target_uid_full),
        "target_kind": None if target_kind is None else str(target_kind),
        "kind": str(kind),
        "qualifiers": dict(qualifiers or {}),
    }


def dataset_identity_payload(
    *, name: str, settings: Mapping[str, Any]
) -> dict[str, Any]:
    return {"name": str(name), "settings": dict(settings)}


def dataset_item_identity_payload(
    *, dataset_uid_full: str, source_uid_full: str
) -> dict[str, Any]:
    return {
        "dataset_uid_full": str(dataset_uid_full),
        "source_uid_full": str(source_uid_full),
    }


def campaign_identity_payload(
    *, name: str | None, spec: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "name": None if name is None else str(name),
        "spec": dict(spec),
    }


def campaign_run_identity_payload(
    *, campaign_uid_full: str, run_spec_hash: str, backend_id: str | None
) -> dict[str, Any]:
    return {
        "campaign_uid_full": str(campaign_uid_full),
        "run_spec_hash": str(run_spec_hash),
        "backend_id": str(backend_id or ""),
    }


def persisted_entity_identity_contract_v2() -> dict[str, Any]:
    return {
        "schema": PERSISTED_ENTITY_IDENTITY_SCHEMA,
        "version": PERSISTED_ENTITY_IDENTITY_VERSION,
        "uid_shape": "<entity-prefix>:v2:<sha256-lowercase-hex>",
        "domains": {
            kind: _ENTITY_DOMAINS[kind].value for kind in sorted(_ENTITY_DOMAINS)
        },
        "entity_prefixes": dict(sorted(_ENTITY_PREFIXES.items())),
        "writer_policy": "emit_only_v2_uids",
        "mutable_fields_excluded": {
            "prototype": ["pareto", "is_pareto", "pareto_rank"],
            "derived_interface": [
                "label",
                "atoms",
                "atoms_artifact_uid",
                "artifact_refs",
            ],
            "followup_result": ["status", "result_payload", "summary_scalars"],
        },
    }
