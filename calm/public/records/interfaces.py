"""Public result containers for CALM facade workflows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TextIO

from calm.analysis.pareto import (
    STRAIN_SIZE_PARETO_POLICY,
    STRAIN_SIZE_PARETO_POPULATION_SCOPE,
    STRAIN_SIZE_PARETO_VERSION,
    strain_size_pareto,
)

from calm.project.presentation.notebook import TableView, _ascii_table_value
from calm.public.collections.views import view_registry
from calm.public.records.candidate_views import (
    CANDIDATE_VIEW_SPECS,
    resolve_candidate_projection,
)
from calm.public.projections.strain import project_candidate_strain_metrics
from calm.public.presentation.plotting import plot_pareto as _plot_pareto
from calm.public.inputs.settings import BuildSettings

if TYPE_CHECKING:
    from calm.public.records.search_audit import InterfaceSearchEnumerationAudit


_MISSING = object()


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default

    for name in names:
        value = getattr(obj, name, _MISSING)
        if value is not _MISSING:
            return value

    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        row = to_dict()
        if not isinstance(row, dict):
            raise TypeError(f"{type(obj).__name__}.to_dict() must return a dict.")
        for name in names:
            if name in row:
                return row[name]
    return default


def _short_uid(value: Any, *, head: int = 12) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= head + 3:
        return text
    return text[:head] + "..."


def _display_candidate_id(
    row: dict[str, Any], *, rank: int | None = None
) -> str | None:
    existing = row.get("candidate_id")
    if existing is not None and not str(existing).startswith(("proto:", "build:")):
        return str(existing)
    uid = row.get("uid") or row.get("prototype_uid") or existing
    if uid is not None:
        uid_s = str(uid)
        if not uid_s.startswith(("proto:", "build:")) and len(uid_s) <= 64:
            return uid_s
    if rank is not None:
        return f"C{int(rank):04d}"
    return _short_uid(uid, head=16)


def _primitive_pair_identity_key(row: dict[str, Any]) -> tuple[Any, ...] | None:
    """Return the authoritative exact coupled-pair identity key."""

    pair_identity = row.get("pair_identity")
    if not isinstance(pair_identity, dict):
        return None
    primitive_key = pair_identity.get("primitive_pair_key")
    key_version = pair_identity.get("key_version")
    pair_symmetry = pair_identity.get("pair_symmetry_policy")
    orientation = pair_identity.get("correspondence_orientation")
    exchange = pair_identity.get("material_exchange_identified")
    if not isinstance(primitive_key, (list, tuple)) or len(primitive_key) != 8:
        return None
    if (
        isinstance(key_version, bool)
        or not isinstance(key_version, int)
        or key_version <= 0
    ):
        return None
    if any(
        isinstance(value, bool) or not isinstance(value, int) for value in primitive_key
    ):
        return None
    if pair_symmetry not in {"proper", "full"}:
        return None
    if orientation not in {"proper", "all"}:
        return None
    if not isinstance(exchange, bool):
        return None
    return (
        key_version,
        tuple(primitive_key),
        pair_symmetry,
        orientation,
        exchange,
    )


def _validate_authoritative_coupled_candidates(
    candidates: Sequence["InterfaceCandidate"],
) -> None:
    """Require complete and unique coupled-v2 identities at projection time."""

    seen: dict[tuple[Any, ...], int] = {}
    for index, candidate in enumerate(candidates):
        row = candidate.to_dict(include_internal=False)
        key = _primitive_pair_identity_key(row)
        if key is None:
            raise ValueError(
                "Coupled-v2 public projection requires every prototype to "
                "carry a complete exact pair_identity; invalid prototype at "
                f"index {index}."
            )
        previous = seen.get(key)
        if previous is not None:
            raise ValueError(
                "Coupled-v2 public projection received duplicate exact "
                "primitive pair identities at indices "
                f"{previous} and {index}."
            )
        seen[key] = index


def _strain_metrics_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return project_candidate_strain_metrics(row)


def _prototype_to_row(prototype: Any, *, rank: int | None = None) -> dict[str, Any]:
    if hasattr(prototype, "to_dict"):
        try:
            row = prototype.to_dict(rank=rank)
        except TypeError:
            row = prototype.to_dict()
            if rank is not None:
                row.setdefault("rank", int(rank))
    elif isinstance(prototype, dict):
        row = dict(prototype)
        if rank is not None:
            row.setdefault("rank", int(rank))
    else:
        row = {
            "uid": _get(prototype, "uid", "prototype_uid"),
            "score": _get(prototype, "score", "match_score"),
            "d_cell": _get(prototype, "d_cell"),
            "hencky_norm": _get(prototype, "hencky_norm"),
            "d_area": _get(prototype, "d_area"),
            "d_shape": _get(prototype, "d_shape"),
            "d_size": _get(prototype, "d_size"),
            "n_atoms_interface": _get(
                prototype, "n_atoms_interface", "n_atoms_estimate"
            ),
            "miller_a": _get(prototype, "miller_a"),
            "miller_b": _get(prototype, "miller_b"),
            "k_a": _get(_get(prototype, "supercell_a"), "k"),
            "k_b": _get(_get(prototype, "supercell_b"), "k"),
            "is_pareto": _get(prototype, "is_pareto"),
            "pareto_rank": _get(prototype, "pareto_rank"),
            "pareto_policy": _get(prototype, "pareto_policy"),
            "pareto_policy_version": _get(prototype, "pareto_policy_version"),
            "pareto_population_scope": _get(prototype, "pareto_population_scope"),
            "pareto_population_size": _get(prototype, "pareto_population_size"),
            "pareto_d_cell_key": _get(prototype, "pareto_d_cell_key"),
            "pareto_status": _get(prototype, "pareto_status"),
        }
        if rank is not None:
            row["rank"] = int(rank)
    if row.get("d_cell") is None and row.get("hencky_norm") is not None:
        row["d_cell"] = 2.0 * float(row["hencky_norm"])
    uid = row.get("uid") or row.get("prototype_uid") or row.get("candidate_id")
    if uid is not None:
        row.setdefault("uid", uid)
        row.setdefault("candidate_uid", uid)
    row["candidate_id"] = _display_candidate_id(row, rank=rank)
    row.setdefault("score", row.get("match_score"))
    row.setdefault(
        "n_atoms_estimate", row.get("n_atoms_interface") or row.get("n_atoms")
    )
    row = _strain_metrics_from_row(row)
    return row


class InterfaceCandidate:
    """User-facing projection of an interface-search candidate.

    The public candidate record intentionally separates display identity
    (``candidate_id``) from scientific/provenance identity
    (``candidate_uid``/``prototype_uid``). The optional ``prototype`` attribute
    is an internal build-stage representation and is omitted from public row
    projections unless explicitly requested with ``include_internal=True``.
    """

    def __init__(
        self,
        prototype: Any | None = None,
        *,
        rank: int | None = None,
        **kwargs,
    ):
        self.prototype = (
            prototype if prototype is not None else kwargs.pop("prototype", None)
        )
        row = _prototype_to_row(
            self.prototype if self.prototype is not None else kwargs,
            rank=rank,
        )
        row.update(kwargs)
        row["candidate_id"] = _display_candidate_id(
            row,
            rank=rank if rank is not None else row.get("rank"),
        )
        row = _strain_metrics_from_row(row)
        from calm.public.records.persistence import record_authority

        row.setdefault(
            "authority",
            record_authority(
                self.prototype if self.prototype is not None else row,
                authoritative_keys=("project_prototype_uid", "project_prototype_id"),
            ).value,
        )
        for k, v in row.items():
            setattr(self, k, v)

    @classmethod
    def from_prototype(
        cls,
        prototype: Any,
        *,
        rank: int | None = None,
    ) -> "InterfaceCandidate":
        return cls(prototype=prototype, rank=rank)

    @property
    def is_pareto(self) -> bool | None:
        return getattr(self, "_is_pareto", getattr(self, "pareto", None))

    @is_pareto.setter
    def is_pareto(self, value: bool | None) -> None:
        self._is_pareto = value

    def to_dict(self, *, include_internal: bool = False) -> dict[str, Any]:
        """Project the candidate into a public row dictionary.

        Internal prototype objects are excluded by default so reporting,
        persistence, and table projections carry stable public fields rather
        than build-stage implementation objects.
        """
        row = {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith("_") and k != "prototype"
        }
        uid = row.get("uid") or row.get("prototype_uid") or row.get("candidate_uid")
        if uid is not None:
            row.setdefault("candidate_uid", uid)
        if row.get("candidate_id") is None or str(row.get("candidate_id")).startswith(
            ("proto:", "build:")
        ):
            row["candidate_id"] = _display_candidate_id(row, rank=row.get("rank"))
        row["is_pareto"] = self.is_pareto
        row = _strain_metrics_from_row(row)
        if include_internal and self.prototype is not None:
            row["prototype"] = self.prototype
        return row

    def summary(self) -> str:
        row = self.to_dict()
        lines = [
            f"CALM interface candidate {row.get('rank', row.get('candidate_id', ''))}"
        ]
        if row.get("miller_a") is not None or row.get("miller_b") is not None:
            lines.append(f"  surfaces: {row.get('miller_a')} | {row.get('miller_b')}")
        lines.append("  match diagnostics:")
        for k in [
            "d_cell",
            "d_area",
            "d_shape",
            "max_principal_strain",
            "isotropic_strain_norm",
            "deviatoric_strain_norm",
        ]:
            if row.get(k) is not None:
                lines.append(f"    {k}: {float(row[k]):.6g}")
        lines.append("  size:")
        for k in ["n_atoms_estimate", "d_size", "k_a", "k_b"]:
            if row.get(k) is not None:
                lines.append(f"    {k}: {row[k]}")
        if row.get("score") is not None:
            lines.append(f"  score: {row['score']}")
        return "\n".join(lines)


class InterfaceSearchResult(Sequence):
    """Sequence-like user-facing result returned by ``search_interfaces``."""

    def __init__(
        self,
        request: Any,
        candidates: Sequence[InterfaceCandidate],
        *,
        internal_result: Any | None = None,
        metadata: dict | None = None,
        apply_pareto: bool = True,
    ):
        self.request = request
        self.candidates = tuple(candidates)
        self._internal_result = internal_result
        self.metadata = dict(metadata or {})
        if apply_pareto:
            self._apply_pareto_flags()

    @classmethod
    def from_internal(
        cls,
        internal_result: Any,
        *,
        request: Any = None,
        surface_a: Any = None,
        surface_b: Any = None,
    ) -> "InterfaceSearchResult":
        protos = list(getattr(internal_result, "prototypes", []) or [])
        candidates = [
            InterfaceCandidate.from_prototype(prototype, rank=index)
            for index, prototype in enumerate(protos)
        ]
        _validate_authoritative_coupled_candidates(candidates)
        for cand in candidates:
            if surface_a is not None:
                cand.material_a = getattr(surface_a, "material", None)
                cand.surface_a_label = getattr(surface_a, "label", None)
                cand.surface_a_uid_full = getattr(
                    surface_a, "project_slab_uid_full", None
                )
                cand.surface_a_id_short = getattr(
                    surface_a, "project_slab_id_short", None
                )
                cand.termination_a = getattr(surface_a, "termination", None)
                cand.termination_shift_a = getattr(surface_a, "termination_shift", None)
            if surface_b is not None:
                cand.material_b = getattr(surface_b, "material", None)
                cand.surface_b_label = getattr(surface_b, "label", None)
                cand.surface_b_uid_full = getattr(
                    surface_b, "project_slab_uid_full", None
                )
                cand.surface_b_id_short = getattr(
                    surface_b, "project_slab_id_short", None
                )
                cand.termination_b = getattr(surface_b, "termination", None)
                cand.termination_shift_b = getattr(surface_b, "termination_shift", None)
        surface_symmetry_a = getattr(
            internal_result,
            "surface_symmetry_a",
            None,
        )
        surface_symmetry_b = getattr(
            internal_result,
            "surface_symmetry_b",
            None,
        )
        if (surface_symmetry_a is None) != (surface_symmetry_b is None):
            raise ValueError(
                "internal search result has incomplete surface-symmetry provenance."
            )
        has_surface_symmetry = surface_symmetry_a is not None
        metadata = {
            "surface_symmetry_status": (
                "validated" if has_surface_symmetry else "legacy_unrecorded"
            ),
            "surface_symmetry_a": (
                surface_symmetry_a.to_dict() if has_surface_symmetry else None
            ),
            "surface_symmetry_b": (
                surface_symmetry_b.to_dict() if has_surface_symmetry else None
            ),
            "pareto_policy": getattr(internal_result, "pareto_policy", None),
            "pareto_policy_version": getattr(
                internal_result, "pareto_policy_version", None
            ),
            "pareto_population_scope": getattr(
                internal_result, "pareto_population_scope", None
            ),
            "pareto_population_size": getattr(
                internal_result, "pareto_population_size", None
            ),
            "pareto_front_uids": list(
                getattr(internal_result, "pareto_front_uids", ()) or ()
            ),
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}
        return cls(
            request=request,
            candidates=candidates,
            internal_result=internal_result,
            metadata=metadata,
        )

    def __len__(self):
        return len(self.candidates)

    def __getitem__(self, idx):
        return self.candidates[idx]

    def __iter__(self):
        return iter(self.candidates)

    def enumeration_audit(self) -> "InterfaceSearchEnumerationAudit | None":
        """Return immutable enumeration accounting for this in-memory search.

        Returns ``None`` only for legacy or synthetic results that do not carry
        matcher accounting.
        """

        audit = getattr(self._internal_result, "enumeration_audit", None)
        if audit is None:
            return None
        from calm.public.records.search_audit import InterfaceSearchEnumerationAudit

        return InterfaceSearchEnumerationAudit.from_value(audit)

    @property
    def best(self):
        return self.candidates[0] if self.candidates else None

    @property
    def empty(self):
        return len(self.candidates) == 0

    @property
    def pareto(self) -> "InterfaceSearchResult":
        return self.select(pareto=True)

    def _apply_pareto_flags(self) -> None:
        rows = [candidate.to_dict() for candidate in self.candidates]
        if not rows:
            return

        has_authoritative_source = all(
            row.get("pareto_policy") == STRAIN_SIZE_PARETO_POLICY
            and row.get("pareto_policy_version") == STRAIN_SIZE_PARETO_VERSION
            and row.get("pareto_population_scope")
            == STRAIN_SIZE_PARETO_POPULATION_SCOPE
            and row.get("pareto_d_cell_key") is not None
            and row.get("is_pareto") is not None
            for row in rows
        )
        if has_authoritative_source:
            self.metadata.setdefault("pareto_policy", STRAIN_SIZE_PARETO_POLICY)
            self.metadata.setdefault(
                "pareto_policy_version", STRAIN_SIZE_PARETO_VERSION
            )
            self.metadata.setdefault(
                "pareto_population_size",
                max(
                    (int(row.get("pareto_population_size") or 0) for row in rows),
                    default=len(rows),
                ),
            )
            return

        missing_objectives = any(
            row.get("n_atoms_estimate") is None or row.get("d_cell") is None
            for row in rows
        )
        if missing_objectives:
            self.metadata.setdefault(
                "pareto_status",
                "unavailable_missing_objectives",
            )
            for candidate in self.candidates:
                candidate.is_pareto = None
                candidate.pareto_rank = None
                candidate.pareto_status = "unavailable_missing_objectives"
            return

        result = strain_size_pareto(
            rows,
            atom_count="n_atoms_estimate",
            d_cell="d_cell",
            ids="candidate_uid",
            policy="current_result_strain_size_pareto",
            population_scope="current_result_population",
        )
        rank_by_index = {index: rank for rank, index in enumerate(result.front_idx)}
        for index, candidate in enumerate(self.candidates):
            candidate.is_pareto = bool(result.mask[index])
            candidate.pareto_rank = rank_by_index.get(index)
            candidate.pareto_policy = result.policy
            candidate.pareto_policy_version = result.version
            candidate.pareto_population_scope = result.population_scope
            candidate.pareto_population_size = result.population_size
            candidate.pareto_d_cell_key = result.d_cell_keys[index]

        self.metadata.update(
            {
                "pareto_policy": result.policy,
                "pareto_policy_version": result.version,
                "pareto_population_scope": result.population_scope,
                "pareto_population_size": result.population_size,
                "pareto_front_uids": list(result.front_ids),
            }
        )

    _view_specs = CANDIDATE_VIEW_SPECS
    _default_view = "summary"

    @classmethod
    def available_views(cls) -> tuple[str, ...]:
        """Return the canonical named candidate views."""

        view_registry(cls._view_specs)
        return tuple(spec.name for spec in cls._view_specs)

    def _resolve_projection(
        self,
        *,
        view: str | None = None,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ):
        return resolve_candidate_projection(
            self.candidates,
            view=view,
            include=include,
            exclude=exclude,
        )

    def to_rows(self, *, view: str = "summary") -> list[dict[str, Any]]:
        """Return homogeneous rows for one validated candidate view."""

        return self._resolve_projection(view=view).to_rows()

    def to_table(
        self,
        *,
        view: str = "summary",
        title: str = "Interface candidates",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ) -> TableView:
        """Return a table using the shared candidate view registry."""

        projection = self._resolve_projection(
            view=view,
            include=include,
            exclude=exclude,
        )
        return TableView(
            rows=projection.to_rows(),
            title=title,
            include=projection.columns,
            column_labels=dict(projection.display_labels),
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(self, *, view: str = "summary"):
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "to_dataframe() requires pandas. Use to_rows() when pandas "
                "is unavailable."
            ) from e
        projection = self._resolve_projection(view=view)
        return pd.DataFrame.from_records(
            projection.to_rows(),
            columns=list(projection.columns),
        )

    def write_table(
        self,
        path,
        *,
        view: str = "summary",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        """Write one candidate view to CSV with the resolved ordered schema."""

        projection = self._resolve_projection(
            view=view,
            include=include,
            exclude=exclude,
        )
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not projection.columns:
            p.write_text("", encoding="utf-8")
            return
        with p.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=list(projection.columns),
                extrasaction="raise",
            )
            writer.writeheader()
            writer.writerows(
                {
                    key: _ascii_table_value(value)
                    for key, value in row.items()
                }
                for row in projection.rows
            )

    def select(
        self,
        *,
        pareto: bool = False,
        strain: Any | None = None,
        max_atoms: int | None = None,
        n: int | None = None,
    ) -> "InterfaceSearchResult":
        cands = list(self.candidates)
        if pareto:
            cands = [c for c in cands if bool(c.is_pareto)]
        if strain is not None:
            cands = [c for c in cands if bool(strain.matches(c.to_dict()))]
        if max_atoms is not None:
            cands = [
                c
                for c in cands
                if (
                    c.to_dict().get("n_atoms_estimate") is not None
                    and int(c.to_dict()["n_atoms_estimate"]) <= int(max_atoms)
                )
            ]
        if n is not None:
            cands = cands[: int(n)]
        # Preserve the Pareto flags from the parent search. Recomputing them on
        # every filtered subset makes a dominated candidate appear Pareto-optimal
        # merely because all dominating points were filtered out. Users can ask
        # plot_pareto(front="computed") when they explicitly want a front
        # recomputed in the current selection and displayed metric plane.
        return InterfaceSearchResult(
            self.request,
            cands,
            internal_result=self._internal_result,
            metadata=self.metadata,
            apply_pareto=False,
        )

    def plot_pareto(
        self,
        *,
        x: str = "n_atoms_estimate",
        y: str = "d_cell",
        front: str = "global",
        save: str | None = None,
        **kwargs,
    ):
        return _plot_pareto(
            self.to_rows(view="all"), x=x, y=y, front=front, save=save, **kwargs
        )

    def summary(self) -> str:
        n = len(self.candidates)
        p = sum(1 for c in self.candidates if c.is_pareto)
        lines = [
            "CALM interface search result",
            f"  candidates: {n}",
            f"  Pareto candidates: {p}",
        ]
        if self.best is not None:
            row = self.best.to_dict()
            lines.append("  best candidate:")
            for k in [
                "candidate_id",
                "score",
                "d_cell",
                "max_principal_strain",
                "n_atoms_estimate",
            ]:
                if row.get(k) is not None:
                    lines.append(f"    {k}: {row[k]}")
        return "\n".join(lines)

    def explain(self) -> str:
        if not self.empty:
            return self.summary()
        settings = getattr(self.request, "search", None) or getattr(
            self.request, "settings", None
        )
        lines = ["No interface candidates were found."]
        if settings is not None:
            lines.append("\nSearch constraints:")
            for k in ["max_principal_strain", "max_supercell_index", "max_atoms"]:
                if hasattr(settings, k):
                    lines.append(f"  {k} = {getattr(settings, k)}")
        lines.append(
            "\nTry increasing max_principal_strain, max_supercell_index, or max_atoms, and inspect the selected surfaces/terminations."
        )
        return "\n".join(lines)


class InterfaceModel:
    """Public wrapper around an atomistic interface object."""

    def __init__(
        self,
        internal_interface: Any,
        *,
        candidate: Any | None = None,
        build_settings: BuildSettings | None = None,
    ):
        self._internal = internal_interface
        self.candidate = candidate
        self.build_settings = build_settings

    @property
    def atoms(self):
        return getattr(self._internal, "atoms", None)

    @property
    def n_atoms(self) -> int | None:
        try:
            return len(self.atoms)
        except Exception:
            return None

    def summary(self) -> str:
        lines = ["CALM interface model"]
        lines.append(f"  atoms: {self.n_atoms}")
        area = getattr(self._internal, "area_A2", None)
        if area is not None:
            try:
                lines.append(f"  area: {float(area):.6g} Å²")
            except Exception:
                lines.append(f"  area: {area}")
        if self.candidate is not None:
            cid = getattr(self.candidate, "candidate_id", None)
            if cid is not None:
                lines.append(f"  source candidate: {cid}")
        build_uid = getattr(self._internal, "build_uid", None)
        proto_uid = getattr(self._internal, "prototype_uid", None)
        if build_uid is not None or proto_uid is not None:
            lines.append("  provenance:")
            if build_uid is not None:
                lines.append(f"    build_uid: {_short_uid(build_uid, head=24)}")
            if proto_uid is not None:
                lines.append(f"    prototype_uid: {_short_uid(proto_uid, head=24)}")
        if self.build_settings is not None:
            lines.append("  build settings:")
            for k, v in self.build_settings.to_dict().items():
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)

    def to_ase(self):
        return self.atoms

    def write(self, path: str | Path, *, format: str | None = None) -> None:
        from calm.structure.io import write_structure

        write_structure(path, self.atoms, format=format)
