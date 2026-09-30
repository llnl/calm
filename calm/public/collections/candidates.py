"""Candidate public query collection."""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    strain_size_pareto,
)

from calm.public.collections.base import _BaseCollection, _row
from calm.public.projections.candidate import normalize_candidate_row
from calm.public.records.candidate_views import CANDIDATE_VIEW_SPECS
from calm.public.presentation.plotting import require_current_metric_name
from calm.public.records.interfaces import InterfaceCandidate


def _row_atom_count(row: dict[str, Any]) -> Any:
    for key in (
        "n_atoms_interface",
        "n_atoms_estimate",
        "natoms",
        "n_atoms",
    ):
        if row.get(key) is not None:
            return row[key]
    return None


def _has_complete_pareto_provenance(
    rows: list[dict[str, Any]],
) -> bool:
    return bool(rows) and all(
        isinstance(row.get("pareto_policy"), str)
        and row.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
        and isinstance(row.get("pareto_population_scope"), str)
        and row.get("pareto_d_cell_key") is not None
        and row.get("is_pareto") is not None
        for row in rows
    )


def _has_authoritative_pareto_provenance(
    rows: list[dict[str, Any]],
) -> bool:
    return _has_complete_pareto_provenance(rows) and all(
        row.get("pareto_policy") == STRAIN_SIZE_PARETO_POLICY
        and row.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
        and row.get("pareto_population_scope") == STRAIN_SIZE_PARETO_POPULATION_SCOPE
        and row.get("pareto_d_cell_key") is not None
        and row.get("is_pareto") is not None
        for row in rows
    )


def _missing_current_collection_objectives(
    rows: list[dict[str, Any]],
) -> bool:
    return any(
        _row_atom_count(row) is None or row.get("d_cell") is None for row in rows
    )


def _mark_pareto_unavailable(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in rows]
    for row in normalized:
        row["is_pareto"] = None
        row["pareto_rank"] = None
        row["pareto_status"] = "unavailable_missing_objectives"
    return normalized


def _compute_current_collection_front(
    rows: list[dict[str, Any]],
    *,
    require_complete: bool,
) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in rows]
    if _missing_current_collection_objectives(normalized):
        if require_complete:
            raise ValueError(
                "A computed strain-size Pareto front requires exact atom "
                "counts and finite d_cell values for every candidate."
            )
        return _mark_pareto_unavailable(normalized)

    result = strain_size_pareto(
        normalized,
        atom_count=_row_atom_count,
        d_cell="d_cell",
        ids=lambda row: (
            row.get("candidate_uid")
            or row.get("prototype_uid")
            or row.get("uid")
            or row.get("candidate_id")
        ),
        policy="current_collection_strain_size_pareto",
        population_scope="current_collection_population",
    )
    rank_by_index = {index: rank for rank, index in enumerate(result.front_idx)}
    for index, row in enumerate(normalized):
        row.update(
            {
                "is_pareto": bool(result.mask[index]),
                "pareto_rank": rank_by_index.get(index),
                "pareto_policy": result.policy,
                "pareto_policy_version": result.version,
                "pareto_population_scope": result.population_scope,
                "pareto_population_size": result.population_size,
                "pareto_d_cell_key": result.d_cell_keys[index],
            }
        )
    return normalized


