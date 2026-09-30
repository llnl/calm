from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from calm.public.collections.datasets import DatasetCollection
from calm.public.records.dataset_learning import (
    DatasetMLReadinessError,
    validate_ml_readiness,
)
from calm.public.records.datasets import (
    export_persisted_dataset,
    normalize_authoritative_dataset_source,
    validate_persisted_dataset,
)
from calm.public.collections.persistence import DatasetItemCollection
from calm.public.records.persistence import (
    ProjectDataset,
    ProjectDatasetItem,
    ProjectEnergyResult,
    ProjectInterface,
    ProjectRelaxationResult,
    ProjectThermodynamicResult,
    RecordAuthority,
)
from calm.public.inputs.settings import (
    DatasetFeature,
    DatasetSettings,
    DatasetSplitSettings,
    DatasetTarget,
)


def _settings(*, seed: int = 7) -> DatasetSettings:
    return DatasetSettings(
        schema_version="calm.interface_learning.v1",
        duplicate_policy="skip",
        features=(
            DatasetFeature(
                "area_A2",
                "thermodynamic.normalization_area_A2",
                units="angstrom^2",
            ),
            DatasetFeature("relax_steps", "relaxation.n_steps", dtype="int"),
            DatasetFeature(
                "max_force_eV_per_A",
                "relaxation.max_force_eV_per_A",
                units="eV/angstrom",
            ),
        ),
        targets=(
            DatasetTarget(
                "interface_energy_J_per_m2",
                "thermodynamic.value_J_per_m2",
                units="J/m^2",
            ),
        ),
        group_by=("lineage.prototype",),
        split=DatasetSplitSettings(seed=seed),
    )


def _records(*, suffix: str = "1"):
    interface = ProjectInterface(
        uid_full=f"interface:relaxed:{suffix}",
        id_short=f"i_relax{suffix}",
        label=f"relaxed-{suffix}",
        prototype_uid_full="proto:shared",
        stage="relaxed",
        metadata={
            "search_name": "learning_search",
            "source_followup_uid": f"followup:relax:{suffix}",
            "area_A2": 12.5,
        },
        authority=RecordAuthority.AUTHORITATIVE,
    )
    relaxation = ProjectRelaxationResult(
        uid_full=f"followup:relax:{suffix}",
        id_short=f"f_relax{suffix}",
        status="done",
        run_uid_full=f"run:relax:{suffix}",
        run_id_short=f"r_relax{suffix}",
        prototype_uid_full="proto:shared",
        target_uid_full=f"interface:refined:{suffix}",
        target_kind="interface",
        relaxed_interface_uid=interface.uid_full,
        final_energy_eV=-10.0,
        n_steps=8,
        converged=True,
        max_force_eV_per_A=0.02,
        backend="real",
        optimizer_reported_converged=True,
        residual_satisfied=True,
        max_optimizer_residual=0.02,
        termination_reason="converged",
        backend_identity={
            "name": "real",
            "scientific_authority": "calculator_backed",
        },
        settings={"fmax": 0.05},
        artifact_refs=(f"artifact:relax:{suffix}",),
        authority=RecordAuthority.AUTHORITATIVE,
    )
    raw = ProjectEnergyResult(
        uid_full=f"followup:raw:{suffix}",
        id_short=f"f_raw{suffix}",
        status="done",
        run_uid_full=f"run:raw:{suffix}",
        run_id_short=f"r_raw{suffix}",
        prototype_uid_full="proto:shared",
        target_uid_full=interface.uid_full,
        target_kind="interface",
        quantity="total_energy",
        energy_eV=-9.5,
        backend="real",
        backend_identity={
            "name": "real",
            "scientific_authority": "calculator_backed",
        },
        settings={"mode": "single_point"},
        artifact_refs=(f"artifact:raw:{suffix}",),
        authority=RecordAuthority.AUTHORITATIVE,
    )
    thermo = ProjectThermodynamicResult(
        uid_full=f"followup:thermo:{suffix}",
        id_short=f"f_thermo{suffix}",
        status="done",
        run_uid_full=f"run:thermo:{suffix}",
        run_id_short=f"r_thermo{suffix}",
        prototype_uid_full="proto:shared",
        target_uid_full=interface.uid_full,
        target_kind="interface",
        raw_energy_followup_uid=raw.uid_full,
        quantity="interface_excess_energy",
        formula_id="interface_excess_strained_bulk",
        value_eV_per_A2=0.25,
        value_J_per_m2=4.005441585,
        normalization_area_A2=12.5,
        n_interfaces=2,
        convention={"formula": "interface_excess_strained_bulk"},
        references={"bulk_a": -1.0, "bulk_b": -2.0},
        reference_source={"mode": "calculated"},
        units={
            "primary": "eV/angstrom^2",
            "secondary": "J/m^2",
        },
        calculator_compatibility={
            "status": "verified",
            "raw": {
                "backend": "real",
                "identity": {
                    "name": "real",
                    "scientific_authority": "calculator_backed",
                },
                "settings": {"mode": "single_point"},
                "interface_area_A2": 12.5,
            },
            "reference": {
                "backend": "real",
                "identity": {
                    "name": "real",
                    "scientific_authority": "calculator_backed",
                },
                "settings": {"mode": "single_point"},
                "interface_area_A2": 12.5,
                "relaxation": None,
            },
        },
        authority=RecordAuthority.AUTHORITATIVE,
    )
    return interface, relaxation, raw, thermo


