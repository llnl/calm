from __future__ import annotations

from typing import List

from sqlalchemy import Connection, select

from ...ports.ids import (
    IdResolver,
    format_short_id,
    normalize_identifier,
    parse_short_id,
)
from .tables import (
    artifacts as artifacts_t,
)
from .tables import (
    bulks as bulks_t,
)
from .tables import (
    calculators as calculators_t,
)
from .tables import (
    campaign_runs as campaign_runs_t,
)
from .tables import (
    campaigns as campaigns_t,
)
from .tables import (
    dataset_items as dataset_items_t,
)
from .tables import (
    datasets as datasets_t,
)
from .tables import (
    derived_interfaces as derived_interfaces_t,
)
from .tables import (
    followup_results as followup_results_t,
)
from .tables import (
    prototypes as prototypes_t,
)
from .tables import (
    runs as runs_t,
)
from .tables import (
    slabs as slabs_t,
)


class SqlAlchemyIdResolver(IdResolver):
    """Resolve short IDs against a SQLite DB via SQLAlchemy Core.

    Extracted from repos.py to isolate id-resolution behavior and make it
    independently testable and reusable.
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

        # Tag -> table mapping. Extend as new entities are introduced.
        self._tag_tables = {
            "b": bulks_t,
            "c": calculators_t,
            "s": slabs_t,
            "r": runs_t,
            "a": artifacts_t,
            "p": prototypes_t,
            "f": followup_results_t,
            "i": derived_interfaces_t,
            # campaigns / campaign_runs short-id tags
            "y": campaigns_t,
            "x": campaign_runs_t,
            # datasets / dataset_items short-id tags
            "d": datasets_t,
            "t": dataset_items_t,
        }

    def _table_for_tag(self, tag: str):
        try:
            return self._tag_tables[tag]
        except KeyError as e:
            raise KeyError(f"Unknown id tag: {tag!r}") from e

    def resolve(self, identifier: str, *, expected_tag: str | None = None) -> str:
        ident = normalize_identifier(identifier)

        parsed = parse_short_id(ident)
        if parsed is not None:
            tag, prefix = parsed
            if expected_tag is not None and tag != expected_tag:
                raise ValueError(
                    f"Expected a '{expected_tag}_...' identifier, got {identifier!r}"
                )

            table = self._table_for_tag(tag)
            matches = (
                self._conn.execute(
                    select(table.c.uid_full).where(
                        table.c.id_short.like(f"{tag}_{prefix}%")
                    )
                )
                .scalars()
                .all()
            )

            if not matches:
                raise KeyError(f"No match for identifier {identifier!r}")
            if len(matches) > 1:
                raise ValueError(
                    f"Identifier prefix is ambiguous: {identifier!r}. "
                    f"Matches: {', '.join(matches[:5])}{' ...' if len(matches) > 5 else ''}. "
                    "Use a longer prefix."
                )
            return str(matches[0])

        # Not a short id; treat as uid_full.
        if expected_tag is not None:
            table = self._table_for_tag(expected_tag)
            uid = self._conn.execute(
                select(table.c.uid_full).where(table.c.uid_full == ident)
            ).scalar_one_or_none()
            if uid is not None:
                return str(uid)
            raise KeyError(f"No {expected_tag} entity with uid {identifier!r}")

        found: List[str] = []
        for table in self._tag_tables.values():
            uid = self._conn.execute(
                select(table.c.uid_full).where(table.c.uid_full == ident)
            ).scalar_one_or_none()
            if uid is not None:
                found.append(str(uid))

        if not found:
            raise KeyError(f"No entity found with uid {identifier!r}")
        if len(found) > 1:
            raise ValueError(
                f"UID is ambiguous across entity kinds: {identifier!r}. "
                "Disambiguate by using a short id (e.g., b_..., r_...) or provide expected_tag."
            )
        return found[0]

    def ensure_short_id(
        self,
        *,
        tag: str,
        uid_full: str,
        min_prefix_len: int = 8,
        max_prefix_len: int = 12,
    ) -> str:
        table = self._table_for_tag(tag)

        for pref_len in range(min_prefix_len, max_prefix_len + 1):
            candidate = format_short_id(tag=tag, uid_full=uid_full, prefix_len=pref_len)
            existing = self._conn.execute(
                select(table.c.uid_full).where(table.c.id_short == candidate)
            ).scalar_one_or_none()

            if existing is None:
                return candidate
            if str(existing) == uid_full:
                return candidate

        raise ValueError(
            f"Unable to allocate a unique short id for uid_full={uid_full!r} tag={tag!r}. "
            "Try increasing max_prefix_len."
        )
