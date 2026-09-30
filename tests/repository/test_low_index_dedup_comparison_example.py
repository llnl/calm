from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np

from benchmarks.benchmarks.claims.dedup_comparison import LedgerEntry


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPOSITORY_ROOT / "examples" / "lif_li2o_low_index_dedup_comparison.py"
README = REPOSITORY_ROOT / "examples" / "README.md"


def _load_script():
    spec = importlib.util.spec_from_file_location("low_index_dedup_comparison", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assignment(search: str, entry: str, method: str, class_id: str) -> dict:
    return {
        "search_name": search,
        "entry_id": entry,
        "method_id": method,
        "class_id": class_id,
    }


def test_low_index_comparison_declares_nine_stable_searches() -> None:
    module = _load_script()
    names = module.default_search_names("campaign")

    assert len(names) == len(set(names)) == 9
    assert names[0] == "campaign-lif-100-li2o-100"
    assert names[-1] == "campaign-lif-111-li2o-111"


def test_low_index_comparison_reports_relative_merges_and_splits() -> None:
    module = _load_script()
    assignments = []
    fixtures = {
        "e1": ("c1", "h1"),
        "e2": ("c2", "h1"),
        "e3": ("c3", "h2"),
        "e4": ("c3", "h3"),
    }
    comparison_methods = (
        "zur_mcgill_descriptor",
        "interoptimus_greedy",
        "ogre_style",
    )
    for entry, (calm_class, comparison_class) in fixtures.items():
        assignments.append(_assignment("search", entry, "calm_final", calm_class))
        for method in comparison_methods:
            assignments.append(
                _assignment("search", entry, method, comparison_class)
            )

    merges, splits = module.build_relative_split_merge_diagnostics(assignments)

    assert {row["comparison_method"] for row in merges} == set(comparison_methods)
    assert {row["comparison_method"] for row in splits} == set(comparison_methods)
    assert all(row["reference_class_count"] == 2 for row in merges)
    assert all(row["comparison_class_count"] == 2 for row in splits)


def test_low_index_comparison_integrates_typed_adapter_protocols() -> None:
    module = _load_script()
    rows = []
    entries = []
    for index, scale in enumerate((1, 2)):
        block = scale * np.eye(2, dtype=int)
        source = np.vstack((block, block))
        basis = block.astype(float)
        record = {
            "entry_id": f"search:{index:08d}",
            "record_id": f"search:{index:08d}",
            "source_pair_matrix": source.tolist(),
            "source_basis_A": basis.tolist(),
            "source_basis_B": basis.tolist(),
            "source_gram_A": (basis.T @ basis).tolist(),
            "source_gram_B": (basis.T @ basis).tolist(),
            "principal_log_strains": [0.0, 0.0],
            "d_cell": 0.0,
            "atom_count": 2,
            "source_atom_count": 2 * scale * scale,
        }
        rows.append(record)
        entries.append(LedgerEntry.from_record(record))
    identity = (np.eye(2, dtype=int),)
    context = {
        "pair_symmetry": "full",
        "correspondence_orientation": "proper",
        "identify_material_exchange": False,
        "pair_key_version": 1,
    }
    ledger = module.SearchLedger(
        name="search",
        search_uid=None,
        surface_a_uid="surface:a",
        surface_b_uid="surface:b",
        settings={},
        point_group_a=identity,
        point_group_b=identity,
        surface_symmetry_a={},
        surface_symmetry_b={},
        trace_context=context,
        records=tuple(rows),
        entries=tuple(entries),
        final_class_count=1,
        persisted_candidate_count=1,
        audit_admitted_count=None,
        audit_identity_reduction=None,
        persisted_pair_keys=((1, 0, 0, 1, 1, 0, 0, 1),),
        rerun_pair_keys=((1, 0, 0, 1, 1, 0, 0, 1),),
    )

    assignments, filters, selectors, summaries, method_runs = (
        module.classify_ledger(
            ledger,
            elastic_energy_by_id=None,
            elastic_energy_provenance=None,
        )
    )

    assert len(assignments) == 14
    assert len(filters) == 2
    assert {row["method_id"] for row in selectors} == {
        "intermat_source",
        "intermat_paper_style",
        "intermatch_style",
    }
    status = {row["method_id"]: row["status"] for row in selectors}
    assert status["intermat_source"] == "not_applicable"
    assert status["intermat_paper_style"] == "selected"
    assert status["intermatch_style"] == "not_applicable"
    calm_final = next(
        row for row in summaries if row["method_id"] == "calm_final"
    )
    assert calm_final["output_count"] == 1
    by_method = {row["method_id"]: row for row in method_runs}
    assert set(by_method) == set(module.USED_METHODS)
    assert len(
        by_method["zur_mcgill_descriptor"]["outcome"]["record_outcomes"]
    ) == 2
    interoptimus = by_method["interoptimus_greedy"]["outcome"]
    assert interoptimus["representative_by_class_id"]
    assert interoptimus["members_by_class_id"]

    provenance = {
        "sha256": "a" * 64,
        "units": "eV",
        "strained_side": "A",
    }
    with_energy = module.classify_ledger(
        ledger,
        elastic_energy_by_id={
            "search:00000000": 0.25,
            "search:00000001": 0.50,
        },
        elastic_energy_provenance=provenance,
    )
    energy_run = next(
        row for row in with_energy[4] if row["method_id"] == "intermatch_style"
    )
    assert energy_run["parameters"]["elastic_energy_input"] == provenance
    assert energy_run["outcome"]["status"] == "selected"


def test_low_index_comparison_validates_exact_persisted_pair_identities() -> None:
    module = _load_script()
    policy = {
        "pair_key_version": 1,
        "pair_symmetry": "full",
        "correspondence_orientation": "proper",
        "identify_material_exchange": False,
    }
    pair_key = [1, 0, 0, 1, 1, 0, 0, 1]

    class Candidates:
        def to_rows(self, *, view: str):
            assert view == "all"
            return [
                {
                    "pair_identity": {
                        "key_version": 1,
                        "primitive_pair_key": pair_key,
                        "pair_symmetry_policy": "full",
                        "correspondence_orientation": "proper",
                        "material_exchange_identified": False,
                    }
                }
            ]

    class Search:
        name = "search"

        @staticmethod
        def candidates():
            return Candidates()

    keys = module._persisted_pair_keys(Search(), expected_policy=policy)

    assert keys == (tuple(pair_key),)
    canonical = b"[[1,0,0,1,1,0,0,1]]"
    assert module._value_sha256(sorted(keys)) == hashlib.sha256(canonical).hexdigest()


def test_low_index_comparison_hashes_and_describes_elastic_input(
    tmp_path: Path,
) -> None:
    module = _load_script()
    path = tmp_path / "elastic.csv"
    payload = "entry_id,elastic_energy\nsearch:00000000,0.25\n"
    path.write_text(payload, encoding="utf-8")

    energies, provenance = module._load_elastic_energy_input(
        path,
        units="eV",
        normalization="per source supercell",
        strained_side="A",
        thickness_convention="3.45 angstrom effective thickness",
    )

    assert energies == {"search:00000000": 0.25}
    assert provenance is not None
    assert provenance["sha256"] == hashlib.sha256(payload.encode()).hexdigest()
    assert provenance["units"] == "eV"
    assert provenance["normalization"] == "per source supercell"
    assert provenance["strained_side"] == "A"
    assert provenance["thickness_convention"].startswith("3.45")


def test_low_index_comparison_requires_complete_elastic_semantics() -> None:
    module = _load_script()

    try:
        module._parse_args(
            ["--intermatch-elastic-energies", "elastic.csv"]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("partial InterMatch energy semantics were accepted")


def test_low_index_comparison_keeps_method_result_types_distinct() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    prose = " ".join(readme.split())

    assert "_capture_coupled_match_trace" in source
    assert "exact_equivalence_class" in source
    assert "heuristic_cluster" in source
    assert "generation_filter" in source
    assert "selection_policy" in source
    assert "native_parity\": False" in source
    assert "method-run-diagnostics.jsonl" in source
    assert "persisted_pair_key_set_equals_rerun" in source
    assert "must not all be described as numbers of unique matches" in prose
    assert "does not contain native JARVIS traversal ranks" in prose


def test_low_index_comparison_help_does_not_require_a_project() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--project-dir" in completed.stdout
    assert "--intermatch-elastic-energies" in completed.stdout
    assert "--intermatch-energy-units" in completed.stdout
    assert "--intermatch-energy-normalization" in completed.stdout
    assert "--intermatch-strained-side" in completed.stdout
    assert "--intermatch-thickness-convention" in completed.stdout
