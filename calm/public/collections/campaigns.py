"""Public query collection for persisted campaigns."""

from __future__ import annotations

from typing import Any, Iterable

from calm.public.collections.base import _BaseCollection
from calm.public.records.campaign_views import (
    CAMPAIGN_VIEW_SPECS,
    normalize_campaign_row,
)
from calm.public.records.persistence import ProjectCampaign


class CampaignCollection(_BaseCollection):
    """Provide typed, chainable access to authoritative campaigns.

    Campaigns are loaded lazily from the project repository when available.
    Records retrieved from a project remain project-bound, allowing callers to
    list deterministic campaign runs or invoke the campaign through the record.
    """

    _view_specs = CAMPAIGN_VIEW_SPECS

    _items_attr = "_campaigns"

    def __init__(
        self,
        campaigns: Iterable[Any] | None = None,
        repo: Any | None = None,
        project: Any | None = None,
    ):
        self._campaigns = list(campaigns) if campaigns is not None else []
        self._loaded = campaigns is not None
        self._repo = repo
        self._project = project

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError("Repository is required to list campaigns.")
        self._campaigns = list(self._repo.list_campaigns(limit=500))
        self._loaded = True

    def _clone(self, items):
        return CampaignCollection(
            campaigns=items,
            repo=self._repo,
            project=self._project,
        )

    def _public_item(self, item: Any) -> ProjectCampaign:
        return (
            item
            if isinstance(item, ProjectCampaign)
            else ProjectCampaign.from_item(item, project=self._project)
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        return normalize_campaign_row(self._public_item(item))

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        self._ensure_loaded()
        return [self._normalize_item(item) for item in self._campaigns]

    def runs(self, campaign: str | None = None):
        """Return typed persisted campaign-run records for one campaign."""
        from calm.public.collections.persistence import CampaignRunCollection

        if self._repo is None:
            raise RuntimeError("Repository is required to list campaign runs.")

        if campaign is None:
            records = self.records()
            if len(records) != 1:
                raise KeyError(
                    "Campaign identifier is required unless the collection "
                    "contains exactly one campaign."
                )
            selected = records[0]
        else:
            selected = self.get(campaign)

        identifier = selected.uid_full or selected.id_short
        if identifier is None:
            raise KeyError("Selected campaign has no persisted identifier.")
        return CampaignRunCollection(
            self._repo.list_campaign_runs(campaign=identifier, limit=500)
        )
