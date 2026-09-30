"""Application service for exact run-scoped artifact persistence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from calm.project.domain.identity_v2 import (
    artifact_identity_payload,
    artifact_storage_metadata,
    persisted_entity_uid_v2,
)

from ..domain.models import ArtifactRef
from ..ports.artifacts import ArtifactStore
from ._uow import fresh_uow, require_entered_uow, require_uow_factory


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArtifactsService:
    """Own artifact files, rows, and mandatory run lineage."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        store: ArtifactStore,
    ) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="ArtifactsService",
        )
        if store is None:
            raise TypeError("ArtifactsService requires an artifact store.")
        self._store = store

    def put_log(
        self,
        run: str,
        *,
        text: str,
        filename: str = "log.txt",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        return self.put_text(
            run,
            category="logs",
            kind="log",
            filename=filename,
            text=text,
            metadata=metadata,
        )

    def put_plot(
        self,
        run: str,
        *,
        data: bytes,
        filename: str = "plot.png",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        return self.put_bytes(
            run,
            data=data,
            filename=filename,
            category="plots",
            kind="plot",
            metadata=metadata,
        )

    def put_structure(
        self,
        run: str,
        *,
        text: str,
        filename: str = "structure.xyz",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        return self.put_text(
            run,
            text=text,
            filename=filename,
            category="structures",
            kind="structure",
            metadata=metadata,
        )

    def put_text(
        self,
        run: str,
        *,
        category: str,
        kind: str,
        filename: str,
        text: str,
        metadata: Mapping[str, Any] | None = None,
        encoding: str = "utf-8",
    ) -> ArtifactRef:
        return self.put_bytes(
            run,
            category=category,
            kind=kind,
            filename=filename,
            data=text.encode(encoding),
            metadata=metadata,
        )

    def put_json(
        self,
        run: str,
        *,
        obj: Any,
        filename: str = "data.json",
        category: str = "data",
        kind: str = "json",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        text = json.dumps(obj, indent=2, sort_keys=True)
        return self.put_bytes(
            run,
            category=category,
            kind=kind,
            filename=filename,
            data=(text + "\n").encode("utf-8"),
            metadata=metadata,
        )

    def put_interface_atoms(
        self,
        run: str,
        *,
        interface_uid_full: str,
        obj: Any,
        filename: str = "interface_atoms.json",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        with fresh_uow(self._uow_factory, owner="ArtifactsService") as uow:
            return self.put_interface_atoms_in(
                uow,
                run,
                interface_uid_full=interface_uid_full,
                obj=obj,
                filename=filename,
                metadata=metadata,
            )

    def put_interface_atoms_in(
        self,
        uow: Any,
        run: str,
        *,
        interface_uid_full: str,
        obj: Any,
        filename: str = "interface_atoms.json",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        meta = dict(metadata or {})
        meta.setdefault("role", "derived_interface_atoms")
        meta.setdefault("interface_uid_full", interface_uid_full)
        text = json.dumps(obj, indent=2, sort_keys=True)
        return self.put_bytes_in(
            uow,
            run,
            category="derived_interfaces",
            kind="interface_atoms",
            filename=filename,
            data=(text + "\n").encode("utf-8"),
            metadata=meta,
        )

    def put_bytes(
        self,
        run: str,
        *,
        category: str,
        kind: str,
        filename: str,
        data: bytes,
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        with fresh_uow(self._uow_factory, owner="ArtifactsService") as uow:
            return self.put_bytes_in(
                uow,
                run,
                category=category,
                kind=kind,
                filename=filename,
                data=data,
                metadata=metadata,
            )

    def put_bytes_in(
        self,
        uow: Any,
        run: str,
        *,
        category: str,
        kind: str,
        filename: str,
        data: bytes,
        metadata: Mapping[str, Any] | None = None,
        lineage_payload: Mapping[str, Any] | None = None,
    ) -> ArtifactRef:
        require_entered_uow(uow, owner="ArtifactsService.put_bytes_in")
        run_uid_full = uow.ids.resolve_run(run)
        run_obj = uow.runs.get_by_uid_full(run_uid_full)
        if run_obj is None:
            raise KeyError(f"No run found for identifier {run!r}")

        self._store.ensure_run_layout(run_id_short=run_obj.id_short)
        path = self._store.put_bytes(
            run_id_short=run_obj.id_short,
            category=category,
            filename=filename,
            data=data,
        )
        uri = self._store.uri_for(path)
        content_sha = _sha256_hex(data)
        user_metadata = dict(metadata or {})
        uid_full = persisted_entity_uid_v2(
            "artifact",
            artifact_identity_payload(
                run_uid_full=run_uid_full,
                kind=kind,
                uri=uri,
                content_sha256=content_sha,
                metadata=user_metadata,
            ),
        )
        stored_metadata = artifact_storage_metadata(
            user_metadata,
            content_sha256=content_sha,
        )
        ref = ArtifactRef(
            uid_full=uid_full,
            id_short=uow.ids.ensure_artifact_id(uid_full),
            run_uid_full=run_uid_full,
            run_id_short=run_obj.id_short,
            kind=kind,
            uri=uri,
            metadata=stored_metadata,
        )
        stored = uow.artifacts.add(ref)
        if stored.uid_full != uid_full or stored.run_uid_full != run_uid_full:
            raise RuntimeError(
                "Artifact repository returned an inconsistent authoritative row."
            )
        edge_payload = dict(lineage_payload or {})
        edge_payload.update(
            {
                "kind": kind,
                "category": category,
                "filename": filename,
            }
        )
        uow.edges.add(
            src_uid_full=run_uid_full,
            dst_uid_full=uid_full,
            kind="run_to_artifact",
            payload=edge_payload,
        )
        return stored

    def list_for_run(self, run: str) -> list[ArtifactRef]:
        with fresh_uow(self._uow_factory, owner="ArtifactsService") as uow:
            run_uid_full = uow.ids.resolve_run(run)
            return uow.artifacts.list_for_run(run_uid_full)
