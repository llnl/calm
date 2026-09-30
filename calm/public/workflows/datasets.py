"""Internal composition owner for public dataset workflows.

The :class:`~calm.public.project.Project` facade delegates dataset creation and
membership updates to this service. Deterministic dataset identity, exact
schema validation, duplicate policy, membership ordering, transactions, and
lineage persistence remain owned by the existing application-layer
:class:`calm.project.application.datasets.DatasetService` reached through the
Workspace adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from calm.public.collections.persistence import DatasetItemCollection
from calm.public.records.dataset_views import dataset_learning_columns
from calm.public.records.persistence import ProjectDataset
from calm.public.inputs.settings import DatasetSettings


class _DatasetWorkspace(Protocol):
    def create_or_get_dataset(
        self,
        *,
        name: str,
        settings: dict[str, Any],
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> Any: ...

    def add_dataset_items(
        self,
        dataset: str,
        items: list[dict[str, Any]],
        *,
        duplicate_policy: str,
    ) -> list[Any]: ...


class _DatasetRepository(Protocol):
    def get_dataset(self, identifier: str) -> Any: ...


class ProjectDatasetWorkflowService:
    """Compose public dataset creation and membership updates."""

    def __init__(
        self,
        *,
        project: Any,
        workspace: _DatasetWorkspace,
        repository: _DatasetRepository,
    ) -> None:
        self._project = project
        self._workspace = workspace
        self._repo = repository

    @staticmethod
    def _name(name: Any) -> str:
        normalized = str(name).strip()
        if not normalized:
            raise ValueError("Dataset name must be non-empty.")
        return normalized

    @staticmethod
    def _settings(settings: Any | None) -> DatasetSettings:
        resolved = DatasetSettings() if settings is None else settings
        if not isinstance(resolved, DatasetSettings):
            raise TypeError("settings must be a DatasetSettings instance.")
        resolved.validate()
        return resolved

    @staticmethod
    def _tags(tags: Any | None) -> list[str]:
        if tags is None:
            return []
        if isinstance(tags, str):
            return [tags]
        try:
            return [str(tag) for tag in tags]
        except TypeError as exc:
            raise TypeError("tags must be a string or an iterable of strings.") from exc

    def _normalize_items(
        self,
        items: Any,
        *,
        settings: DatasetSettings,
    ) -> list[dict[str, Any]]:
        from calm.public.records.datasets import normalize_authoritative_dataset_source

        if isinstance(items, (str, bytes, Mapping)) or not hasattr(items, "__iter__"):
            values = [items]
        else:
            values = list(items)

        normalized: list[dict[str, Any]] = []
        for item in values:
            row = normalize_authoritative_dataset_source(
                self._project,
                item,
                settings=settings,
            )
            if row is not None:
                normalized.append(row)
        return normalized

    @staticmethod
    def _preflight_duplicates(
        rows: list[dict[str, Any]],
        *,
        duplicate_policy: str,
    ) -> None:
        if duplicate_policy != "error":
            return
        seen: set[str] = set()
        duplicates: set[str] = set()
        for row in rows:
            source_uid = str(row["source_uid_full"])
            if source_uid in seen:
                duplicates.add(source_uid)
            seen.add(source_uid)
        if duplicates:
            raise ValueError(
                "Dataset contains duplicate authoritative sources: "
                + ", ".join(sorted(duplicates))
            )

    def _dataset(self, item: Any) -> ProjectDataset:
        return ProjectDataset.from_item(item, project=self._project)

    def create_dataset(
        self,
        name: str,
        items: Any | None = None,
        *,
        settings: Any | None = None,
        description: str | None = None,
        tags: Any | None = None,
    ) -> ProjectDataset:
        """Create or reopen one deterministic authoritative dataset."""

        normalized_name = self._name(name)
        resolved_settings = self._settings(settings)
        normalized_items = (
            self._normalize_items(items, settings=resolved_settings)
            if items is not None
            else None
        )
        if normalized_items is not None:
            self._preflight_duplicates(
                normalized_items,
                duplicate_policy=resolved_settings.duplicate_policy,
            )

        record = self._workspace.create_or_get_dataset(
            name=normalized_name,
            settings=resolved_settings.to_dict(),
            description=description,
            tags=self._tags(tags),
        )
        dataset = self._dataset(record)
        if normalized_items is None:
            return dataset

        selector = dataset.uid_full or normalized_name
        self._workspace.add_dataset_items(
            selector,
            normalized_items,
            duplicate_policy=resolved_settings.duplicate_policy,
        )
        return self._dataset(self._repo.get_dataset(selector))

    def add_dataset_items(
        self,
        dataset: str,
        items: Any,
    ) -> DatasetItemCollection:
        """Normalize and append sources under the persisted dataset policy."""

        selector = str(dataset).strip()
        if not selector:
            raise ValueError("Dataset selectors must be non-empty.")
        record = self._dataset(self._repo.get_dataset(selector))
        settings = self._settings(DatasetSettings(**dict(record.settings or {})))
        normalized = self._normalize_items(items, settings=settings)
        created = self._workspace.add_dataset_items(
            record.uid_full or selector,
            normalized,
            duplicate_policy=settings.duplicate_policy,
        )
        return DatasetItemCollection(
            created,
            learning_columns=dataset_learning_columns(settings),
        )
