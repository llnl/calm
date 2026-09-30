from __future__ import annotations

from pathlib import Path


class ProjectArtifacts:
    def __init__(self, project_root: str | Path | None):
        self._root = (
            Path(project_root) / "CALM_results" if project_root is not None else None
        )

    def root(self) -> Path | None:
        return self._root

    def list(self, pattern: str | None = None) -> list[Path]:
        if self._root is None or not self._root.exists():
            return []
        if pattern is None:
            return list(self._root.rglob("*"))
        return list(self._root.rglob(pattern))

    def find_by_kind(self, kind: str) -> list[Path]:
        if self._root is None or not self._root.exists():
            return []
        kind_map = {
            "tables": "tables",
            "plots": "plots",
            "reports": "reports",
            "structures": "structures",
            "datasets": "datasets",
        }
        sub = kind_map.get(kind, kind)
        path = self._root / sub
        if not path.exists():
            return []
        return list(path.rglob("*"))