class _Repo:
    def __init__(self, project):
        self._project = project

    def resolve_identifier(self, identifier):
        return identifier

    def list_edges(self, **kwargs):
        del kwargs
        return [SimpleNamespace()]

    def list_dataset_items(self, identifier):
        del identifier
        return list(self._project.dataset_item_rows)


class _Project:
    def __init__(self, records):
        self.interface_record, self.relaxation, self.raw, self.thermo = records
        self.dataset_item_rows = []
        self._repo = _Repo(self)
        self._structure_queries = SimpleNamespace(
            get_interface_atoms=self._load_interface_atoms
        )

    def energy_result(self, identifier):
        assert identifier == self.raw.uid_full
        return self.raw

    def interface(self, identifier):
        assert identifier == self.interface_record.uid_full
        return self.interface_record

    def relaxation_result(self, identifier):
        assert identifier == self.relaxation.uid_full
        return self.relaxation

    def relaxation_results(self, **kwargs):
        del kwargs
        return [self.relaxation]

    def edges(self, **kwargs):
        del kwargs
        return [SimpleNamespace(src_uid_full=self.relaxation.uid_full)]

    def _load_interface_atoms(self, identifier):
        assert identifier == self.interface_record.uid_full
        return [object(), object()]

    def dataset_items(self, identifier):
        del identifier
        return DatasetItemCollection(self.dataset_item_rows)

    def export_dataset(self, identifier, destination, **kwargs):
        del identifier
        return export_persisted_dataset(
            self,
            self.dataset_record,
            destination,
            **kwargs,
        )


def _dataset(project: _Project, rows: list[dict], *, settings=None) -> ProjectDataset:
    project.dataset_item_rows = [
        ProjectDatasetItem(
            uid_full=f"dataset_item:{index}",
            id_short=f"di_{index}",
            dataset_uid_full="dataset:learning",
            index=index,
            metadata=row,
            authority=RecordAuthority.AUTHORITATIVE,
        )
        for index, row in enumerate(rows)
    ]
    selected = settings or _settings()
    dataset = ProjectDataset(
        uid_full="dataset:learning",
        id_short="d_learning",
        name="learning",
        metadata={
            "schema_version": selected.schema,
            "settings": selected.to_dict(),
        },
        authority=RecordAuthority.AUTHORITATIVE,
        _project=project,
    )
    project.dataset_record = dataset
    return dataset


