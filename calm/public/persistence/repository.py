"""Authoritative public repository for project-backed entities.

The project database is the sole source of entity existence and durable state.
Searches, candidates, materials, interfaces, datasets, and energy results are
projected entirely from authoritative database records and persisted payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from calm.public.projections.strain import project_candidate_strain_metrics
from calm.public.projections.interface import normalize_interface_row
from calm.public.persistence.adapter import WorkspaceAdapter


def _as_row(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    if hasattr(item, "to_dict"):
        return dict(item.to_dict())
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


def _identity_keys(row: Mapping[str, Any], fields: tuple[str, ...]) -> set[str]:
    return {str(row[field]) for field in fields if row.get(field) not in (None, "")}


def _prototype_row(item: Any) -> dict[str, Any]:
    row = _as_row(item)
    payload = row.get("payload")
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            row.setdefault(key, value)
        metrics = payload.get("metrics")
        if isinstance(metrics, Mapping):
            for key, value in metrics.items():
                row.setdefault(key, value)

    uid_full = row.get("uid_full") or row.get("prototype_uid_full")
    id_short = row.get("id_short") or row.get("prototype_id_short")
    run_uid = row.get("run_uid_full") or row.get("run_uid")
    run_id = row.get("run_id_short") or row.get("run_id")
    if uid_full is not None:
        row.setdefault("uid", uid_full)
        row.setdefault("prototype_uid", uid_full)
        row.setdefault("prototype_uid_full", uid_full)
        row.setdefault("candidate_uid", uid_full)
        row.setdefault("project_prototype_uid", uid_full)
    if id_short is not None:
        row.setdefault("prototype_id_short", id_short)
        row.setdefault("project_prototype_id", id_short)
    if run_uid is not None:
        row.setdefault("run_uid", run_uid)
    if run_id is not None:
        row.setdefault("run_id", run_id)
    row.setdefault("score", row.get("match_score"))
    row.setdefault(
        "n_atoms_estimate",
        row.get("n_atoms_interface") or row.get("natoms"),
    )
    row.setdefault(
        "area_A2",
        row.get("interface_area_A2") or row.get("interface_area"),
    )
    row.setdefault("surface_a_uid_full", row.get("slab_a_uid_full"))
    row.setdefault("surface_b_uid_full", row.get("slab_b_uid_full"))
    row.setdefault("surface_a_id_short", row.get("slab_a_id_short"))
    row.setdefault("surface_b_id_short", row.get("slab_b_id_short"))
    row.setdefault("slab_a_project_uid", row.get("slab_a_uid_full"))
    row.setdefault("slab_b_project_uid", row.get("slab_b_uid_full"))
    row.setdefault("slab_a_project_id", row.get("slab_a_id_short"))
    row.setdefault("slab_b_project_id", row.get("slab_b_id_short"))
    row = project_candidate_strain_metrics(row)
    row["_object"] = item
    row["_authority"] = "authoritative"
    row["authority"] = "authoritative"
    return row


def _search_surface_context(search: Any, side: str) -> dict[str, Any]:
    spec = getattr(search, "spec", None)
    if not isinstance(spec, Mapping):
        return {}
    surface = spec.get(f"surface_{side}")
    return dict(surface) if isinstance(surface, Mapping) else {}


def _apply_search_context(row: dict[str, Any], search: Any) -> None:
    """Decorate one candidate from its authoritative search descriptor."""

    row["search_name"] = str(search.name)
    row["search_id"] = str(search.name)
    row["search_identity"] = str(search.search_identity)
    for side in ("a", "b"):
        surface = _search_surface_context(search, side)
        if not surface:
            continue
        material = surface.get("material")
        uid_full = surface.get("uid_full")
        id_short = surface.get("id_short")
        row.setdefault(f"material_{side}", material)
        row.setdefault(f"surface_{side}", material or id_short or uid_full)
        row.setdefault(f"surface_{side}_uid_full", uid_full)
        row.setdefault(f"surface_{side}_id_short", id_short)
        row.setdefault(f"miller_{side}", surface.get("miller"))
        row.setdefault(f"termination_{side}", surface.get("termination"))
        row.setdefault(
            f"termination_shift_{side}",
            surface.get("termination_shift"),
        )


def _candidate_rows_by_prototype(
    adapter: WorkspaceAdapter,
    searches: list[Any],
    *,
    run: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return authoritative candidate context keyed by prototype UID."""

    searches_by_run = {str(search.run_uid_full): search for search in searches}
    rank_by_run: dict[str, int] = {}
    rows: dict[str, dict[str, Any]] = {}
    for prototype in adapter.list_prototypes(run=run, limit=None):
        row = _prototype_row(prototype)
        prototype_uid = row.get("uid_full") or row.get("prototype_uid_full")
        if prototype_uid in (None, ""):
            raise RuntimeError(
                "Authoritative prototype summaries must expose durable identity."
            )
        run_uid = str(row.get("run_uid_full") or "")
        rank = rank_by_run.get(run_uid, 0)
        rank_by_run[run_uid] = rank + 1
        row["rank"] = rank
        row["candidate_id"] = f"C{rank:04d}"
        owner = searches_by_run.get(run_uid)
        if owner is not None:
            _apply_search_context(row, owner)
        rows[str(prototype_uid)] = row
    return rows


