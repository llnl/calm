"""Current filesystem artifact-store implementation.

Artifacts are written under::

    <root>/runs/<run_id_short>/<category>/<filename>

The authoritative database stores canonical absolute ``file://`` URIs.
"""

from __future__ import annotations

from pathlib import Path


class FSArtifactStore:
    """Persist run-scoped artifact bytes beneath one filesystem root."""

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _runs_dir(self) -> Path:
        return self._root / "runs"

    def _run_dir(self, run_id_short: str) -> Path:
        return self._runs_dir() / run_id_short

    def ensure_run_layout(self, *, run_id_short: str) -> None:
        self._runs_dir().mkdir(parents=True, exist_ok=True)
        run_dir = self._run_dir(run_id_short)
        for category in (
            "logs",
            "plots",
            "structures",
            "data",
            "tables",
            "files",
        ):
            (run_dir / category).mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        *,
        run_id_short: str,
        category: str,
        filename: str,
        data: bytes,
    ) -> Path:
        """Write bytes and return their absolute path."""

        self.ensure_run_layout(run_id_short=run_id_short)
        path = self._run_dir(run_id_short) / category / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    @staticmethod
    def uri_for(path: Path) -> str:
        """Return the canonical absolute local-file URI for ``path``."""

        if not isinstance(path, Path):
            raise TypeError("Artifact paths must be pathlib.Path instances.")
        if not path.is_absolute():
            raise ValueError("Artifact paths must be absolute.")
        return path.resolve().as_uri()
