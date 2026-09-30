"""Application service for deterministic authoritative dataset persistence."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from calm.project.domain.contracts.dataset import (
    DatasetIdentityConflictError,
    canonical_dataset_schema,
    validate_dataset_item_values,
    validate_learning_dataset_collection,
)
from calm.project.domain.identity_v2 import (
    dataset_identity_payload,
    dataset_item_identity_payload,
    persisted_entity_uid_v2,
)
from calm.project.domain.models import Dataset, DatasetItem


_DUPLICATE_POLICIES = {"error", "skip"}


class DatasetService:
    """Own deterministic dataset identity, membership, and lineage writes."""

    def __init__(self, *, uow_factory: Callable[[], Any]) -> None:
        if not callable(uow_factory):
            raise TypeError("DatasetService requires a UnitOfWork factory.")
        self._uow_factory = uow_factory

    def create_or_get(
        self,
        *,
        name: str,
        settings: Mapping[str, Any],
        description: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> Dataset:
        normalized_name = str(name).strip()
        if not normalized_name:
            raise ValueError("Dataset name must be non-empty.")
        canonical_settings = dict(settings)
        identity = persisted_entity_uid_v2(
            "dataset",
            dataset_identity_payload(
                name=normalized_name,
                settings=canonical_settings,
            ),
        )
        metadata = {
            "dataset_identity_version": 2,
            "dataset_identity": identity,
            "schema_version": canonical_settings.get("schema_version"),
            "settings": canonical_settings,
            "stage": "validated_dataset",
            "tags": sorted({str(tag) for tag in (tags or [])}),
        }

        with self._fresh_uow() as uow:
            repo = self._require_repo(uow)
            named = [
                row
                for row in repo.list_datasets(limit=None)
                if row.name == normalized_name
            ]
            if len(named) > 1:
                raise DatasetIdentityConflictError(
                    "Multiple authoritative datasets already use name "
                    f"{normalized_name!r}."
                )
            if named:
                existing = named[0]
                self._validate_existing(
                    existing,
                    identity=identity,
                    name=normalized_name,
                    settings=canonical_settings,
                )
                return existing

            existing = repo.get_dataset(identity)
            if existing is not None:
                self._validate_existing(
                    existing,
                    identity=identity,
                    name=normalized_name,
                    settings=canonical_settings,
                )
                return existing

            created = repo.create_dataset(
                uid_full=identity,
                name=normalized_name,
                project_id=None,
                description=description,
                metadata=metadata,
            )
            if created is None:
                raise RuntimeError(
                    "Dataset repository did not return the authoritative row."
                )
            self._validate_existing(
                created,
                identity=identity,
                name=normalized_name,
                settings=canonical_settings,
            )
            return created

    def list_datasets(self, *, limit: int | None = None) -> list[Dataset]:
        """List authoritative datasets through one fresh read transaction."""
        with self._fresh_uow() as uow:
            return list(self._require_repo(uow).list_datasets(limit=limit))

    def get_dataset(self, identifier: str) -> Dataset:
        """Resolve one authoritative dataset by full ID, short ID, or name."""
        with self._fresh_uow() as uow:
            return self._resolve_dataset(self._require_repo(uow), identifier)

    def list_items(self, dataset: str) -> list[DatasetItem]:
        """List authoritative items for one resolved dataset."""
        with self._fresh_uow() as uow:
            repo = self._require_repo(uow)
            resolved = self._resolve_dataset(repo, dataset)
            return list(repo.list_dataset_items(resolved.uid_full))

    def add_items(
        self,
        dataset_identifier: str,
        items: Iterable[Mapping[str, Any]],
        *,
        duplicate_policy: str,
    ) -> list[DatasetItem]:
        policy = str(duplicate_policy).strip().lower()
        if policy not in _DUPLICATE_POLICIES:
            raise ValueError(
                "Unsupported dataset duplicate policy; expected one of: "
                + ", ".join(sorted(_DUPLICATE_POLICIES))
            )
        incoming = [dict(item) for item in items]

        with self._fresh_uow() as uow:
            repo = self._require_repo(uow)
            dataset = self._resolve_dataset(repo, dataset_identifier)
            existing = list(repo.list_dataset_items(dataset.uid_full))
            existing_by_source = {
                str((item.metadata or {}).get("source_uid_full")): item
                for item in existing
                if (item.metadata or {}).get("source_uid_full")
            }
            settings = dict((dataset.metadata or {}).get("settings") or {})
            schema = canonical_dataset_schema(
                str(
                    settings.get("schema_version")
                    or (dataset.metadata or {}).get("schema_version")
                    or ""
                )
            )

            existing_rows = [dict(item.metadata or {}) for item in existing]
            combined = existing_rows + incoming
            rows_to_validate = (
                combined if schema == "calm.interface_learning.v1" else incoming
            )
            validation_messages: list[str] = []
            for item in rows_to_validate:
                validation_messages.extend(
                    validate_dataset_item_values(
                        item,
                        schema=schema,
                        allow_failed=settings.get("failure_policy") == "include",
                        settings=settings,
                    )
                )
            if schema == "calm.interface_learning.v1":
                validation_messages.extend(
                    validate_learning_dataset_collection(combined)
                )
            if validation_messages:
                raise ValueError(
                    "Dataset items violate the persisted dataset contract: "
                    + "; ".join(validation_messages)
                )

            seen: set[str] = set()
            duplicates: list[str] = []
            for item in incoming:
                source_uid = str(item.get("source_uid_full") or "")
                if source_uid in seen or source_uid in existing_by_source:
                    duplicates.append(source_uid)
                seen.add(source_uid)
            if duplicates and policy == "error":
                raise ValueError(
                    "Dataset contains duplicate authoritative sources: "
                    + ", ".join(sorted(set(duplicates)))
                )

            next_index = (
                max(
                    [int(item.index) for item in existing if item.index is not None]
                    or [-1]
                )
                + 1
            )
            created: list[DatasetItem] = []
            created_sources: set[str] = set()
            for item in incoming:
                source_uid = str(item["source_uid_full"])
                if source_uid in existing_by_source or source_uid in created_sources:
                    continue
                uid = persisted_entity_uid_v2(
                    "dataset_item",
                    dataset_item_identity_payload(
                        dataset_uid_full=dataset.uid_full,
                        source_uid_full=source_uid,
                    ),
                )
                artifact_refs = list(item.get("artifact_refs") or [])
                row = repo.add_dataset_item(
                    uid_full=uid,
                    dataset_uid_full=dataset.uid_full,
                    index=next_index,
                    metadata=item,
                    artifact_refs=artifact_refs,
                )
                if row is None:
                    raise RuntimeError(
                        "Dataset repository did not return the authoritative item."
                    )
                if row.uid_full != uid or row.dataset_uid_full != dataset.uid_full:
                    raise RuntimeError(
                        "Dataset repository returned an inconsistent item record."
                    )
                uow.edges.add(
                    src_uid_full=uid,
                    dst_uid_full=dataset.uid_full,
                    kind="included_in_dataset",
                    payload={"dataset_index": next_index},
                )
                uow.edges.add(
                    src_uid_full=uid,
                    dst_uid_full=source_uid,
                    kind="dataset_item_from_source",
                    payload={"source_kind": item.get("source_kind")},
                )
                provenance = item.get("provenance")
                if isinstance(provenance, Mapping):
                    component_fields = (
                        "prototype_uid_full",
                        "relaxed_interface_uid_full",
                        "relaxation_run_uid_full",
                        "relaxation_followup_uid",
                        "raw_energy_run_uid_full",
                        "raw_energy_followup_uid",
                        "thermodynamic_run_uid_full",
                        "thermodynamic_followup_uid",
                    )
                    seen_components = {source_uid}
                    for role in component_fields:
                        component_uid = provenance.get(role)
                        if not component_uid:
                            continue
                        component_uid = str(component_uid)
                        if component_uid in seen_components:
                            continue
                        seen_components.add(component_uid)
                        uow.edges.add(
                            src_uid_full=uid,
                            dst_uid_full=component_uid,
                            kind="dataset_item_from_component",
                            payload={"role": role},
                        )
                for ref in artifact_refs:
                    artifact_uid = self._artifact_uid(ref)
                    if artifact_uid:
                        uow.edges.add(
                            src_uid_full=uid,
                            dst_uid_full=artifact_uid,
                            kind="dataset_item_uses_artifact",
                            payload={"artifact_uid_full": artifact_uid},
                        )
                created.append(row)
                created_sources.add(source_uid)
                next_index += 1
            return created

    def _fresh_uow(self) -> Any:
        uow = self._uow_factory()
        if uow is None:
            raise RuntimeError("Dataset UnitOfWork factory returned None.")
        if int(getattr(uow, "_depth", 0) or 0) != 0:
            raise ValueError("DatasetService requires a fresh non-entered UnitOfWork.")
        return uow

    @staticmethod
    def _require_repo(uow: Any) -> Any:
        repo = getattr(uow, "datasets", None)
        if repo is None:
            raise RuntimeError("Dataset repository is unavailable in this workspace.")
        return repo

    @staticmethod
    def _resolve_dataset(repo: Any, identifier: str) -> Dataset:
        text = str(identifier)
        matches = [
            row
            for row in repo.list_datasets(limit=None)
            if text in {row.uid_full, row.id_short, row.name}
        ]
        if not matches:
            raise KeyError(f"Dataset not found: {identifier}")
        if len(matches) > 1:
            raise DatasetIdentityConflictError(
                f"Dataset identifier {identifier!r} is ambiguous."
            )
        return matches[0]

    @staticmethod
    def _validate_existing(
        row: Dataset,
        *,
        identity: str,
        name: str,
        settings: Mapping[str, Any],
    ) -> None:
        if row.uid_full != identity:
            raise DatasetIdentityConflictError(
                f"Dataset name {name!r} is already bound to different settings."
            )
        if row.name != name:
            raise DatasetIdentityConflictError(
                "Deterministic dataset identity already exists under a different name."
            )
        existing_settings = dict((row.metadata or {}).get("settings") or {})
        if existing_settings and existing_settings != dict(settings):
            raise DatasetIdentityConflictError(
                f"Dataset name {name!r} is already bound to different settings."
            )

    @staticmethod
    def _artifact_uid(ref: Any) -> str | None:
        if isinstance(ref, str):
            return ref
        if isinstance(ref, Mapping):
            value = (
                ref.get("artifact_uid")
                or ref.get("artifact_uid_full")
                or ref.get("uid_full")
                or ref.get("uid")
                or ref.get("id")
            )
            return str(value) if value else None
        return None
