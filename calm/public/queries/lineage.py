"""Read-only authoritative lineage reconstruction for the public facade."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from typing import Any


class ProjectLineageQueryService:
    """Resolve and traverse persisted provenance without mutating project state."""

    def __init__(self, *, repository: Any) -> None:
        self._repo = repository

    @staticmethod
    def _identifier(target: Any) -> str:
        if isinstance(target, str):
            return target
        if isinstance(target, Mapping):
            for key in (
                "uid_full",
                "project_prototype_uid",
                "project_interface_uid",
                "project_dataset_uid",
                "dataset_uid_full",
                "campaign_uid_full",
                "target_uid_full",
                "run_uid_full",
            ):
                value = target.get(key)
                if value:
                    return str(value)
        for key in (
            "uid_full",
            "project_prototype_uid",
            "project_interface_uid",
            "project_dataset_uid",
            "run_uid_full",
        ):
            value = getattr(target, key, None)
            if value:
                return str(value)
        raise TypeError(
            "lineage() requires a persisted object, full UID, or project short ID."
        )

    @staticmethod
    def _kind_hints(edge: Any) -> dict[str, str]:
        """Infer endpoint entity kinds from the persisted edge contract."""
        relation = {
            "bulk_to_slab": ("material", "surface"),
            "run_to_prototype": ("run", "candidate"),
            "slab_to_prototype": ("surface", "candidate"),
            "prototype_to_interface": ("candidate", "interface"),
            "interface_to_interface": ("interface", "interface"),
            "run_to_followup": ("run", "followup_result"),
            "prototype_to_followup": ("candidate", "followup_result"),
            "interface_to_followup": ("interface", "followup_result"),
            "followup_to_interface": ("followup_result", "interface"),
            "run_to_artifact": ("run", "artifact"),
            "dataset_item_from_prototype": ("dataset_item", "candidate"),
            "dataset_item_from_build": ("dataset_item", "interface"),
            "dataset_item_from_source": ("dataset_item", "unknown"),
            "dataset_item_from_component": ("dataset_item", "unknown"),
            "included_in_dataset": ("dataset_item", "dataset"),
            "dataset_item_uses_artifact": ("dataset_item", "artifact"),
            "produced_by": ("dataset", "campaign_run"),
            "belonged_to_campaign": ("dataset", "campaign"),
            "run_of_campaign": ("run", "campaign"),
            "run_of_campaign_execution": ("run", "campaign_run"),
        }.get(edge.kind)
        if relation is None:
            return {}
        return {
            edge.src_uid_full: relation[0],
            edge.dst_uid_full: relation[1],
        }

    def _node(self, uid_full: str, *, kind_hint: str | None = None):
        from calm.public.records.persistence import LineageNode, uid_kind

        inferred_kind = uid_kind(uid_full)
        if inferred_kind == "unknown" and kind_hint is not None:
            inferred_kind = kind_hint

        getters = {
            "material": self._repo.get_bulk,
            "surface": self._repo.get_slab,
            "candidate": self._repo.get_prototype,
            "interface": self._repo.get_interface,
            "run": self._repo.get_run,
            "followup_result": self._repo.get_followup_result,
            "dataset": self._repo.get_dataset,
            "campaign": self._repo.get_campaign,
            "campaign_run": self._repo.get_campaign_run,
        }
        item = None
        getter = getters.get(inferred_kind)
        if getter is not None:
            try:
                item = getter(uid_full)
            except (AttributeError, KeyError, ValueError, RuntimeError):
                item = None

        # Content-derived identities such as bulk and follow-up hashes may not
        # carry a type prefix. Probe exact authoritative repositories only when
        # neither the UID nor its incident edges identify the entity kind.
        if item is None and inferred_kind == "unknown":
            for candidate_kind, candidate_getter in getters.items():
                try:
                    candidate = candidate_getter(uid_full)
                except (AttributeError, KeyError, ValueError, RuntimeError):
                    continue
                if candidate is not None:
                    inferred_kind = candidate_kind
                    item = candidate
                    break

        if isinstance(item, Mapping):
            id_short = item.get("id_short")
            label = item.get("label") or item.get("name")
        else:
            id_short = getattr(item, "id_short", None)
            label = getattr(item, "label", None) or getattr(item, "name", None)
        return LineageNode(
            uid_full=uid_full,
            kind=inferred_kind,
            id_short=str(id_short) if id_short is not None else None,
            label=str(label) if label is not None else None,
        )

    def lineage(
        self,
        target: Any,
        *,
        direction: str = "both",
        depth: int | None = None,
        kinds: tuple[str, ...] | list[str] | set[str] | None = None,
    ):
        """Return the authoritative persisted provenance subgraph for *target*."""
        from calm.public.records.persistence import LineageGraph, ProjectEdge

        if direction not in {"upstream", "downstream", "both"}:
            raise ValueError("direction must be 'upstream', 'downstream', or 'both'.")
        if depth is not None and depth < 0:
            raise ValueError("depth must be non-negative or None.")
        if isinstance(kinds, str):
            raise TypeError(
                "kinds must be a collection of edge-kind strings, not a string."
            )

        identifier = self._identifier(target)
        root_uid = self._repo.resolve_identifier(identifier)
        allowed_kinds = set(kinds) if kinds is not None else None
        queue = deque([(root_uid, 0)])
        seen_nodes = {root_uid}
        edges_by_uid: dict[str, ProjectEdge] = {}
        kind_hints: dict[str, str] = {}

        while queue:
            current, level = queue.popleft()
            if depth is not None and level >= depth:
                continue

            raw_edges: list[Any] = []
            if direction in {"upstream", "both"}:
                raw_edges.extend(self._repo.list_edges(dst=current))
            if direction in {"downstream", "both"}:
                raw_edges.extend(self._repo.list_edges(src=current))

            for raw_edge in raw_edges:
                edge = ProjectEdge.from_item(raw_edge)
                if allowed_kinds is not None and edge.kind not in allowed_kinds:
                    continue
                edge_key = edge.uid_full or (
                    f"{edge.src_uid_full}|{edge.kind}|{edge.dst_uid_full}"
                )
                edges_by_uid[edge_key] = edge
                kind_hints.update(self._kind_hints(edge))
                for neighbor in (edge.src_uid_full, edge.dst_uid_full):
                    if neighbor not in seen_nodes:
                        seen_nodes.add(neighbor)
                        queue.append((neighbor, level + 1))

        nodes = tuple(
            self._node(uid_full, kind_hint=kind_hints.get(uid_full))
            for uid_full in sorted(seen_nodes)
        )
        edges = tuple(
            sorted(
                edges_by_uid.values(),
                key=lambda edge: (
                    edge.created_at or "",
                    edge.kind,
                    edge.src_uid_full,
                    edge.dst_uid_full,
                ),
            )
        )
        return LineageGraph(
            root_uid_full=root_uid,
            nodes=nodes,
            edges=edges,
        )
