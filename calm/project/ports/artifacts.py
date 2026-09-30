"""Current artifact-byte persistence boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ArtifactStore(Protocol):
    """Persist run-scoped bytes and return one canonical storage URI."""

    def ensure_run_layout(self, *, run_id_short: str) -> None: ...

    def put_bytes(
        self,
        *,
        run_id_short: str,
        category: str,
        filename: str,
        data: bytes,
    ) -> Path: ...

    def uri_for(self, path: Path) -> str: ...
