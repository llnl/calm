"""Project-backed public collection factories.

The database is authoritative. All public collections are projected only from
authoritative database records and their persisted payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.public.collections.campaigns import CampaignCollection
from calm.public.collections.candidates import CandidateCollection
from calm.public.collections.datasets import DatasetCollection
from calm.public.collections.interfaces import InterfaceCollection
from calm.public.collections.persistence import SearchCollection
from calm.public.collections.structures import (
    MaterialCollection,
    SurfaceCollection,
)


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _object_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "to_dict"):
        return dict(item.to_dict())
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


def _authoritative_row(authoritative: Any) -> dict[str, Any]:
    row = _object_row(authoritative)
    row["_object"] = authoritative
    row["_authority"] = "authoritative"
    row["authority"] = "authoritative"
    return row


class PublicProjectQueries:
    """Create typed public views over authoritative project records."""

    def __init__(
        self,
        workspace_adapter: Any,
        *,
        repo: Any,
        project: Any,
    ) -> None:
        self._workspace = workspace_adapter
        self._repo = repo
        self._project = project

    def materials(self) -> MaterialCollection:
        return MaterialCollection(
            self._workspace,
            items=self._repo.list_bulks(),
            repo=self._repo,
        )

    def surfaces(self) -> SurfaceCollection:
        return SurfaceCollection(
            workspace=self._workspace,
            repo=self._repo,
        )

    def searches(self) -> SearchCollection:
        rows: list[dict[str, Any]] = []
        for search in self._repo.list_searches(limit=5000):
            row = _authoritative_row(search)
            row.update(
                {
                    "name": str(_value(search, "name")),
                    "search_name": str(_value(search, "name")),
                    "search_id": str(_value(search, "name")),
                    "search_identity": _value(search, "search_identity"),
                    "run_uid_full": _value(search, "run_uid_full"),
                    "run_id_short": _value(search, "run_id_short"),
                    "n_candidates": len(
                        self._repo.list_prototypes(
                            run=str(_value(search, "run_uid_full")),
                            limit=None,
                        )
                    ),
                }
            )
            rows.append(row)
        return SearchCollection(rows)

    def candidates(self) -> CandidateCollection:
        return CandidateCollection(workspace=self._workspace, repo=self._repo)

    def interfaces(self) -> InterfaceCollection:
        return InterfaceCollection(self._workspace, repo=self._repo)

    def datasets(self) -> DatasetCollection:
        return DatasetCollection(
            workspace=self._workspace,
            datasets=self._repo.list_datasets(limit=500),
            repo=self._repo,
            project=self._project,
        )

    def campaigns(self) -> CampaignCollection:
        return CampaignCollection(repo=self._repo, project=self._project)
