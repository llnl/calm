"""Repository for exact derived-interface records."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from sqlalchemy import Connection, asc, desc, insert, select, update
from sqlalchemy.sql import func

from calm.project.domain.contracts.derived_interface import (
    canonical_derived_interface_spec,
)
from calm.project.domain.identity_v2 import (
    derived_interface_identity_payload,
    persisted_entity_uid_v2,
)
from ....domain.models import DerivedInterface
from ....ports.ids import IdResolver
from ....ports.repos import DerivedInterfaceRepository
from ..tables import derived_interfaces as derived_interfaces_t
from ._common import datetime_to_text as _dt_to_str


def _derived_interface_spec_json(spec: Mapping[str, Any]) -> str:
    """Serialize an identity-bearing current spec without numeric rounding."""

    return json.dumps(
        dict(spec),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


class SqlAlchemyDerivedInterfaceRepository(DerivedInterfaceRepository):
    def __init__(self, conn: Connection, *, ids: IdResolver):
        self._conn = conn
        self._ids = ids

    def upsert(self, iface: DerivedInterface) -> DerivedInterface:
        spec = canonical_derived_interface_spec(
            iface.spec,
            prototype_uid_full=iface.prototype_uid_full,
        )
        expected_uid = persisted_entity_uid_v2(
            "derived_interface",
            derived_interface_identity_payload(
                prototype_uid_full=iface.prototype_uid_full,
                spec=spec,
            ),
        )
        if iface.uid_full != expected_uid:
            raise ValueError(
                "Derived-interface uid_full does not match its exact current spec."
            )
        existing = self.get_by_uid_full(iface.uid_full)
        if existing is not None:
            existing_identity = derived_interface_identity_payload(
                prototype_uid_full=existing.prototype_uid_full,
                spec=existing.spec,
            )
            incoming_identity = derived_interface_identity_payload(
                prototype_uid_full=iface.prototype_uid_full,
                spec=spec,
            )
            if existing_identity != incoming_identity:
                raise ValueError(
                    "Derived-interface UID collision across distinct current specs."
                )

            values: dict[str, Any] = {}
            if iface.label is not None and iface.label != existing.label:
                values["label"] = iface.label

            existing_artifact_uid = existing.atoms_artifact_uid
            incoming_artifact_uid = iface.atoms_artifact_uid
            if incoming_artifact_uid is not None:
                if existing_artifact_uid is None:
                    values["spec_json"] = _derived_interface_spec_json(spec)
                elif existing_artifact_uid != incoming_artifact_uid:
                    raise ValueError(
                        "A derived interface cannot own conflicting atoms artifacts."
                    )
                elif existing.spec != spec:
                    raise ValueError(
                        "A derived interface cannot change current artifact "
                        "reference metadata."
                    )

            if not values:
                return existing
            values["updated_at"] = func.current_timestamp()
            stmt = (
                update(derived_interfaces_t)
                .where(derived_interfaces_t.c.uid_full == iface.uid_full)
                .values(**values)
            )
            self._conn.execute(stmt)
            refreshed = self.get_by_uid_full(iface.uid_full)
            return refreshed if refreshed is not None else iface

        values = {
            "uid_full": iface.uid_full,
            "id_short": iface.id_short,
            "prototype_uid_full": iface.prototype_uid_full,
            "label": iface.label,
            "spec_json": _derived_interface_spec_json(spec),
        }
        self._conn.execute(insert(derived_interfaces_t).values(**values))
        return iface

    def get_by_uid_full(self, uid_full: str) -> Optional[DerivedInterface]:
        stmt = select(derived_interfaces_t).where(
            derived_interfaces_t.c.uid_full == uid_full
        )
        row = self._conn.execute(stmt).mappings().first()
        return _derived_interface_from_row(row) if row is not None else None

    def list(
        self,
        *,
        prototype_uid_full: str | None = None,
        limit: int | None = None,
        order_by: str | None = None,
        descending: bool = True,
    ) -> list[DerivedInterface]:
        stmt = select(derived_interfaces_t)
        if prototype_uid_full:
            stmt = stmt.where(
                derived_interfaces_t.c.prototype_uid_full == prototype_uid_full
            )

        # Allow only a small safe set of order-by columns.
        col = derived_interfaces_t.c.created_at
        if order_by:
            key = order_by.strip().lower()
            if key in {"created_at", "updated_at"}:
                col = getattr(derived_interfaces_t.c, key)
            elif key in {"id", "id_short"}:
                col = derived_interfaces_t.c.id_short
            elif key in {"label"}:
                col = derived_interfaces_t.c.label

        stmt = stmt.order_by(desc(col) if descending else asc(col))

        if limit is not None:
            stmt = stmt.limit(int(limit))

        rows = self._conn.execute(stmt).mappings().all()
        return [_derived_interface_from_row(r) for r in rows]


def _derived_interface_from_row(row: Mapping[str, Any]) -> DerivedInterface:
    uid_raw = row.get("uid_full")
    if not isinstance(uid_raw, str) or not uid_raw or uid_raw != uid_raw.strip():
        raise ValueError("Current derived-interface rows require a non-empty uid_full.")
    uid_full = uid_raw
    id_short_raw = row.get("id_short")
    if (
        not isinstance(id_short_raw, str)
        or not id_short_raw
        or id_short_raw != id_short_raw.strip()
    ):
        raise ValueError("Current derived-interface rows require a non-empty id_short.")
    prototype_raw = row.get("prototype_uid_full")
    if (
        not isinstance(prototype_raw, str)
        or not prototype_raw
        or prototype_raw != prototype_raw.strip()
    ):
        raise ValueError(
            "Current derived-interface rows require a non-empty prototype_uid_full."
        )
    prototype_uid_full = prototype_raw
    spec_raw = row.get("spec_json")
    if not isinstance(spec_raw, str) or not spec_raw:
        raise ValueError("Current derived-interface rows require non-empty spec_json.")
    decoded = json.loads(spec_raw)
    if not isinstance(decoded, Mapping):
        raise ValueError(
            "Current derived-interface spec_json must decode to a mapping."
        )
    spec = canonical_derived_interface_spec(
        decoded,
        prototype_uid_full=prototype_uid_full,
    )
    expected_uid = persisted_entity_uid_v2(
        "derived_interface",
        derived_interface_identity_payload(
            prototype_uid_full=prototype_uid_full,
            spec=spec,
        ),
    )
    if uid_full != expected_uid:
        raise ValueError(
            "Persisted derived-interface identity does not match spec_json."
        )
    return DerivedInterface(
        uid_full=uid_full,
        id_short=id_short_raw,
        prototype_uid_full=prototype_uid_full,
        label=row.get("label"),
        spec=spec,
        created_at=_dt_to_str(row.get("created_at")),
        updated_at=_dt_to_str(row.get("updated_at")),
    )