def test_learning_settings_are_typed_identity_bearing_and_legacy_safe() -> None:
    legacy = DatasetSettings(schema_version="calm.raw_energy.v1")
    assert legacy.to_dict() == {
        "schema_version": "calm.raw_energy.v1",
        "duplicate_policy": "error",
        "failure_policy": "error",
        "require_complete_provenance": True,
    }

    settings = _settings()
    payload = settings.to_dict()
    assert payload["schema_version"] == "calm.interface_learning.v1"
    assert payload["features"][0]["name"] == "area_A2"
    assert payload["targets"][0]["source"] == "thermodynamic.value_J_per_m2"
    assert payload["group_by"] == ["lineage.prototype"]
    assert payload["split"]["seed"] == 7
    assert payload["split"]["policy_version"] == 2
    assert DatasetSettings(**payload) == settings

    with pytest.raises(ValueError, match="at least one DatasetFeature"):
        DatasetSettings(
            schema_version="calm.interface_learning.v1",
            targets=(DatasetTarget("y", "raw_energy.energy_eV"),),
            group_by=("lineage.prototype",),
            split=DatasetSplitSettings(),
        ).validate()
    with pytest.raises(ValueError, match="sum to 1.0"):
        DatasetSplitSettings(0.7, 0.2, 0.2).validate()
    with pytest.raises(ValueError, match="only supported"):
        DatasetSettings(
            schema_version="calm.raw_energy.v1",
            features=(DatasetFeature("x", "raw_energy.energy_eV"),),
        ).validate()
    with pytest.raises(ValueError, match="rooted at one of"):
        DatasetFeature("x", "payload.energy").validate()
    with pytest.raises(ValueError, match="public lineage alias"):
        DatasetFeature("x", "lineage.prototype_uid_full").validate()
    with pytest.raises(ValueError, match="entries must be unique"):
        replace(
            settings,
            group_by=("lineage.prototype", "lineage.prototype"),
        ).validate()
    with pytest.raises(ValueError, match="does not include failed samples"):
        replace(settings, failure_policy="include").validate()
    with pytest.raises(ValueError, match="require_complete_provenance=True"):
        replace(settings, require_complete_provenance=False).validate()


def test_joined_row_contains_structure_relaxation_energy_and_split_contract() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )

    assert row["schema_version"] == "calm.interface_learning.v1"
    assert row["source_kind"] == "joined_interface_record"
    assert row["interface_uid_full"] == project.interface_record.uid_full
    assert row["relaxation_followup_uid"] == project.relaxation.uid_full
    assert row["raw_energy_followup_uid"] == project.raw.uid_full
    assert row["thermodynamic_followup_uid"] == project.thermo.uid_full
    assert row["features"] == {
        "area_A2": 12.5,
        "relax_steps": 8,
        "max_force_eV_per_A": 0.02,
    }
    assert row["targets"] == {"interface_energy_J_per_m2": 4.005441585}
    assert row["split"] in {"train", "validation", "test"}
    assert row["split_contract_status"] == "complete_v2"
    assert row["split_provenance"]["split"] == row["split"]
    assert row["split_provenance"]["policy_version"] == 2
    assert row["group_by"] == {
        "lineage.prototype": "proto:shared"
    }
    assert row["provenance"]["terminal_source_uid_full"] == project.thermo.uid_full
    assert row["artifact_refs"] == ["artifact:relax:1", "artifact:raw:1"]


def test_group_assignment_is_stable_across_distinct_terminal_results() -> None:
    first_project = _Project(_records(suffix="1"))
    second_project = _Project(_records(suffix="2"))
    settings = _settings(seed=31)
    first = normalize_authoritative_dataset_source(
        first_project,
        first_project.thermo,
        settings=settings,
    )
    second = normalize_authoritative_dataset_source(
        second_project,
        second_project.thermo,
        settings=settings,
    )
    assert first["group_id"] == second["group_id"]
    assert first["split"] == second["split"]
    assert first["source_uid_full"] != second["source_uid_full"]


