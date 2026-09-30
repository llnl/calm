"""Repository for exact current slab records."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping, Optional, Sequence

from sqlalchemy import Connection, insert, select
from sqlalchemy.sql import func

from calm.project.domain.contracts.slab_record import (
    canonical_miller,
    canonical_slab_record_payload,
    slab_atoms_payload,
)
from calm.project.domain.identity_v2 import (
    persisted_entity_uid_v2,
    slab_identity_payload,
)
from ....domain.models import Slab, SlabReferenceRecord, SlabSummary
from ....ports.ids import IdResolver
from ....ports.repos import SlabRepository
from ..payload_helpers import extract_canonical_tilt_metadata
from ..tables import bulks as bulks_t
from ..tables import slabs as slabs_t
from ._common import datetime_to_text as _dt_to_str


def _slab_tilt_columns(
    payload: dict[str, Any],
    *,
    slab_uid_full: str,
) -> dict[str, Any]:
    """Project canonical slab tilt provenance into normalized SQL columns."""

    atoms = slab_atoms_payload(payload)
    if atoms is None:
        return {}

    tilt = extract_canonical_tilt_metadata({"atoms": atoms})
    if tilt is None:
        raise ValueError(
            "Atomistic slab payload is missing canonical "
            "atoms.info['calm:tilt'] metadata for "
            f"uid={slab_uid_full}."
        )

    def finite_number(name: str, value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"Canonical slab tilt field {name!r} must be numeric for "
                f"uid={slab_uid_full}."
            )
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(
                f"Canonical slab tilt field {name!r} must be finite for "
                f"uid={slab_uid_full}."
            )
        return number

    tilt_xy = tilt.get("tilt_xy")
    if not isinstance(tilt_xy, (list, tuple)) or len(tilt_xy) != 2:
        raise ValueError(
            "Canonical slab tilt metadata must contain two-value 'tilt_xy' "
            f"for uid={slab_uid_full}."
        )
    tilt_x = finite_number("tilt_xy[0]", tilt_xy[0])
    tilt_y = finite_number("tilt_xy[1]", tilt_xy[1])
    tilt_magnitude = finite_number(
        "tilt_magnitude",
        tilt.get("tilt_magnitude"),
    )

    required_flags = (
        "has_residual_tilt",
        "orthogonalize_c_applied",
        "integer_c_tilt_reduction_applied",
    )
    for name in required_flags:
        if not isinstance(tilt.get(name), bool):
            raise ValueError(
                f"Canonical slab tilt field {name!r} must be boolean for "
                f"uid={slab_uid_full}."
            )

    values: dict[str, Any] = {
        "tilt_x": tilt_x,
        "tilt_y": tilt_y,
        "tilt_magnitude": tilt_magnitude,
        "has_residual_tilt": tilt["has_residual_tilt"],
        "orthogonalize_c_applied": tilt["orthogonalize_c_applied"],
        "integer_c_tilt_reduction_applied": tilt["integer_c_tilt_reduction_applied"],
    }

    c_tilt_mn = tilt.get("c_tilt_mn")
    if c_tilt_mn is not None:
        if not isinstance(c_tilt_mn, (list, tuple)) or len(c_tilt_mn) != 2:
            raise ValueError(
                "Canonical slab tilt field 'c_tilt_mn' must contain two "
                f"integers for uid={slab_uid_full}."
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int) for value in c_tilt_mn
        ):
            raise ValueError(
                "Canonical slab tilt field 'c_tilt_mn' must contain two "
                f"integers for uid={slab_uid_full}."
            )
        values["c_tilt_m"] = c_tilt_mn[0]
        values["c_tilt_n"] = c_tilt_mn[1]

    return values


class SqlAlchemySlabRepository(SlabRepository):
    def __init__(self, conn: Connection, ids: IdResolver) -> None:
        self._conn = conn
        self._ids = ids

    @staticmethod
    def _payload_json(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def _from_row(self, row: Mapping[str, Any]) -> Slab:
        uid_raw = row.get("uid_full")
        if not isinstance(uid_raw, str) or not uid_raw or uid_raw != uid_raw.strip():
            raise ValueError("Current slab rows require a non-empty uid_full.")
        id_raw = row.get("id_short")
        if not isinstance(id_raw, str) or not id_raw or id_raw != id_raw.strip():
            raise ValueError("Current slab rows require a non-empty id_short.")

        bulk_row = (
            self._conn.execute(
                select(bulks_t.c.uid_full, bulks_t.c.id_short).where(
                    bulks_t.c.bulk_pk == row.get("bulk_pk")
                )
            )
            .mappings()
            .first()
        )
        if bulk_row is None:
            raise ValueError(
                "Current slab rows require a live authoritative parent bulk."
            )
        bulk_uid_full = str(bulk_row["uid_full"])
        bulk_id_short = str(bulk_row["id_short"])

        miller = canonical_miller(
            (row.get("miller_h"), row.get("miller_k"), row.get("miller_l"))
        )
        payload_json = row.get("payload_json")
        if not isinstance(payload_json, str) or not payload_json:
            raise ValueError("Current slab rows require non-empty payload_json.")
        decoded = json.loads(payload_json)
        if not isinstance(decoded, Mapping):
            raise ValueError("Current slab payload_json must decode to a mapping.")
        payload = canonical_slab_record_payload(
            decoded,
            bulk_uid_full=bulk_uid_full,
            miller=miller,
        )
        if payload_json != self._payload_json(payload):
            raise ValueError("Current slab payload_json must be canonical.")

        expected_uid = persisted_entity_uid_v2(
            "slab",
            slab_identity_payload(
                bulk_uid_full=bulk_uid_full,
                miller=miller,
                payload=payload,
            ),
        )
        if uid_raw != expected_uid:
            raise ValueError(
                "Persisted slab identity does not match its current payload."
            )

        expected_tilt = _slab_tilt_columns(payload, slab_uid_full=uid_raw)
        tilt_fields = (
            "tilt_x",
            "tilt_y",
            "tilt_magnitude",
            "has_residual_tilt",
            "orthogonalize_c_applied",
            "integer_c_tilt_reduction_applied",
            "c_tilt_m",
            "c_tilt_n",
        )
        for field in tilt_fields:
            stored_value = row.get(field)
            expected_value = expected_tilt.get(field)
            if stored_value != expected_value:
                raise ValueError(
                    f"Persisted slab {field} projection does not match payload_json."
                )

        return Slab(
            uid_full=uid_raw,
            id_short=id_raw,
            bulk_uid_full=bulk_uid_full,
            bulk_id_short=bulk_id_short,
            miller=miller,
            payload=payload,
            created_at=_dt_to_str(row.get("created_at")),
            updated_at=_dt_to_str(row.get("updated_at")),
        )

    def create_many(self, slabs: Sequence[Slab]) -> list[Slab]:
        out: list[Slab] = []
        for slab in slabs:
            miller = canonical_miller(slab.miller)
            bulk_pk = self._conn.execute(
                select(bulks_t.c.bulk_pk).where(
                    bulks_t.c.uid_full == slab.bulk_uid_full
                )
            ).scalar_one_or_none()
            if bulk_pk is None:
                raise ValueError(
                    "Current slab writes require a live authoritative parent bulk."
                )
            payload = canonical_slab_record_payload(
                slab.payload or {},
                bulk_uid_full=slab.bulk_uid_full,
                miller=miller,
            )
            expected_uid = persisted_entity_uid_v2(
                "slab",
                slab_identity_payload(
                    bulk_uid_full=slab.bulk_uid_full,
                    miller=miller,
                    payload=payload,
                ),
            )
            if slab.uid_full != expected_uid:
                raise ValueError(
                    "Slab uid_full does not match its authoritative parent, Miller "
                    "index, and current payload."
                )
            existing_row = (
                self._conn.execute(
                    select(slabs_t).where(slabs_t.c.uid_full == slab.uid_full)
                )
                .mappings()
                .first()
            )
            if existing_row is not None:
                existing = self._from_row(existing_row)
                if (
                    existing.bulk_uid_full != slab.bulk_uid_full
                    or tuple(existing.miller) != miller
                    or existing.payload != payload
                ):
                    raise ValueError(
                        "Existing slab identity is associated with different scientific state."
                    )
                out.append(existing)
                continue

            id_short = slab.id_short or self._ids.ensure_slab_id(slab.uid_full)
            values: dict[str, Any] = {
                "uid_full": slab.uid_full,
                "id_short": id_short,
                "bulk_pk": bulk_pk,
                "miller_h": miller[0],
                "miller_k": miller[1],
                "miller_l": miller[2],
                "payload_json": self._payload_json(payload),
                "updated_at": func.current_timestamp(),
            }
            values.update(_slab_tilt_columns(payload, slab_uid_full=slab.uid_full))
            self._conn.execute(insert(slabs_t).values(**values))
            stored = self.get_by_uid_full(slab.uid_full)
            assert stored is not None
            out.append(stored)
        return out

    def get_by_uid_full(self, uid_full: str) -> Optional[Slab]:
        row = (
            self._conn.execute(select(slabs_t).where(slabs_t.c.uid_full == uid_full))
            .mappings()
            .first()
        )
        return None if row is None else self._from_row(row)

    def get_many_by_uid_full(self, uid_fulls: Sequence[str]) -> list[Slab]:
        if not uid_fulls:
            return []
        rows = (
            self._conn.execute(
                select(slabs_t).where(slabs_t.c.uid_full.in_(list(uid_fulls)))
            )
            .mappings()
            .all()
        )
        by_uid = {str(row["uid_full"]): self._from_row(row) for row in rows}
        return [by_uid[uid] for uid in uid_fulls if uid in by_uid]

    def list(
        self,
        *,
        bulk_uid_full: str | None = None,
        limit: int | None = None,
    ) -> list[SlabSummary]:
        q = select(slabs_t).order_by(slabs_t.c.slab_pk.asc())
        if bulk_uid_full is not None:
            bulk_pk = self._conn.execute(
                select(bulks_t.c.bulk_pk).where(bulks_t.c.uid_full == bulk_uid_full)
            ).scalar_one_or_none()
            if bulk_pk is None:
                return []
            q = q.where(slabs_t.c.bulk_pk == bulk_pk)
        if limit is not None:
            q = q.limit(limit)
        slabs = [self._from_row(row) for row in self._conn.execute(q).mappings().all()]
        return [
            SlabSummary(
                uid_full=slab.uid_full,
                id_short=slab.id_short,
                bulk_uid_full=slab.bulk_uid_full,
                bulk_id_short=slab.bulk_id_short,
                miller=slab.miller,
                created_at=slab.created_at,
            )
            for slab in slabs
        ]

    def list_reference_records(
        self,
        *,
        limit: int | None = None,
    ) -> list[SlabReferenceRecord]:
        """Return raw slab-parent references without hydrating slab payloads.

        This bounded diagnostic projection allows workspace validation to report
        a missing parent bulk or malformed slab row. Ordinary runtime readers
        continue to use the strict current-schema hydration path.
        """

        stmt = (
            select(
                slabs_t.c.uid_full,
                slabs_t.c.id_short,
                slabs_t.c.bulk_pk,
                bulks_t.c.uid_full.label("bulk_uid_full"),
                bulks_t.c.id_short.label("bulk_id_short"),
            )
            .select_from(
                slabs_t.outerjoin(
                    bulks_t,
                    slabs_t.c.bulk_pk == bulks_t.c.bulk_pk,
                )
            )
            .order_by(slabs_t.c.slab_pk.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return [
            SlabReferenceRecord(
                uid_full=str(row["uid_full"]),
                id_short=str(row["id_short"]),
                bulk_pk=int(row["bulk_pk"]),
                bulk_uid_full=(
                    None
                    if row.get("bulk_uid_full") is None
                    else str(row["bulk_uid_full"])
                ),
                bulk_id_short=(
                    None
                    if row.get("bulk_id_short") is None
                    else str(row["bulk_id_short"])
                ),
            )
            for row in self._conn.execute(stmt).mappings().all()
        ]
