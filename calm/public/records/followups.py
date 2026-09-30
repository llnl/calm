"""Typed public results for authoritative follow-up workflows."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from math import isclose, isfinite
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from calm.project.domain.contracts.refinement_result import (
    registry_result_state,
    strain_partition_selection,
)
from calm.public.records.result_views import (
    ENERGY_WORKFLOW_COMBINED_VIEW_SPECS,
    RAW_ENERGY_RESULT_VIEW_SPECS,
    REFERENCE_ENERGY_RESULT_VIEW_SPECS,
    REGISTRY_SEARCH_VIEW_SPECS,
    RELAXATION_RESULT_VIEW_SPECS,
    STRAIN_PARTITION_VIEW_SPECS,
    THERMODYNAMIC_RESULT_VIEW_SPECS,
    registry_search_rows,
    strain_partition_rows,
)
from calm.public.records.tabular import (
    TabularResultMixin,
    projection_dataframe,
    projection_table,
    resolve_named_projection,
    write_projection_csv,
)


def _positive_reference_area(value: Any) -> float:
    """Return one finite positive persisted reference area."""

    try:
        area = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "Calculated reference results are missing an authoritative "
            "positive interface area."
        ) from exc
    if not isfinite(area) or area <= 0.0:
        raise RuntimeError(
            "Calculated reference results are missing an authoritative "
            "positive interface area."
        )
    return area


def _write_rows_csv(
    path: str | Path,
    rows: list[dict],
    *,
    preferred: list[str] | None = None,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    preferred = preferred or []
    all_keys = set()
    for r in rows:
        all_keys.update(r.keys())

    fieldnames: list[str] = []
    for k in preferred:
        if k in all_keys:
            fieldnames.append(k)
            all_keys.remove(k)
    remaining = sorted(all_keys)
    fieldnames.extend(remaining)

    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class StrainPartitionScan(TabularResultMixin):
    _view_specs = STRAIN_PARTITION_VIEW_SPECS

    project: Any
    run: Any

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        results = list(
            self.project.followups(
                run=self.run.id_short,
                kind="strain_partition_scan",
            )
        )
        out: list[dict] = []
        for result in results:
            payload = dict(result.payload or {})
            points = payload.get("points", [])
            if not isinstance(points, list):
                raise TypeError("Strain-partition result points must be a list.")
            target_metric, target_alpha, target_value = strain_partition_selection(
                payload
            )
            for point in points:
                if not isinstance(point, Mapping):
                    raise TypeError(
                        "Strain-partition result points must be mapping rows."
                    )
                row = dict(point)
                for field in (
                    "side_a_principal_log_strains",
                    "side_b_principal_log_strains",
                ):
                    values = row.get(field)
                    if not isinstance(values, list) or len(values) != 2:
                        raise TypeError(
                            f"Strain-partition result {field} must be a two-value list."
                        )
                    row[field] = tuple(float(value) for value in values)
                row.update(
                    {
                        "run_id": result.run_id_short or self.run.id_short,
                        "followup_id": result.id_short,
                        "prototype_id": result.prototype_id_short,
                        "target_kind": result.target_kind,
                        "target_alpha": target_alpha,
                        "target_metric": target_metric,
                        "target_value": target_value,
                    }
                )
                out.append(row)
        return strain_partition_rows(out)

    def plot(self, *, metric: str | None = None, filename: str | None = None) -> Any:
        # Forward to project plotting facade
        kwargs = {"metric": metric}
        if filename is not None:
            kwargs["filename"] = filename
        return self.project.plot_strain_partition_scan(self.run.id_short, **kwargs)


@dataclass
class RegistrySearchRun(TabularResultMixin):
    _view_specs = REGISTRY_SEARCH_VIEW_SPECS

    project: Any
    run: Any

    def _validated_results(self) -> list[tuple[Any, dict, str]]:
        results = list(
            self.project.followups(
                run=self.run.id_short,
                kind="registry_search",
            )
        )
        out: list[tuple[Any, dict, str]] = []
        from calm.interface.refinement.registry import (
            REGISTRY_PROVENANCE_COMPLETE,
            classify_registry_provenance,
        )

        for result in results:
            payload = dict(result.payload or {})
            registry_result_state(payload)
            provenance_status = classify_registry_provenance(payload.get("provenance"))
            if provenance_status != REGISTRY_PROVENANCE_COMPLETE:
                raise ValueError(
                    "Registry-search result provenance is not exact-current."
                )
            out.append((result, payload, provenance_status))
        return out

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        out: list[dict] = []
        for result, payload, provenance_status in self._validated_results():
            shift, z_padding, vacuum = registry_result_state(payload)
            out.append(
                {
                    "run_id": result.run_id_short or self.run.id_short,
                    "followup_id": result.id_short,
                    "prototype_id": result.prototype_id_short,
                    "target_kind": result.target_kind,
                    "registry_shift_frac_a": list(shift),
                    "z_padding": z_padding,
                    "vacuum": vacuum,
                    "objective": payload["objective"],
                    "objective_units": payload["objective_units"],
                    "score": payload["score"],
                    "n_steps": payload["n_steps"],
                    "n_accepted": payload["n_accepted"],
                    "registry_provenance_status": provenance_status,
                }
            )
        return registry_search_rows(out)

    def trace_rows(self) -> list[dict]:
        """Return detached exact-current proposal rows for every target."""

        out: list[dict] = []
        translation_fields = (
            "translation_increment",
            "proposed_translation",
            "current_translation",
            "best_translation",
        )
        for result, payload, provenance_status in self._validated_results():
            proposals = payload.get("proposal_trace")
            if not isinstance(proposals, list):
                raise TypeError("Registry-search proposal_trace must be a list.")
            for proposal in proposals:
                if not isinstance(proposal, Mapping):
                    raise TypeError(
                        "Registry-search proposal_trace items must be mappings."
                    )
                row = dict(proposal)
                for field in translation_fields:
                    values = row.get(field)
                    if values is None:
                        continue
                    if not isinstance(values, list) or len(values) != 2:
                        raise TypeError(
                            f"Registry-search trace {field} must be a two-value list."
                        )
                    row[field] = tuple(float(value) for value in values)
                row.update(
                    {
                        "run_id": result.run_id_short or self.run.id_short,
                        "followup_id": result.id_short,
                        "prototype_id": result.prototype_id_short,
                        "target_kind": result.target_kind,
                        "objective": payload["objective"],
                        "objective_units": payload["objective_units"],
                        "registry_provenance_status": provenance_status,
                    }
                )
                out.append(row)
        return out

    def write_trace(self, path: str | Path) -> None:
        """Write the full exact-current proposal trace to CSV."""

        _write_rows_csv(
            path,
            self.trace_rows(),
            preferred=[
                "run_id",
                "followup_id",
                "prototype_id",
                "target_kind",
                "step",
                "move_kind",
                "translation_increment",
                "proposed_translation",
                "proposed_score",
                "accepted",
                "current_translation",
                "current_score",
                "best_translation",
                "best_score",
                "temperature",
                "acceptance_uniform",
                "log_acceptance_ratio",
                "objective",
                "objective_units",
                "registry_provenance_status",
            ],
        )

    def plot(self, *, filename: str | None = None) -> Any:
        if filename is None:
            return self.project.plot_registry_search(self.run.id_short)
        return self.project.plot_registry_search(self.run.id_short, filename=filename)


@dataclass
class InterfaceRefinementResult:
    ok: bool
    issues: list[str]
    strain_scan: StrainPartitionScan | None = None
    registry_run: RegistrySearchRun | None = None
    strain_interfaces: list[Any] | None = None
    registry_interfaces: list[Any] | None = None

    def to_rows(self) -> dict:
        return {
            "strain_points": (
                self.strain_scan.to_rows(view="all") if self.strain_scan else []
            ),
            "registry_rows": (
                self.registry_run.to_rows(view="all") if self.registry_run else []
            ),
        }

    def summary(self) -> str:
        lines = [f"Interface refinement: ok={self.ok}"]
        if self.issues:
            lines.append(f" issues={len(self.issues)}: {self.issues}")
        if self.strain_scan:
            try:
                lines.append(f" strain_scan={self.strain_scan.run.id_short}")
            except Exception:
                lines.append(" strain_scan=<unknown>")
        if self.registry_run:
            try:
                lines.append(f" registry_run={self.registry_run.run.id_short}")
            except Exception:
                lines.append(" registry_run=<unknown>")
        if self.strain_interfaces:
            lines.append(f" strain_interfaces={len(self.strain_interfaces)}")
        if self.registry_interfaces:
            lines.append(f" registry_interfaces={len(self.registry_interfaces)}")
        return "\n".join(lines)

    def _owning_project(self) -> Any | None:
        owners = [
            owner
            for wrapper in (self.strain_scan, self.registry_run)
            if (owner := getattr(wrapper, "project", None)) is not None
        ]
        if not owners:
            return None
        first = owners[0]
        if any(owner is not first for owner in owners[1:]):
            raise RuntimeError(
                "Interface refinement result wrappers do not share one owning "
                "Project."
            )
        return first

    def interfaces(self, *, stage: str = "registry_refined"):
        from calm.public.collections.interfaces import InterfaceCollection

        project = self._owning_project()
        if stage == "strain_partitioned":
            return InterfaceCollection(
                project=project,
                interfaces=list(self.strain_interfaces or []),
            )
        if stage == "registry_refined":
            return InterfaceCollection(
                project=project,
                interfaces=list(self.registry_interfaces or []),
            )
        raise ValueError("stage must be 'strain_partitioned' or 'registry_refined'")

    def write_outputs(  # noqa: C901
        self,
        out_dir: str | Path,
        *,
        filename_prefix: str = "",
        plots: tuple[str, ...] | None = None,
        reporter: Any | None = None,
    ) -> dict[str, Path]:
        from calm.public.presentation.reporting import ensure_console_reporter

        rep = ensure_console_reporter(reporter)

        prefix = str(filename_prefix)
        if "\x00" in prefix or "/" in prefix or "\\" in prefix:
            raise ValueError(
                "filename_prefix must be a filename prefix, not a path."
            )

        od = Path(out_dir)
        od.mkdir(parents=True, exist_ok=True)

        def output_path(filename: str) -> Path:
            return od / f"{prefix}{filename}"

        out: dict[str, Path] = {}
        # tables
        if self.strain_scan:
            strain_path = output_path("strain_partition_results.csv")
            self.strain_scan.write_table(strain_path)
            out["strain_table"] = strain_path
        if self.registry_run:
            reg_path = output_path("registry_search_results.csv")
            self.registry_run.write_table(reg_path)
            out["registry_table"] = reg_path
            trace_path = output_path("registry_search_trace.csv")
            self.registry_run.write_trace(trace_path)
            out["registry_trace"] = trace_path
        # Persisted interfaces from both refinement stages export the shared
        # construction schema plus the explicit composed-strain diagnostics.
        for (
            key,
            filename,
            strain_key,
            strain_filename,
            stage,
            interfaces,
        ) in (
            (
                "strain_interfaces",
                "strain_partitioned_interfaces.csv",
                "strain_interface_strain",
                "strain_partitioned_interface_strain.csv",
                "strain_partitioned",
                self.strain_interfaces,
            ),
            (
                "registry_interfaces",
                "registry_refined_interfaces.csv",
                "registry_interface_strain",
                "registry_refined_interface_strain.csv",
                "registry_refined",
                self.registry_interfaces,
            ),
        ):
            if not interfaces:
                continue
            collection = self.interfaces(stage=stage)
            iface_path = output_path(filename)
            collection.write_table(iface_path, view="construction")
            out[key] = iface_path

            strain_path = output_path(strain_filename)
            collection.write_table(strain_path, view="strain")
            out[strain_key] = strain_path

        # plots: None -> defaults, () -> no plots
        if plots is None:
            # Default plotting set for refinement outputs: prefer potential energy density
            # by default; interfacial_energy may be expensive to compute or require
            # optional calculator providers and therefore is not guaranteed.
            plots_to_try = ("potential_energy_density_eV_per_A2",)
        else:
            plots_to_try = tuple(plots)

        if self.strain_scan and plots_to_try:
            for m in plots_to_try:
                try:
                    fname = output_path(f"strain_partition_{m}.png")
                    self.strain_scan.plot(metric=m, filename=fname)
                    out[f"plot_{m}"] = fname
                except Exception as e:
                    # Record failure in issues but continue
                    self.issues.append(f"plot_failed_{m}:{e}")

        # Report written outputs to reporter (best-effort)
        try:
            if out:
                with rep.stage("write_refinement_outputs", out_dir=str(od)):
                    try:
                        rep.mapping(
                            {k: str(v) for k, v in out.items()},
                            title="Refinement outputs",
                        )
                    except Exception:
                        for k, p in out.items():
                            rep.info(f"{k}: {p}")
        except Exception:
            pass

        return out

    # End of followups wrappers


@dataclass(frozen=True)
class RelaxationWorkflowResult(TabularResultMixin):
    """Composite result of one authoritative structural-relaxation run."""

    _view_specs = RELAXATION_RESULT_VIEW_SPECS

    run: Any
    results: Any
    relaxed_interfaces: Any

    @property
    def ok(self) -> bool:  # noqa: C901
        records = list(self.results.records())
        return bool(records) and all(record.succeeded for record in records)

    @property
    def failures(self):
        return self.results.failures()

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        rows = [dict(row) for row in self.results.to_rows(view="all")]
        run_uid = getattr(self.run, "uid_full", None)
        run_id = getattr(self.run, "id_short", None)
        for row in rows:
            row.setdefault("run_uid_full", run_uid)
            row.setdefault("run_id_short", run_id)
        return rows

    def summary(self) -> str:
        records = list(self.results.records())
        n_completed = sum(
            bool(getattr(record, "succeeded", False)) for record in records
        )
        n_failed = sum(
            getattr(record, "failure", None) is not None for record in records
        )
        run_id = getattr(self.run, "id_short", None) or getattr(
            self.run, "uid_full", None
        )
        return "\n".join(
            [
                f"Structural relaxation run: {run_id}",
                f"  status: {getattr(self.run, 'status', None)}",
                f"  completed targets: {n_completed}",
                f"  failed targets: {n_failed}",
                f"  relaxed interfaces: {len(self.relaxed_interfaces)}",
            ]
        )


@dataclass(frozen=True)
class ReferenceEnergyWorkflowResult(TabularResultMixin):
    """Composite result for one authoritative reference-energy run.

    The result retains one pair of reference calculations per authoritative
    source interface and can provide the target-indexed payload required by the
    thermodynamic derivation workflow.
    """

    _view_specs = REFERENCE_ENERGY_RESULT_VIEW_SPECS

    run: Any
    results: Any
    convention: Any

    @property
    def ok(self) -> bool:
        records = list(self.results.records())
        if not records or not all(record.succeeded for record in records):
            return False
        try:
            self.reference_map()
        except (KeyError, RuntimeError, ValueError):
            return False
        return True

    @property
    def failures(self):
        return self.results.failures() if hasattr(self.results, "failures") else []

    @staticmethod
    def _interface_identifier(interface: Any) -> str:
        value = (
            getattr(interface, "uid_full", None)
            or getattr(interface, "id_short", None)
            or interface
        )
        return str(value)

    def _completed_by_interface(self) -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for record in self.results.completed().records():
            target_uid = str(record.target_uid_full or "")
            if not target_uid:
                continue
            bucket = grouped.setdefault(target_uid, {})
            if record.reference_kind in bucket:
                raise RuntimeError(
                    f"Reference run contains duplicate {record.reference_kind!r} "
                    f"results for interface {target_uid!r}."
                )
            bucket[record.reference_kind] = record
        return grouped

    @staticmethod
    def _common_calculator_provenance(  # noqa: C901
        records: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return one verified calculator provenance shared by a reference pair."""

        ordered = [record for _kind, record in sorted(records.items())]
        if not ordered:
            raise RuntimeError(
                "Reference-energy provenance requires at least one record."
            )
        first = ordered[0]
        backend = first.backend
        identity = dict(first.backend_identity)
        relaxation_engine = identity.pop(
            "reference_relaxation_engine",
            None,
        )
        settings = dict(first.settings)
        formula_id = str(first.formula_id or "")
        first_payload = dict(first.payload or {})
        first_reference = dict(first_payload["reference"])
        first_metadata = dict(first_reference["metadata"])
        first_relaxation = first_payload.get("relaxation")
        reference_protocol = first_metadata.get("reference_protocol")
        reference_relaxation = (
            dict(first_relaxation["settings"])
            if isinstance(first_relaxation, Mapping)
            else None
        )
        source_structure_fingerprint = first_metadata.get(
            "source_interface_structure_fingerprint"
        )
        first_area = _positive_reference_area(first_metadata.get("reference_area_A2"))
        if not backend or not identity or not formula_id:
            raise RuntimeError(
                "Calculated reference results are missing authoritative calculator "
                "or formula provenance."
            )
        for record in ordered[1:]:
            if record.backend != backend:
                raise RuntimeError(
                    "Reference-energy pair was evaluated with different backends."
                )
            record_identity = dict(record.backend_identity)
            record_relaxation_engine = record_identity.pop(
                "reference_relaxation_engine",
                None,
            )
            if record_identity != identity:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent calculator identity."
                )
            if record_relaxation_engine != relaxation_engine:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent relaxation-engine "
                    "provenance."
                )
            if dict(record.settings) != settings:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent calculation settings."
                )
            if str(record.formula_id or "") != formula_id:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent thermodynamic formulas."
                )
            payload = dict(record.payload or {})
            reference = dict(payload["reference"])
            metadata = dict(reference["metadata"])
            relaxation = payload.get("relaxation")
            if metadata.get("reference_protocol") != reference_protocol:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent reference protocols."
                )
            if (
                dict(relaxation["settings"])
                if isinstance(relaxation, Mapping)
                else None
            ) != reference_relaxation:
                raise RuntimeError(
                    "Reference-energy pair has inconsistent relaxation settings."
                )
            if (
                metadata.get("source_interface_structure_fingerprint")
                != source_structure_fingerprint
            ):
                raise RuntimeError(
                    "Reference-energy pair was not cleaved from one source interface."
                )
            area = _positive_reference_area(metadata.get("reference_area_A2"))
            if not isclose(
                area,
                first_area,
                rel_tol=1e-10,
                abs_tol=1e-10,
            ):
                raise RuntimeError(
                    "Reference-energy pair has inconsistent interface areas."
                )
        provenance = {
            "compatibility_source": "calculated_reference_workflow",
            "energy_backend": backend,
            "backend_identity": identity,
            "energy_settings": settings,
            "formula_id": formula_id,
            "reference_area_A2": first_area,
        }
        if formula_id == "work_of_adhesion_relaxed_surfaces":
            if not reference_protocol or not isinstance(
                reference_relaxation,
                Mapping,
            ):
                raise RuntimeError(
                    "Relaxed surface references are missing protocol provenance."
                )
            for record in ordered:
                payload = dict(record.payload or {})
                relaxation = payload.get("relaxation")
                if not isinstance(relaxation, Mapping):
                    raise RuntimeError(
                        "Relaxed surface reference is missing relaxation provenance."
                    )
                summary = relaxation.get("summary")
                if not isinstance(summary, Mapping) or not bool(
                    summary.get("converged")
                ):
                    raise RuntimeError(
                        "Relaxed surface reference is missing a convergence certificate."
                    )
                if not relaxation.get("final_structure_fingerprint"):
                    raise RuntimeError(
                        "Relaxed surface reference is missing its final structure "
                        "fingerprint."
                    )
            if not isinstance(relaxation_engine, Mapping):
                raise RuntimeError(
                    "Relaxed surface references are missing relaxation-engine "
                    "provenance."
                )
            provenance.update(
                {
                    "reference_protocol": str(reference_protocol),
                    "reference_relaxation": dict(reference_relaxation),
                    "reference_relaxation_engine": dict(relaxation_engine),
                    "source_interface_structure_fingerprint": (
                        source_structure_fingerprint
                    ),
                }
            )
        return provenance

    def references_for(self, interface: Any):  # noqa: C901
        """Return validated scalar references for one authoritative interface."""
        from calm.public.inputs.settings import ReferenceEnergySettings

        identifier = self._interface_identifier(interface)
        grouped = self._completed_by_interface()
        if identifier not in grouped:
            matching_records = [
                record
                for record in self.results.records()
                if str(record.target_uid_full or "") == identifier
            ]
            failures = [
                record.failure.message
                for record in matching_records
                if record.failure is not None
            ]
            if matching_records:
                detail = "; ".join(failures) or "no completed reference pair"
                raise RuntimeError(
                    f"Interface {identifier!r} has no complete reference-energy pair: "
                    f"{detail}."
                )
            raise KeyError(
                f"No reference-energy results match interface {identifier!r}."
            )
        records = grouped[identifier]
        formula = str(self.convention.formula)
        metadata = {
            "reference_run_uid_full": getattr(self.run, "uid_full", None),
            "reference_result_uids": {
                kind: record.uid_full for kind, record in sorted(records.items())
            },
            "source": "calm.reference_energy.v3",
            **self._common_calculator_provenance(records),
        }
        if formula == "interface_excess_strained_bulk":
            required = ("strained_bulk_a", "strained_bulk_b")
            missing = [kind for kind in required if kind not in records]
            if missing:
                raise RuntimeError(
                    f"Interface {identifier!r} is missing reference results: {missing}."
                )
            a = records[required[0]]
            b = records[required[1]]
            values = ReferenceEnergySettings(
                bulk_a_eV_per_formula_unit=a.energy_eV_per_formula_unit,
                bulk_b_eV_per_formula_unit=b.energy_eV_per_formula_unit,
                n_formula_units_a=a.interface_formula_units,
                n_formula_units_b=b.interface_formula_units,
                metadata=metadata,
            )
        elif formula in {
            "work_of_separation_unrelaxed_surfaces",
            "work_of_adhesion_relaxed_surfaces",
        }:
            required = (
                ("isolated_surface_a", "isolated_surface_b")
                if formula == "work_of_separation_unrelaxed_surfaces"
                else ("relaxed_surface_a", "relaxed_surface_b")
            )
            missing = [kind for kind in required if kind not in records]
            if missing:
                raise RuntimeError(
                    f"Interface {identifier!r} is missing reference results: {missing}."
                )
            values = ReferenceEnergySettings(
                surface_a_total_energy_eV=records[required[0]].energy_eV,
                surface_b_total_energy_eV=records[required[1]].energy_eV,
                metadata=metadata,
            )
        else:
            raise ValueError(f"Unsupported reference formula: {formula!r}.")
        values.validate_for(self.convention)
        return values

    def reference_map(self) -> dict[str, Any]:
        """Return one ``ReferenceEnergySettings`` value per interface."""
        interface_uids = sorted(
            {
                str(record.target_uid_full)
                for record in self.results.records()
                if record.target_uid_full
            }
        )
        if not interface_uids:
            raise RuntimeError("Reference-energy run contains no interface results.")
        return {
            interface_uid: self.references_for(interface_uid)
            for interface_uid in interface_uids
        }

    def to_thermodynamic_payload(self) -> dict[str, Any]:
        """Return the persisted target-indexed reference payload."""
        values = self.reference_map()
        return {
            "mode": "by_target_uid",
            "reference_run_uid_full": getattr(self.run, "uid_full", None),
            "formula_id": str(self.convention.formula),
            "by_target_uid": {
                uid: settings.to_dict() for uid, settings in values.items()
            },
        }

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        del view
        rows = [dict(row) for row in self.results.to_rows(view="all")]
        for row in rows:
            row.setdefault("run_uid_full", getattr(self.run, "uid_full", None))
            row.setdefault("run_id_short", getattr(self.run, "id_short", None))
        return rows

    def summary(self) -> str:
        records = list(self.results.records())
        interfaces = {
            str(record.target_uid_full) for record in records if record.target_uid_full
        }
        run_id = getattr(self.run, "id_short", None) or getattr(
            self.run, "uid_full", None
        )
        return "\n".join(
            [
                f"Reference energy run: {run_id}",
                f"  status: {getattr(self.run, 'status', None)}",
                f"  formula: {self.convention.formula}",
                f"  source interfaces: {len(interfaces)}",
                f"  completed references: {sum(record.succeeded for record in records)}",
                f"  failed references: {sum(record.failure is not None for record in records)}",
            ]
        )