def _rows_with_pareto_provenance(
    rows: list[dict[str, Any]],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    normalized = [dict(row) for row in rows]
    if mode == "computed":
        return _compute_current_collection_front(
            normalized,
            require_complete=True,
        )
    authoritative = _has_authoritative_pareto_provenance(normalized)
    if authoritative or not normalized:
        return normalized
    if mode == "auto" and _has_complete_pareto_provenance(normalized):
        return normalized
    if mode == "authoritative":
        raise ValueError(
            "Authoritative full-population Pareto provenance is unavailable. "
            "Use scope='auto' or scope='computed' for an explicitly scoped "
            "current-collection front."
        )
    return _compute_current_collection_front(
        normalized,
        require_complete=False,
    )


class CandidateCollection(_BaseCollection):
    """Provide chainable inspection and selection of interface candidates.

    The collection normalizes authoritative prototype records together with
    their database-owned search context into ``InterfaceCandidate``
    objects. It supports material, size, strain,
    termination, and Pareto filtering.

    Authoritative persisted Pareto provenance is preserved when available. A
    computed current-collection front is explicitly scoped and must not be confused
    with the full search-population Pareto set.
    """

    _view_specs = CANDIDATE_VIEW_SPECS

    _items_attr = "_protos"

    def __init__(
        self,
        workspace: Any | None = None,
        prototypes: Iterable[Any] | None = None,
        items: Iterable[Any] | None = None,
        repo: Any | None = None,
        search_name: str | None = None,
    ):
        self._ws = workspace
        self._repo = repo
        self._search_name = search_name
        source = prototypes if prototypes is not None else items
        self._protos = list(source) if source is not None else []
        self._loaded = source is not None
        self._display_rank_by_item_id: dict[int, int] = {}
        if self._loaded:
            self._record_display_ranks(self._protos)

    @staticmethod
    def _explicit_rank(item: Any) -> int | None:
        if isinstance(item, dict):
            value = item.get("rank")
        else:
            value = getattr(item, "rank", None)
        if value is None:
            return None
        return int(value)

    def _record_display_ranks(self, items: Iterable[Any]) -> None:
        for index, item in enumerate(items):
            rank = self._explicit_rank(item)
            self._display_rank_by_item_id[id(item)] = index if rank is None else rank

    def _display_rank(self, item: Any, *, fallback: int | None = None) -> int | None:
        rank = self._explicit_rank(item)
        if rank is not None:
            return rank
        stored = self._display_rank_by_item_id.get(id(item))
        return stored if stored is not None else fallback

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._repo is None:
            raise RuntimeError(
                "CandidateCollection requires an authoritative project repository."
            )
        self._protos = list(self._repo.list_candidates(search_name=self._search_name))
        self._record_display_ranks(self._protos)
        self._loaded = True

    def _clone(self, items):
        selected = list(items)
        clone = CandidateCollection(
            workspace=self._ws,
            prototypes=selected,
            repo=self._repo,
            search_name=self._search_name,
        )
        clone._display_rank_by_item_id = {
            id(item): self._display_rank(item, fallback=index)
            for index, item in enumerate(selected)
        }
        return clone

    def _public_item(self, item: Any) -> InterfaceCandidate:
        return (
            item
            if isinstance(item, InterfaceCandidate)
            else self._as_candidate(item, rank=self._display_rank(item))
        )

    def _normalize_item(self, item: Any) -> dict[str, Any]:
        from calm.public.projections.candidate import normalize_candidate_row

        rank = self._display_rank(item)
        candidate = (
            item
            if isinstance(item, InterfaceCandidate)
            else self._as_candidate(item, rank=rank)
        )
        return normalize_candidate_row(candidate.to_dict(), rank=rank)

    def _as_candidate(
        self,
        item: Any,
        *,
        rank: int | None = None,
    ) -> InterfaceCandidate:
        """Wrap one authoritative prototype row as a public candidate."""
        if isinstance(item, InterfaceCandidate):
            return item
        if isinstance(item, dict):
            row = dict(item)
            prototype = row.pop("_object", None)
            persisted_rank = row.pop("rank", None)
            effective_rank = rank if rank is not None else persisted_rank
            return InterfaceCandidate(prototype, rank=effective_rank, **row)
        return InterfaceCandidate(item, rank=rank)

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        candidates = [
            self._as_candidate(
                item,
                rank=self._display_rank(item, fallback=index),
            )
            for index, item in enumerate(self._protos)
        ]
        rows = [c.to_dict() for c in candidates]

        rows = _rows_with_pareto_provenance(rows, mode="auto")

        return [
            normalize_candidate_row(
                row,
                rank=row.get("rank"),
                is_pareto=row.get("is_pareto"),
            )
            for row in rows
        ]

    def search(self, name: str | None = None, *, id: str | None = None):
        """Filter candidates by public search name or search id.

        ``Project.search_interfaces(...)`` records both ``search_name`` and
        ``search_id`` on candidate rows. This helper is a readable shortcut for
        durable project-query workflows.
        """

        if name is None and id is None:
            return self
        selector = name if name is not None else id
        if not self._loaded and self._repo is not None and selector is not None:
            return CandidateCollection(
                workspace=self._ws,
                repo=self._repo,
                search_name=str(selector),
            )
        self._ensure_loaded()
        out = []
        for p in self._protos:
            r = _row(p)
            if name is not None and r.get("search_name") == name:
                out.append(p)
                continue
            if id is not None and r.get("search_id") == id:
                out.append(p)
        return self._clone(out)

    def materials(self, *names: str):
        if not names:
            return self
        names_l = {n.lower() for n in names}
        self._ensure_loaded()
        filtered = []
        for p in self._protos:
            r = _row(p)
            vals = {
                str(r.get("material_a") or "").lower(),
                str(r.get("material_b") or "").lower(),
            }
            # fall back to labels/surface fields when material fields are absent
            vals.update(
                {
                    str(r.get("surface_a") or "").lower(),
                    str(r.get("surface_b") or "").lower(),
                }
            )
            if vals & names_l:
                filtered.append(p)
        return self._clone(filtered)

    def atoms(self, *, min: int | None = None, max: int | None = None):
        return self.where(n_atoms_estimate=(min, max))

    def pareto(self, *, scope: str = "auto"):
        scope_token = str(scope).lower()
        if scope_token not in {
            "auto",
            "authoritative",
            "computed",
        }:
            raise ValueError(
                "CandidateCollection.pareto scope must be 'auto', "
                "'authoritative', or 'computed'."
            )
        self._ensure_loaded()
        candidates = [
            self._as_candidate(
                item,
                rank=self._display_rank(item, fallback=index),
            )
            for index, item in enumerate(self._protos)
        ]
        mode = "authoritative" if scope_token == "authoritative" else "auto"
        if scope_token == "computed":
            mode = "computed"
        rows = _rows_with_pareto_provenance(
            [candidate.to_dict() for candidate in candidates],
            mode=mode,
        )
        annotated: list[InterfaceCandidate] = []
        for candidate, row in zip(candidates, rows):
            for key in (
                "is_pareto",
                "pareto_rank",
                "pareto_policy",
                "pareto_policy_version",
                "pareto_population_scope",
                "pareto_population_size",
                "pareto_d_cell_key",
            ):
                setattr(candidate, key, row.get(key))
            if bool(row.get("is_pareto")):
                annotated.append(candidate)
        return self._clone(annotated)

    def strain(self, strain_filter: Any):
        self._ensure_loaded()
        return self._clone(
            [p for p in self._protos if bool(strain_filter.matches(_row(p)))]
        )

    def miller_pair(
        self,
        miller_a: tuple[int, int, int],
        miller_b: tuple[int, int, int],
    ):
        self._ensure_loaded()
        ma_t = tuple(int(x) for x in miller_a)
        mb_t = tuple(int(x) for x in miller_b)
        out = []
        for p in self._protos:
            r = _row(p)
            ma = r.get("miller_a")
            mb = r.get("miller_b")
            try:
                ma = tuple(int(x) for x in ma)
                mb = tuple(int(x) for x in mb)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Candidate Miller indices must be exact integer triplets."
                ) from exc
            if len(ma) != 3 or len(mb) != 3:
                raise ValueError(
                    "Candidate Miller indices must be exact integer triplets."
                )
            if ma == ma_t and mb == mb_t:
                out.append(p)
        return self._clone(out)

    def tags(self, *tags: str):
        tags_l = {t.lower() for t in tags}
        self._ensure_loaded()
        out = []
        for p in self._protos:
            rtags = _row(p).get("tags") or []
            if isinstance(rtags, str):
                rtags = [rtags]
            if {str(t).lower() for t in rtags} & tags_l:
                out.append(p)
        return self._clone(out)

    def terminations(self, *terminations: str):
        tset = {t.lower() for t in terminations}
        self._ensure_loaded()
        out = []
        for p in self._protos:
            r = _row(p)
            vals = {
                str(r.get("termination_a") or "").lower(),
                str(r.get("termination_b") or "").lower(),
                str(r.get("termination") or "").lower(),
            }
            if vals & tset:
                out.append(p)
        return self._clone(out)

    def select_top(self, n: int = 1, by: str = "score"):
        self._ensure_loaded()
        col = require_current_metric_name(by, argument="Candidate ranking field")

        def key(p):
            value = _row(p).get(col)
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Candidate ranking metric {col!r} must be numeric."
                ) from exc
            if not isfinite(number):
                raise ValueError(f"Candidate ranking metric {col!r} must be finite.")
            return number

        return self._clone(sorted(self._protos, key=key)[: int(n)])

    def select(
        self,
        *,
        n_per_pair: int | None = None,
        pareto: bool = False,
        strain: Any | None = None,
        **kwargs,
    ):
        coll = self.pareto() if pareto else self
        if strain is not None:
            coll = coll.strain(strain)
        if kwargs:
            coll = coll.where(**kwargs)
        if n_per_pair is None:
            return coll
        coll._ensure_loaded()
        groups: dict[tuple, list] = {}
        for p in coll._protos:
            r = _row(p)
            key = (
                tuple(r.get("miller_a") or (None, None, None)),
                tuple(r.get("miller_b") or (None, None, None)),
            )
            groups.setdefault(key, []).append(p)
        selected = []
        for items in groups.values():
            selected.extend(items[: int(n_per_pair)])
        return self._clone(selected)

    def get(self, *args, **filters):
        if "rank" in filters:
            rank = int(filters.pop("rank"))
            self._ensure_loaded()
            for p in self._protos:
                if self._display_rank(p) == rank:
                    return self._as_candidate(p, rank=rank)
            raise KeyError(f"No candidate with rank={rank}.")
        obj = super().get(*args, **filters)
        return obj if isinstance(obj, InterfaceCandidate) else self._as_candidate(obj)

    def validate_buildable(self):
        """Validate every candidate through the authoritative batch checker."""
        from calm.public.projections.buildability import (
            prototype_identifier_from_candidate_row,
        )
        from calm.public.projections.candidate import normalize_candidate_row
        from calm.public.records.buildability import (
            BuildabilityIssue,
            BuildabilityReport,
        )

        self._ensure_loaded()
        rows = [
            normalize_candidate_row(
                self._normalize_item(item),
                rank=self._display_rank(item, fallback=index),
            )
            for index, item in enumerate(self._protos)
        ]
        identifiers = [
            identifier
            for row in rows
            if (identifier := prototype_identifier_from_candidate_row(row)) is not None
        ]
        results = self._ws.check_prototypes_buildability(identifiers)

        issues: list[BuildabilityIssue] = []
        n_buildable = 0
        for row in rows:
            candidate_id = row.get("candidate_id")
            candidate_uid = (
                row.get("candidate_uid") or row.get("prototype_uid") or row.get("uid")
            )
            identifier = prototype_identifier_from_candidate_row(row)
            if identifier is None:
                reasons = ["missing_prototype"]
                buildable = False
            else:
                result = results.get(identifier)
                if result is None:
                    reasons = ["prototype_not_found"]
                    buildable = False
                else:
                    reasons = list(result.reasons)
                    buildable = bool(result.buildable)

            if buildable:
                n_buildable += 1
                continue
            issues.append(
                BuildabilityIssue(
                    candidate_id=candidate_id,
                    candidate_uid=candidate_uid,
                    code=reasons[0] if reasons else "unknown",
                    message=",".join(reasons) if reasons else "not buildable",
                )
            )

        return BuildabilityReport(
            n_candidates=len(rows),
            n_buildable=n_buildable,
            issues=issues,
        )