def test_ml_readiness_and_collection_split_views() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])

    report = dataset.validate_ml()
    assert report.ok
    assert report.n_ready == 1
    assert report.n_features == 3
    assert report.n_targets == 1
    assert report.split_counts[row["split"]] == 1
    assert "ML readiness: ready" in report.summary()

    items = dataset.items()
    assert len(items.split(row["split"])) == 1
    assert len(items.groups()) == 1
    learning = items.to_rows(view="learning")[0]
    assert learning["source_id"] == project.thermo.id_short
    assert learning["interface_id"] == project.interface_record.id_short
    assert "source_uid_full" not in learning
    assert "interface_uid_full" not in learning
    assert learning["feature_area_A2"] == 12.5
    assert learning["target_interface_energy_J_per_m2"] == 4.005441585



def test_authoritative_dataset_collection_writes_item_manifest(tmp_path) -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])
    collection = DatasetCollection(
        datasets=[dataset],
        repo=project._repo,
        project=project,
    )

    manifest = tmp_path / "dataset-items.csv"
    collection.write_manifest(manifest)

    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["dataset_uid_full"] == dataset.uid_full
    assert rows[0]["source_uid_full"] == project.thermo.uid_full
    assert rows[0]["split"] == row["split"]

def test_ml_readiness_rejects_group_leakage_and_missing_targets() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    other_split = next(
        value for value in ("train", "validation", "test") if value != row["split"]
    )
    corrupted = dict(row)
    corrupted["split"] = other_split
    corrupted["targets"] = {}
    dataset = _dataset(project, [row, corrupted])

    report = validate_ml_readiness(project, dataset, check_structures=False)
    assert not report.ok
    assert {issue.code for issue in report.issues} >= {
        "invalid_target",
        "group_leakage",
    }
    with pytest.raises(DatasetMLReadinessError):
        report.raise_for_errors()


def test_learning_declarations_are_exposed_from_persisted_dataset() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])

    assert dataset.feature_declarations[0].name == "area_A2"
    assert dataset.target_declarations[0].name == "interface_energy_J_per_m2"
    assert dataset.grouping_fields == ("lineage.prototype",)
    assert dataset.split_settings.seed == 7
    assert len(dataset.split(row["split"])) == 1


def test_learning_export_records_declarations_and_split_summary(tmp_path) -> None:
    import json

    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])
    exported = dataset.export(
        tmp_path / "learning-export",
        include_structures=False,
    )
    payload = json.loads(exported.manifest_path.read_text(encoding="utf-8"))
    assert payload["feature_declarations"][0]["name"] == "area_A2"
    assert payload["target_declarations"][0]["name"] == "interface_energy_J_per_m2"
    assert payload["group_by"] == ["lineage.prototype"]
    assert payload["split_settings"]["seed"] == 7
    assert payload["split_settings"]["policy_version"] == 2
    assert payload["split_contract"]["policy_version"] == 2
    assert payload["split_contract"]["comparison_policy"] == (
        "exact_u64_ratio_vs_binary64_threshold_ratios"
    )
    assert payload["split_summary"] == {row["split"]: 1}
    assert payload["content_fingerprint"].startswith("dataset_content:")
    assert exported.content_fingerprint == payload["content_fingerprint"]


def test_learning_validation_recomputes_split_and_content_fingerprint() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])

    report = validate_persisted_dataset(project, dataset)
    assert report.ok
    assert report.content_fingerprint is not None
    assert report.content_fingerprint.startswith("dataset_content:")

    corrupted = deepcopy(row)
    corrupted["split"] = next(
        name
        for name in ("train", "validation", "test")
        if name != row["split"]
    )
    invalid = validate_persisted_dataset(project, _dataset(project, [corrupted]))
    assert not invalid.ok
    assert any(
        "deterministic group assignment" in issue.message
        for issue in invalid.issues
    )

    tampered = deepcopy(row)
    tampered["split_provenance"]["hash_prefix_hex"] = "0000000000000000"
    invalid_provenance = validate_persisted_dataset(
        project,
        _dataset(project, [tampered]),
    )
    assert not invalid_provenance.ok
    assert any(
        "split_provenance" in issue.message
        for issue in invalid_provenance.issues
    )


