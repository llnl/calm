"""Application service for authoritative campaign persistence."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from calm.project.domain.contracts.campaign import (
    CampaignIdentityConflictError,
    campaign_spec_equal,
)
from calm.project.domain.identity_v2 import (
    campaign_identity_payload,
    persisted_entity_uid_v2,
)


_CAMPAIGN_RUN_STATUSES = {
    "pending",
    "running",
    "completed",
    "partial",
    "failed",
    "skipped",
}


class CampaignService:
    """Own campaign identity, run creation, status, and lineage writes."""

    def __init__(
        self,
        uow: Any | None = None,
        *,
        uow_factory: Callable[[], Any] | None = None,
    ) -> None:
        if uow_factory is None:
            if uow is None:
                raise TypeError("CampaignService requires a UnitOfWork factory.")

            def provided_uow_factory() -> Any:
                return uow

            uow_factory = provided_uow_factory
        self._uow_factory = uow_factory

    def create_or_get(
        self,
        *,
        name: str | None,
        spec: Mapping[str, Any] | None = None,
        uid_full: str | None = None,
    ) -> Any:
        canonical_spec = dict(spec or {})
        identity = persisted_entity_uid_v2(
            "campaign",
            campaign_identity_payload(name=name, spec=canonical_spec),
        )
        if uid_full not in {None, identity}:
            raise ValueError(
                "Explicit campaign uid_full does not match the canonical "
                "persisted campaign identity."
            )

        with self._uow_factory() as uow:
            repo = self._require_repo(uow)
            named = [
                row
                for row in repo.list_campaigns(limit=None)
                if name is not None and self._field(row, "name") == name
            ]
            if len(named) > 1:
                raise CampaignIdentityConflictError(
                    f"Multiple authoritative campaigns already use name {name!r}."
                )
            if named:
                existing = named[0]
                self._validate_existing(
                    existing,
                    identity=identity,
                    name=name,
                    spec=canonical_spec,
                )
                return existing

            existing = repo.get_campaign(identity)
            if existing is not None:
                self._validate_existing(
                    existing,
                    identity=identity,
                    name=name,
                    spec=canonical_spec,
                )
                return existing

            created = repo.create_campaign(
                uid_full=identity,
                name=name,
                project_id=None,
                spec=canonical_spec,
            )
            if created is None:
                raise RuntimeError(
                    "Campaign repository did not return the authoritative row."
                )
            self._validate_existing(
                created,
                identity=identity,
                name=name,
                spec=canonical_spec,
            )
            return created

    def create_or_get_run(
        self,
        campaign_uid_full: str,
        *,
        run_spec: Mapping[str, Any],
        backend_id: str | None = None,
        status: str | None = None,
    ) -> Any:
        normalized_status = self._normalize_status(status, allow_none=True)
        with self._uow_factory() as uow:
            repo = self._require_repo(uow)
            campaign = repo.get_campaign(str(campaign_uid_full))
            if campaign is None:
                raise KeyError(f"Campaign not found: {campaign_uid_full}")

            run = repo.create_or_get_campaign_run(
                campaign_uid_full=str(campaign_uid_full),
                run_spec=dict(run_spec),
                backend_id=backend_id or "",
                status=normalized_status,
            )
            if run is None:
                raise RuntimeError(
                    "Campaign repository did not return the authoritative run."
                )
            run_uid = self._field(run, "uid_full")
            if not run_uid:
                raise RuntimeError("Authoritative campaign run is missing uid_full.")
            stored_campaign_uid = self._field(run, "campaign_uid_full")
            if stored_campaign_uid != str(campaign_uid_full):
                raise RuntimeError(
                    "Authoritative campaign run references a different campaign."
                )

            uow.edges.add(
                src_uid_full=str(run_uid),
                dst_uid_full=str(campaign_uid_full),
                kind="run_of_campaign",
                payload={"campaign_uid_full": str(campaign_uid_full)},
            )
            return run

    def mark_run(self, campaign_run_uid_full: str, *, status: str) -> Any:
        normalized_status = self._normalize_status(status, allow_none=False)
        with self._uow_factory() as uow:
            repo = self._require_repo(uow)
            existing = repo.get_campaign_run(str(campaign_run_uid_full))
            if existing is None:
                raise KeyError(f"Campaign run not found: {campaign_run_uid_full}")
            updated = repo.mark_campaign_run(
                str(campaign_run_uid_full),
                status=normalized_status,
            )
            if updated is None:
                raise RuntimeError(
                    "Campaign repository did not return the updated run."
                )
            if self._field(updated, "status") != normalized_status:
                raise RuntimeError(
                    "Campaign repository did not persist the requested status."
                )
            return updated

    @staticmethod
    def _require_repo(uow: Any) -> Any:
        repo = getattr(uow, "campaigns", None)
        if repo is None:
            raise RuntimeError("Campaign repository is unavailable in this workspace.")
        return repo

    @staticmethod
    def _field(row: Any, name: str) -> Any:
        if isinstance(row, Mapping):
            return row.get(name)
        return getattr(row, name, None)

    @classmethod
    def _validate_existing(
        cls,
        row: Any,
        *,
        identity: str,
        name: str | None,
        spec: Mapping[str, Any],
    ) -> None:
        if cls._field(row, "uid_full") != identity:
            raise CampaignIdentityConflictError(
                f"Campaign name {name!r} is already bound to a different specification."
            )
        if cls._field(row, "name") != name:
            raise CampaignIdentityConflictError(
                "Deterministic campaign identity already exists under a different name."
            )
        existing_spec = cls._field(row, "spec") or {}
        if not campaign_spec_equal(existing_spec, spec):
            raise CampaignIdentityConflictError(
                f"Campaign name {name!r} is already bound to a different specification."
            )

    @staticmethod
    def _normalize_status(status: str | None, *, allow_none: bool) -> str | None:
        if status is None and allow_none:
            return None
        if not isinstance(status, str):
            raise TypeError("Campaign-run status must be a string.")
        normalized = status.strip().lower()
        if normalized not in _CAMPAIGN_RUN_STATUSES:
            raise ValueError(
                "Unsupported campaign-run status; expected one of: "
                + ", ".join(sorted(_CAMPAIGN_RUN_STATUSES))
            )
        return normalized
