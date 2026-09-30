"""Identifier utilities and resolver interfaces.

Provides helpers for short id formatting/parsing and the IdResolver interface
used by repository implementations to allocate and resolve human-friendly
short identifiers.
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

SHORT_ID_RE = re.compile(r"^(?P<tag>[a-z])_(?P<prefix>[0-9a-f]{4,64})$")


def normalize_identifier(identifier: str) -> str:
    return identifier.strip()


def _stable_hex(uid_full: str) -> str:
    """Return a stable hex digest for arbitrary UID strings."""

    if re.fullmatch(r"[0-9a-f]{8,128}", uid_full):
        return uid_full
    return hashlib.sha256(uid_full.encode("utf-8")).hexdigest()


def format_short_id(*, tag: str, uid_full: str, prefix_len: int = 8) -> str:
    """Format a deterministic short id for uid_full."""

    hex_ = _stable_hex(uid_full)
    return f"{tag}_{hex_[:prefix_len]}"


def parse_short_id(identifier: str) -> tuple[str, str] | None:
    m = SHORT_ID_RE.match(normalize_identifier(identifier))
    if not m:
        return None
    return m.group("tag"), m.group("prefix")


class IdResolver(Protocol):
    """Resolve public identifiers (short IDs / full UIDs) to canonical UIDs."""

    def resolve(self, identifier: str, *, expected_tag: str | None = None) -> str:
        """Resolve identifier to a canonical uid_full."""

    def ensure_short_id(
        self,
        *,
        tag: str,
        uid_full: str,
        min_prefix_len: int = 8,
        max_prefix_len: int = 12,
    ) -> str:
        """Return a unique short id for uid_full within the entity table for *tag*."""

    # Convenience helpers -------------------------------------------------

    def resolve_slab(self, identifier: str) -> str:
        return self.resolve(identifier, expected_tag="s")

    def resolve_run(self, identifier: str) -> str:
        return self.resolve(identifier, expected_tag="r")

    def resolve_prototype(self, identifier: str) -> str:
        return self.resolve(identifier, expected_tag="p")

    def ensure_bulk_id(self, uid_full: str) -> str:
        return self.ensure_short_id(tag="b", uid_full=uid_full)

    def ensure_slab_id(self, uid_full: str) -> str:
        return self.ensure_short_id(tag="s", uid_full=uid_full)

    def ensure_run_id(self, uid_full: str) -> str:
        return self.ensure_short_id(tag="r", uid_full=uid_full)

    def ensure_artifact_id(self, uid_full: str) -> str:
        return self.ensure_short_id(tag="a", uid_full=uid_full)

    def ensure_prototype_id(self, uid_full: str) -> str:
        return self.ensure_short_id(tag="p", uid_full=uid_full)