def test_dataset_validation_distinguishes_missing_and_failed_source_resolution() -> None:
    project = _Project(_records())
    row = normalize_authoritative_dataset_source(
        project,
        project.thermo,
        settings=_settings(),
    )
    dataset = _dataset(project, [row])

    project._repo.resolve_identifier = lambda _identifier: (
        (_ for _ in ()).throw(KeyError("source missing"))
    )
    missing = validate_persisted_dataset(project, dataset)
    assert any(issue.code == "missing_source" for issue in missing.issues)
    assert not any(
        issue.code == "source_resolution_failed" for issue in missing.issues
    )

    project._repo.resolve_identifier = lambda _identifier: (
        (_ for _ in ()).throw(RuntimeError("database unavailable"))
    )
    failed = validate_persisted_dataset(project, dataset)
    issue = next(
        issue
        for issue in failed.issues
        if issue.code == "source_resolution_failed"
    )
    assert "RuntimeError" in issue.message
    assert "database unavailable" in issue.message


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda records: (
                records[0],
                records[1],
                replace(
                    records[2],
                    backend_identity={
                        "name": "deterministic",
                        "scientific_authority": "synthetic_test_only",
                    },
                ),
                records[3],
            ),
            "raw-energy sources must be calculator-backed",
        ),
        (
            lambda records: (
                records[0],
                replace(records[1], residual_satisfied=False),
                records[2],
                records[3],
            ),
            "residual_satisfied=True",
        ),
        (
            lambda records: (
                records[0],
                records[1],
                records[2],
                replace(
                    records[3],
                    calculator_compatibility={
                        "status": "manual_unverified",
                        "reference_source": "user",
                    },
                ),
            ),
            "calculator-verified references",
        ),
        (
            lambda records: (
                records[0],
                records[1],
                replace(records[2], prototype_uid_full="proto:other"),
                records[3],
            ),
            "inconsistent or missing prototype identity",
        ),
    ],
)
def test_learning_eligibility_rejects_unverified_scientific_records(
    mutate,
    message: str,
) -> None:
    project = _Project(mutate(_records()))
    with pytest.raises(ValueError, match=message):
        normalize_authoritative_dataset_source(
            project,
            project.thermo,
            settings=_settings(),
        )


def test_thermodynamic_source_requires_raw_energy_lineage() -> None:
    project = _Project(_records())
    orphan = replace(project.thermo, raw_energy_followup_uid=None)

    with pytest.raises(ValueError, match="no authoritative raw-energy source"):
        normalize_authoritative_dataset_source(
            project,
            orphan,
            settings=_settings(),
        )


def test_learning_failure_policy_excludes_before_join_materialization() -> None:
    project = _Project(_records())
    failed = replace(project.thermo, status="failed")

    excluded = normalize_authoritative_dataset_source(
        project,
        failed,
        settings=replace(_settings(), failure_policy="exclude"),
    )
    assert excluded is None

    with pytest.raises(ValueError, match="is failed"):
        normalize_authoritative_dataset_source(
            project,
            failed,
            settings=_settings(),
        )


def test_joined_row_preserves_raw_energy_lookup_failures() -> None:
    project = _Project(_records())

    def fail_lookup(_identifier):
        raise RuntimeError("raw energy repository unavailable")

    project.energy_result = fail_lookup

    with pytest.raises(RuntimeError, match="raw energy repository unavailable"):
        normalize_authoritative_dataset_source(
            project,
            project.thermo,
            settings=_settings(),
        )