@dataclass(frozen=True)
class EnergyWorkflowResult:
    """Composite result for raw energy evaluation and optional derivation."""

    _view_specs = RAW_ENERGY_RESULT_VIEW_SPECS

    energy_run: Any
    energy_results: Any
    thermodynamic_run: Any | None = None
    thermodynamic_results: Any | None = None

    @property
    def ok(self) -> bool:  # noqa: C901
        raw = list(self.energy_results.records())
        if not raw or not all(getattr(record, "succeeded", False) for record in raw):
            return False
        if self.thermodynamic_results is None:
            return True
        derived = list(self.thermodynamic_results.records())
        return bool(derived) and all(
            getattr(record, "succeeded", False) for record in derived
        )

    @property
    def failures(self):
        failures = list(self.energy_results.failures().records())
        if self.thermodynamic_results is not None:
            failures.extend(self.thermodynamic_results.failures().records())
        return failures

    @staticmethod
    def _validate_kind(kind: str) -> str:
        if kind not in {"raw", "thermodynamic", "all"}:
            raise ValueError("kind must be 'raw', 'thermodynamic', or 'all'.")
        return kind

    @staticmethod
    def _view_specs_for_kind(kind: str):
        if kind == "raw":
            return RAW_ENERGY_RESULT_VIEW_SPECS
        if kind == "thermodynamic":
            return THERMODYNAMIC_RESULT_VIEW_SPECS
        return ENERGY_WORKFLOW_COMBINED_VIEW_SPECS

    @classmethod
    def available_views(cls, *, kind: str = "raw") -> tuple[str, ...]:
        """Return the canonical named views supported for one result kind."""

        canonical = cls._validate_kind(kind)
        return tuple(spec.name for spec in cls._view_specs_for_kind(canonical))

    def _rows_for_kind(self, kind: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if kind in {"raw", "all"}:
            for value in self.energy_results.to_rows(view="all"):
                row = dict(value)
                row["result_kind"] = "raw_energy"
                row.setdefault(
                    "run_uid_full", getattr(self.energy_run, "uid_full", None)
                )
                row.setdefault(
                    "run_id_short", getattr(self.energy_run, "id_short", None)
                )
                rows.append(row)

        if kind in {"thermodynamic", "all"} and self.thermodynamic_results is not None:
            for value in self.thermodynamic_results.to_rows(view="all"):
                row = dict(value)
                row["result_kind"] = "thermodynamic_quantity"
                row.setdefault(
                    "run_uid_full",
                    getattr(self.thermodynamic_run, "uid_full", None),
                )
                row.setdefault(
                    "run_id_short",
                    getattr(self.thermodynamic_run, "id_short", None),
                )
                rows.append(row)
        return rows

    def _resolve_projection(
        self,
        *,
        kind: str,
        view: str,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ):
        canonical = self._validate_kind(kind)
        return resolve_named_projection(
            self._view_specs_for_kind(canonical),
            self._rows_for_kind(canonical),
            view=view,
            include=include,
            exclude=exclude,
        )

    def to_rows(
        self,
        *,
        kind: str = "raw",
        view: str = "summary",
    ) -> list[dict]:
        """Return raw, thermodynamic, or combined energy-result rows."""
        return self._resolve_projection(kind=kind, view=view).to_rows()

    def to_table(
        self,
        *,
        kind: str = "raw",
        view: str = "summary",
        title: str = "Energy results",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ):
        """Return one deferred table for raw, derived, or combined results."""

        projection = self._resolve_projection(
            kind=kind,
            view=view,
            include=include,
            exclude=exclude,
        )
        return projection_table(
            projection,
            title=title,
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(
        self,
        *,
        kind: str = "raw",
        view: str = "summary",
    ):
        """Return one dataframe using the same resolved result schema."""

        return projection_dataframe(self._resolve_projection(kind=kind, view=view))

    def write_table(
        self,
        path: str | Path,
        *,
        kind: str = "raw",
        view: str = "summary",
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        write_projection_csv(
            path,
            self._resolve_projection(
                kind=kind,
                view=view,
                include=include,
                exclude=exclude,
            ),
        )

    def summary(self) -> str:
        raw = list(self.energy_results.records())
        derived = (
            list(self.thermodynamic_results.records())
            if self.thermodynamic_results is not None
            else []
        )
        energy_run_id = getattr(self.energy_run, "id_short", None) or getattr(
            self.energy_run, "uid_full", None
        )
        thermo_run_id = None
        if self.thermodynamic_run is not None:
            thermo_run_id = getattr(
                self.thermodynamic_run, "id_short", None
            ) or getattr(self.thermodynamic_run, "uid_full", None)
        lines = [
            f"Raw energy run: {energy_run_id}",
            f"  status: {getattr(self.energy_run, 'status', None)}",
            f"  completed targets: {sum(record.succeeded for record in raw)}",
            f"  failed targets: {sum(record.failure is not None for record in raw)}",
        ]
        if self.thermodynamic_run is not None:
            lines.extend(
                [
                    f"Thermodynamic derivation run: {thermo_run_id}",
                    f"  status: {getattr(self.thermodynamic_run, 'status', None)}",
                    f"  derived quantities: {sum(record.succeeded for record in derived)}",
                ]
            )
        return "\n".join(lines)