def _authoritative_interface_row(
    item: Any,
    *,
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project one persisted derived interface without a reporting overlay."""

    row = dict(normalize_interface_row(item))
    row.pop("build_uid", None)
    uid_full = getattr(item, "uid_full", None) or row.get("uid_full")
    id_short = getattr(item, "id_short", None) or row.get("id_short")
    prototype_uid = (
        getattr(item, "prototype_uid_full", None)
        or row.get("prototype_uid_full")
        or row.get("prototype_uid")
    )
    if uid_full in (None, "") or id_short in (None, "") or prototype_uid in (None, ""):
        raise RuntimeError(
            "Authoritative derived interfaces must expose uid_full, id_short, "
            "and prototype_uid_full."
        )

    row.update(
        {
            "uid_full": str(uid_full),
            "id_short": str(id_short),
            "interface_id": str(id_short),
            "id": str(id_short),
            "structure_id": str(id_short),
            "interface_uid": str(uid_full),
            "project_interface_uid": str(uid_full),
            "project_interface_id": str(id_short),
            "prototype_uid": (
                str(prototype_uid) if prototype_uid not in (None, "") else None
            ),
            "prototype_uid_full": (
                str(prototype_uid) if prototype_uid not in (None, "") else None
            ),
            "candidate_uid": (
                str(prototype_uid) if prototype_uid not in (None, "") else None
            ),
            "has_atoms": bool(getattr(item, "atoms_artifact_uid", None)),
            "artifact_refs": list(getattr(item, "artifact_refs", []) or []),
        }
    )

    row["stage"] = str(item.stage)
    shift = item.registry_shift_frac_a
    row["translation_x"] = float(shift[0])
    row["translation_y"] = float(shift[1])
    row["gap"] = float(item.z_padding)

    if candidate is not None:
        for key, value in candidate.items():
            if key in {"_object", "_authority", "authority"}:
                continue
            if value is not None and row.get(key) in (None, ""):
                row[key] = value
        row["candidate_uid"] = str(prototype_uid)
        row["candidate_id"] = candidate.get("candidate_id")

    row["_object"] = item
    row["_authority"] = "authoritative"
    row["authority"] = "authoritative"
    return row


_CANDIDATE_ID_FIELDS = (
    "candidate_id",
    "candidate_uid",
    "prototype_uid",
    "prototype_uid_full",
    "project_prototype_uid",
    "project_prototype_id",
    "uid_full",
    "id_short",
)
_INTERFACE_ID_FIELDS = (
    "uid_full",
    "id_short",
    "interface_id",
    "interface_uid",
    "project_interface_uid",
    "project_interface_id",
    "structure_id",
    "name",
    "label",
)


class PublicRepository:
    """Project authoritative workspace entities into the public query model."""

    def __init__(
        self,
        workspace_adapter: WorkspaceAdapter,
    ) -> None:
        if not isinstance(workspace_adapter, WorkspaceAdapter):
            raise TypeError(
                "PublicRepository requires a WorkspaceAdapter; normalize the "
                "workspace at the Project composition root"
            )
        self._adapter = workspace_adapter

    # ---------- Materials and slabs ----------
    def list_bulks(self, *, limit: int | None = None) -> list[Any]:
        summaries = self._adapter.list_bulks(limit=limit)
        bulks: list[Any] = []
        for summary in summaries:
            row = _as_row(summary)
            identifier = row.get("uid_full") or row.get("id_short")
            if identifier is None:
                raise RuntimeError(
                    "Authoritative bulk summaries must expose durable identity."
                )
            bulks.append(self._adapter.get_bulk(str(identifier)))
        return bulks

    def get_bulk(self, identifier: str) -> Any:
        return self._adapter.get_bulk(identifier)

    def list_slabs(self, *, limit: int | None = None) -> list[Any]:
        summaries = self._adapter.list_slabs(limit=limit)
        slabs: list[Any] = []
        for summary in summaries:
            row = _as_row(summary)
            identifier = row.get("uid_full") or row.get("id_short")
            if identifier is None:
                raise RuntimeError(
                    "Authoritative slab summaries must expose durable identity."
                )
            slabs.append(self._adapter.get_slab(str(identifier)))
        return slabs

    def get_slab(self, identifier: str) -> Any:
        return self._adapter.get_slab(identifier)

    # ---------- Prototypes and candidates ----------
    def list_prototypes(
        self,
        *,
        run: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return self._adapter.list_prototypes(run=run, limit=limit)

    def get_prototype(self, identifier: str) -> Any:
        return self._adapter.get_prototype(identifier)

    # ---------- Named interface searches ----------
    def list_searches(self, *, limit: int | None = None) -> list[Any]:
        return self._adapter.list_interface_searches(limit=limit)

    def get_search(self, identifier: str) -> Any:
        return self._adapter.get_interface_search(identifier)

    def _search_descriptor(self, identifier: str) -> Any | None:
        try:
            return self.get_search(identifier)
        except KeyError:
            return None

    def list_candidates(
        self, *, search_name: str | None = None
    ) -> list[dict[str, Any]]:
        search = (
            self._search_descriptor(search_name) if search_name is not None else None
        )
        if search_name is not None and search is None:
            return []
        run_identifier = (
            getattr(search, "run_uid_full", None) if search is not None else None
        )
        prototypes = self._adapter.list_prototypes(
            run=run_identifier,
            limit=None,
        )
        searches_by_run = (
            {str(search.run_uid_full): search}
            if search is not None
            else {
                str(item.run_uid_full): item for item in self.list_searches(limit=None)
            }
        )

        rows: list[dict[str, Any]] = []
        for prototype in prototypes:
            row = _prototype_row(prototype)
            owner = searches_by_run.get(str(row.get("run_uid_full") or ""))
            if owner is not None:
                _apply_search_context(row, owner)
            rows.append(row)
        return rows

    def get_candidate(self, identifier: str) -> dict[str, Any]:
        matches = [
            row
            for row in self.list_candidates()
            if str(identifier) in _identity_keys(row, _CANDIDATE_ID_FIELDS)
        ]
        if not matches:
            raise KeyError(f"Candidate not found: {identifier}")
        if len(matches) > 1:
            raise RuntimeError(f"Candidate identifier is ambiguous: {identifier}")
        return matches[0]

    # ---------- Derived interfaces ----------
    def list_interfaces(
        self,
        *,
        search_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        search = (
            self._search_descriptor(search_name) if search_name is not None else None
        )
        if search_name is not None and search is None:
            return []

        searches = [search] if search is not None else self.list_searches(limit=None)
        candidate_by_prototype = _candidate_rows_by_prototype(
            self._adapter,
            [item for item in searches if item is not None],
            run=(str(search.run_uid_full) if search is not None else None),
        )
        selected_prototypes = (
            set(candidate_by_prototype) if search is not None else None
        )

        authoritative = self._adapter.list_derived_interfaces(
            limit=None if search is not None else limit
        )
        rows: list[dict[str, Any]] = []
        for item in authoritative:
            prototype_uid = getattr(item, "prototype_uid_full", None)
            if (
                selected_prototypes is not None
                and str(prototype_uid or "") not in selected_prototypes
            ):
                continue
            row = _authoritative_interface_row(
                item,
                candidate=candidate_by_prototype.get(str(prototype_uid or "")),
            )
            rows.append(row)
        return rows if limit is None else rows[:limit]

    def get_interface(self, identifier: str) -> dict[str, Any]:
        matches = [
            row
            for row in self.list_interfaces()
            if str(identifier) in _identity_keys(row, _INTERFACE_ID_FIELDS)
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(f"Interface identifier is ambiguous: {identifier}")

        item = self._adapter.get_derived_interface(identifier)
        prototype_uid = getattr(item, "prototype_uid_full", None)
        candidate_by_prototype = _candidate_rows_by_prototype(
            self._adapter,
            self.list_searches(limit=None),
        )
        return _authoritative_interface_row(
            item,
            candidate=candidate_by_prototype.get(str(prototype_uid or "")),
        )

    def save_interface(
        self,
        interface: Any,
        *,
        name: str | None = None,
    ) -> Any:
        """Persist one interface through the authoritative database owner."""
        persisted = self._adapter.persist_derived_interface(
            interface,
            name=name,
        )
        uid_full = getattr(persisted, "uid_full", None)
        id_short = getattr(persisted, "id_short", None)
        if not uid_full or not id_short:
            from calm.public.errors import ProjectPersistenceError

            raise ProjectPersistenceError(
                "Authoritative interface persistence must return uid_full and id_short."
            )
        return persisted

    # ---------- Runs, follow-ups, artifacts, edges ----------
    def list_runs(
        self,
        *,
        run_type: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return self._adapter.list_runs(
            run_type=run_type,
            status=status,
            limit=limit,
        )

    def get_run(self, run: str) -> Any:
        return self._adapter.get_run(run)

    def list_followup_results(
        self,
        *,
        run: str | None = None,
        prototype: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return self._adapter.list_followup_results(
            run=run,
            prototype=prototype,
            kind=kind,
            status=status,
            limit=limit,
        )

    def get_followup_result(self, identifier: str) -> Any:
        return self._adapter.get_followup_result(identifier)

    def list_artifacts(self, run: str) -> list[Any]:
        return self._adapter.list_artifacts(run)

    def list_edges(
        self,
        *,
        src: str | None = None,
        dst: str | None = None,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return self._adapter.list_edges(
            src=src,
            dst=dst,
            kind=kind,
            limit=limit,
        )

    def resolve_identifier(self, identifier: str) -> str:
        return self._adapter.resolve_identifier(identifier)

    # ---------- Datasets and campaigns ----------
    def list_datasets(self, *, limit: int | None = None) -> list[Any]:
        return self._adapter.list_datasets(limit=limit)

    def get_dataset(self, identifier: str) -> Any:
        return self._adapter.get_dataset(identifier)

    def list_dataset_items(self, dataset: str) -> list[Any]:
        return self._adapter.list_dataset_items(dataset)

    def list_campaigns(self, *, limit: int | None = None) -> list[Any]:
        return self._adapter.list_campaigns(limit=limit)

    def get_campaign(self, identifier: str) -> Any:
        return self._adapter.get_campaign(identifier)

    def get_campaign_run(self, identifier: str) -> Any:
        return self._adapter.get_campaign_run(identifier)

    def list_campaign_runs(
        self,
        *,
        campaign: str | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        return self._adapter.list_campaign_runs(campaign=campaign, limit=limit)

    def get_campaign_run_for_dataset(self, dataset: str) -> Any:
        return self._adapter.get_campaign_run_for_dataset(dataset)

    def get_campaign_for_dataset(self, dataset: str) -> Any:
        return self._adapter.get_campaign_for_dataset(dataset)
