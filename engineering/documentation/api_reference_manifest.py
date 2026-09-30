#!/usr/bin/env python3
"""Generate CALM's compact, user-facing public API reference."""

from __future__ import annotations

from collections import defaultdict
import inspect
import importlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
TABLE_VIEW_CONTRACT = (
    ROOT / "engineering" / "architecture" / "current-public-table-views.json"
)
OUTPUT_ROOT = Path("reference/api")


PROJECT_GROUPS = (
    "project",
    "queries_and_provenance",
    "materials",
    "surfaces",
    "search_and_refinement",
    "relaxation_and_energy",
    "datasets",
    "campaigns",
)

PROJECT_GROUP_TITLES = {
    "project": "Project state and reproducibility",
    "queries_and_provenance": "Queries, artifacts, and lineage",
    "materials": "Materials",
    "surfaces": "Surfaces",
    "search_and_refinement": "Search, construction, and refinement",
    "relaxation_and_energy": "Relaxation and energy",
    "datasets": "Datasets",
    "campaigns": "Campaigns",
}

PROJECT_GROUP_GUIDES = {
    "project": (("Projects", "../../use/projects.md"),),
    "queries_and_provenance": (("Projects", "../../use/projects.md"),),
    "materials": (("Materials", "../../use/materials.md"),),
    "surfaces": (("Surfaces and terminations", "../../use/surfaces.md"),),
    "search_and_refinement": (
        ("Searches and candidates", "../../use/searches.md"),
        ("Build and refine interfaces", "../../use/build-refine.md"),
    ),
    "relaxation_and_energy": (
        ("Relax and evaluate", "../../use/relax-evaluate.md"),
        ("Energy and reference conventions", "../../understand/energetics.md"),
    ),
    "datasets": (("Datasets and campaigns", "../../use/datasets-campaigns.md"),),
    "campaigns": (("Datasets and campaigns", "../../use/datasets-campaigns.md"),),
}

INPUT_GROUPS = (
    ("Structure and calculator inputs", ("Material", "Potential")),
    (
        "Matching, construction, and refinement settings",
        ("SearchSettings", "StrainPartitionSettings", "BuildSettings", "RegistrySettings"),
    ),
    (
        "Relaxation and energy settings",
        ("RelaxSettings", "EnergySettings", "EnergyConvention", "ReferenceEnergySettings"),
    ),
    (
        "Dataset declarations",
        ("DatasetFeature", "DatasetTarget", "DatasetSplitSettings", "DatasetSettings"),
    ),
    ("Campaign declarations", ("CampaignCase", "CampaignSettings")),
)

INPUT_GROUP_GUIDES = {
    "Structure and calculator inputs": (
        ("Materials", "../../use/materials.md"),
        ("Calculator support", "../calculator-support.md"),
    ),
    "Matching, construction, and refinement settings": (
        ("Searches and candidates", "../../use/searches.md"),
        ("Build and refine interfaces", "../../use/build-refine.md"),
    ),
    "Relaxation and energy settings": (
        ("Relax and evaluate", "../../use/relax-evaluate.md"),
        ("Energy and reference conventions", "../../understand/energetics.md"),
    ),
    "Dataset declarations": (
        ("Datasets and campaigns", "../../use/datasets-campaigns.md"),
    ),
    "Campaign declarations": (
        ("Datasets and campaigns", "../../use/datasets-campaigns.md"),
    ),
}

RETURNED_OBJECT_GROUPS = (
    (
        "Surfaces, searches, candidates, and interfaces",
        (
            "GeneratedSurface",
            "SurfaceCollection",
            "PersistedInterfaceSearch",
            "CandidateCollection",
            "InterfaceCollection",
        ),
    ),
    (
        "Composite workflow results",
        ("RelaxationWorkflowResult", "EnergyWorkflowResult", "CampaignWorkflowResult"),
    ),
    (
        "Datasets and campaigns",
        (
            "ProjectDataset",
            "ProjectDatasetItem",
            "DatasetValidationReport",
            "DatasetExportResult",
            "ProjectCampaign",
            "ProjectCampaignRun",
        ),
    ),
    (
        "Provenance and reproducibility",
        (
            "ProjectRun",
            "ProjectSearch",
            "ProjectFollowupResult",
            "ProjectArtifact",
            "ProjectEdge",
            "LineageGraph",
            "ProjectReproducibilityManifest",
            "ReproducibilityVerificationReport",
        ),
    ),
    (
        "Saved interfaces and energy results",
        ("ProjectInterface", "ProjectEnergyResult", "ProjectThermodynamicResult"),
    ),
)

RETURNED_OBJECT_GROUP_GUIDES = {
    "Surfaces, searches, candidates, and interfaces": (
        ("Surfaces and terminations", "../../use/surfaces.md"),
        ("Searches and candidates", "../../use/searches.md"),
        ("Build and refine interfaces", "../../use/build-refine.md"),
    ),
    "Composite workflow results": (
        ("Relax and evaluate", "../../use/relax-evaluate.md"),
        ("Datasets and campaigns", "../../use/datasets-campaigns.md"),
    ),
    "Datasets and campaigns": (
        ("Datasets and campaigns", "../../use/datasets-campaigns.md"),
    ),
    "Provenance and reproducibility": (("Projects", "../../use/projects.md"),),
    "Saved interfaces and energy results": (
        ("Build and refine interfaces", "../../use/build-refine.md"),
        ("Relax and evaluate", "../../use/relax-evaluate.md"),
    ),
}

EXCEPTION_GUIDES = {
    "CalmPublicAPIError": (("Public API overview", "../public-api.md"),),
    "CalmDependencyError": (
        ("Calculator support", "../calculator-support.md"),
        ("Calculation troubleshooting", "../troubleshooting-calculations.md"),
    ),
    "CalmNoCandidatesError": (
        ("Searches and candidates", "../../use/searches.md"),
        ("Geometry troubleshooting", "../troubleshooting-geometry.md"),
    ),
    "AmbiguousProjectQueryError": (
        ("Projects", "../../use/projects.md"),
        ("Geometry troubleshooting", "../troubleshooting-geometry.md"),
    ),
    "SearchIdentityConflictError": (("Searches and candidates", "../../use/searches.md"),),
    "DatasetIdentityConflictError": (("Datasets and campaigns", "../../use/datasets-campaigns.md"),),
    "CampaignIdentityConflictError": (("Datasets and campaigns", "../../use/datasets-campaigns.md"),),
    "ProjectPersistenceError": (
        ("Projects", "../../use/projects.md"),
        ("Geometry troubleshooting", "../troubleshooting-geometry.md"),
    ),
    "ProjectReproducibilityError": (("Projects", "../../use/projects.md"),),
    "DatasetValidationError": (
        ("Datasets and campaigns", "../../use/datasets-campaigns.md"),
        ("Calculation troubleshooting", "../troubleshooting-calculations.md"),
    ),
    "UnsupportedReferenceWorkflowError": (
        ("Relax and evaluate", "../../use/relax-evaluate.md"),
        ("Energy and reference conventions", "../../understand/energetics.md"),
    ),
}

UTILITY_GUIDES = {
    "tutorial_structure": (("Build your first interface", "../../learn/first-interface.md"),),
    "load_structure": (("Materials", "../../use/materials.md"),),
    "write_structure": (("Materials", "../../use/materials.md"),),
    "write_json": (("Projects", "../../use/projects.md"),),
}

EXPORT_PURPOSES = {
    "__version__": "Installed CALM version string.",
    "Project": "Project object returned by `calm.open_project()`.",
    "open_project": "Open an existing CALM project or create a new one.",
    "Material": "Bulk-material input supplied by the user or returned by a project.",
    "Potential": "Calculator or machine-learned interatomic-potential input.",
    "SearchSettings": "Control coherent-interface search bounds and candidate admission.",
    "StrainPartitionSettings": "Control strain-partition sampling and objective selection.",
    "BuildSettings": "Control atomistic interface construction from a selected candidate.",
    "RegistrySettings": "Control in-plane registry refinement.",
    "RelaxSettings": "Control structural relaxation and convergence limits.",
    "EnergySettings": "Control raw total-energy evaluation.",
    "EnergyConvention": "Declare the formula and normalization for a derived interfacial quantity.",
    "ReferenceEnergySettings": "Supply explicit thermodynamic reference energies with named units.",
    "DatasetFeature": "Declare one named feature in a learning dataset.",
    "DatasetTarget": "Declare one named supervised-learning target.",
    "DatasetSplitSettings": "Configure group-preserving train, validation, and test assignment.",
    "DatasetSettings": "Configure dataset schema, validation, splitting, and export behavior.",
    "CampaignCase": "Declare one named system and workflow case in a campaign.",
    "CampaignSettings": "Configure campaign stages and shared workflow controls.",
    "tutorial_structure": "Load one package-owned structure used by the CALM tutorials.",
    "write_json": "Write JSON data to a file.",
}

PROJECT_PURPOSE_OVERRIDES = {
    "configure": "Save project-wide workflow defaults.",
    "materials": "Return saved materials, optionally filtered by name or identifier.",
    "add_material": "Save one user-authored material and return it.",
    "material": "Return exactly one saved material.",
    "export_materials": "Export named materials and return the written paths.",
    "surfaces": "Return saved surfaces, optionally filtered by public surface selectors.",
    "search": "Return exactly one saved interface search.",
    "search_interfaces": "Run or resume one interface search and return its saved search object.",
    "build_interfaces": "Build selected candidates and save the resulting interfaces.",
    "refine_interfaces": "Evaluate strain partitioning and registry refinement for interfaces from one search.",
    "refine_registry": "Refine in-plane registry for strain-partitioned interfaces.",
    "refined_interfaces": "Return strain- or registry-refined interfaces.",
    "interface": "Return exactly one saved interface.",
    "interface_atoms": "Return interface atoms or construct a temporary registry-shift variant.",
    "relaxed_interfaces": "Return relaxed interfaces.",
    "relax_interfaces": "Relax selected interfaces synchronously.",
    "reference_energy_runs": "Return reference-energy workflow runs.",
    "reference_energy_results": "Return per-interface reference-energy results.",
    "reference_energy_result": "Return exactly one reference-energy result.",
    "energy_runs": "Return raw-energy workflow runs.",
    "energy_results": "Return raw total-energy results.",
    "energy_result": "Return exactly one raw total-energy result.",
    "thermodynamic_runs": "Return thermodynamic-derivation runs.",
    "thermodynamic_results": "Return derived thermodynamic quantities.",
    "thermodynamic_result": "Return exactly one derived thermodynamic quantity.",
    "dataset": "Return exactly one project dataset.",
    "dataset_items": "Return membership items for one dataset.",
    "create_dataset": "Create a new dataset or reopen an identical saved dataset.",
    "add_dataset_items": "Normalize and add items under the dataset's saved policy.",
    "validate_dataset": "Validate dataset membership, schema, and provenance.",
    "campaign": "Return exactly one saved campaign.",
    "campaign_run": "Return exactly one campaign run.",
    "create_campaign": "Create a new campaign or reopen an identical saved campaign.",
}

WORKFLOW_ROLE_OVERRIDES = {
    "GeneratedSurface": "Oriented surface object returned by surface generation and queries.",
    "SurfaceCollection": "Collection returned by `Project.surfaces()`.",
    "PersistedInterfaceSearch": "Saved interface search with candidate and downstream-result navigation.",
    "CandidateCollection": "Candidate collection with filtering, Pareto inspection, plotting, and selection.",
    "InterfaceCollection": "Collection of constructed, refined, or relaxed interfaces.",
    "ProjectRun": "Saved workflow-run summary.",
    "ProjectSearch": "Saved interface-search summary.",
    "ProjectFollowupResult": "Saved refinement or follow-up result.",
    "ProjectInterface": "Saved interface summary.",
    "ProjectEnergyResult": "Raw total-energy result.",
    "ProjectThermodynamicResult": "Derived interfacial quantity under an explicit convention.",
    "ProjectDataset": "Project dataset with validation, splitting, table, and export operations.",
    "ProjectDatasetItem": "One item in a project dataset.",
    "ProjectCampaign": "Project campaign and its saved runs.",
    "ProjectCampaignRun": "One campaign execution.",
    "ProjectArtifact": "File or other artifact attached to a workflow run.",
    "ProjectEdge": "Directed provenance relationship between two saved objects.",
    "LineageGraph": "Provenance graph returned by `Project.lineage()`.",
    "RelaxationWorkflowResult": "Composite relaxation result with run status, per-target results, and relaxed interfaces.",
    "EnergyWorkflowResult": "Composite energy result with raw and optional derived quantities.",
    "CampaignWorkflowResult": "Composite campaign result with cases, datasets, failures, and comparison views.",
    "DatasetValidationReport": "Structured dataset-validation report.",
    "DatasetExportResult": "Structured dataset-export result and checksum inventory.",
    "ProjectReproducibilityManifest": "Immutable snapshot of project reproducibility evidence.",
    "ReproducibilityVerificationReport": "Comparison between a recorded manifest and the current project state.",
}

WORKFLOW_OBJECT_MEMBERS = {
    "GeneratedSurface": (
        "id_short", "uid_full", "label", "material", "miller", "formula", "natoms",
        "area", "vacuum", "thickness", "layers", "termination_top",
        "termination_bottom", "summary", "to_ase", "to_file", "characterize",
        "to_surface",
    ),
    "SurfaceCollection": (
        "available_views", "to_rows", "to_table", "to_dataframe", "write_table",
        "where", "get", "one_or_none", "latest", "characterizations",
        "usable_surfaces", "select", "one",
    ),
    "PersistedInterfaceSearch": (
        "name", "id_short", "uid_full", "run_status", "empty", "candidates",
        "validate_buildable", "status", "buildability_summary", "summary", "explain",
        "interfaces", "prototype_ids", "reference_energy_results", "energy_results",
        "thermodynamic_results",
    ),
    "CandidateCollection": (
        "available_views", "to_rows", "to_table", "to_dataframe", "write_table",
        "where", "get", "one_or_none", "latest", "plot_pareto", "materials", "atoms",
        "pareto", "strain", "miller_pair", "tags", "terminations", "select_top",
        "select", "validate_buildable",
    ),
    "InterfaceCollection": (
        "available_views", "to_rows", "to_table", "to_dataframe", "write_table",
        "where", "get", "one_or_none", "latest", "materials", "stage", "refined",
        "relaxed", "candidate", "search", "write_structures", "plot_build_summary",
    ),
    "ProjectRun": ("uid_full", "id_short", "run_type", "status", "created_at", "updated_at"),
    "ProjectSearch": (
        "name", "uid_full", "id_short", "run_uid_full", "status", "n_candidates",
        "created_at", "updated_at",
    ),
    "ProjectFollowupResult": (
        "uid_full", "id_short", "kind", "status", "target_uid_full", "best_energy",
        "param1", "param2", "n_points", "created_at", "updated_at",
    ),
    "ProjectInterface": ("uid_full", "id_short", "label", "prototype_uid_full", "stage"),
    "ProjectEnergyResult": (
        "uid_full", "id_short", "status", "target_uid_full", "target_kind", "quantity",
        "energy_eV", "units", "backend", "succeeded",
    ),
    "ProjectThermodynamicResult": (
        "uid_full", "id_short", "status", "target_uid_full", "target_kind", "quantity",
        "value_eV_per_A2", "value_J_per_m2", "normalization_area_A2", "n_interfaces",
        "units", "succeeded",
    ),
    "ProjectDataset": (
        "uid_full", "id_short", "name", "description", "created_at", "schema_version",
        "items", "add", "validate", "validate_ml", "split", "groups", "available_views",
        "to_rows", "to_table", "to_dataframe", "write_table", "export",
    ),
    "ProjectDatasetItem": (
        "uid_full", "id_short", "index", "created_at", "features", "targets", "group_id",
        "split_name",
    ),
    "ProjectCampaign": ("uid_full", "id_short", "name", "created_at", "runs", "run"),
    "ProjectCampaignRun": (
        "uid_full", "id_short", "status", "started_at", "finished_at",
    ),
    "ProjectArtifact": ("uid_full", "id_short", "kind", "uri", "created_at"),
    "ProjectEdge": ("src_uid_full", "dst_uid_full", "kind", "created_at"),
    "LineageGraph": ("root_uid_full", "nodes", "edges", "node", "upstream", "downstream", "to_rows"),
    "RelaxationWorkflowResult": (
        "run", "results", "relaxed_interfaces", "ok", "failures", "available_views",
        "to_rows", "to_table", "to_dataframe", "write_table", "summary",
    ),
    "EnergyWorkflowResult": (
        "energy_run", "energy_results", "thermodynamic_run", "thermodynamic_results",
        "ok", "failures", "available_views", "to_rows", "to_table", "to_dataframe",
        "write_table", "summary",
    ),
    "CampaignWorkflowResult": (
        "campaign", "run", "cases", "status", "reused", "datasets", "failures",
        "available_views", "to_rows", "to_table", "to_dataframe", "write_table",
        "comparison", "summary",
    ),
    "DatasetValidationReport": (
        "dataset_uid_full", "n_items", "n_valid", "issues", "content_fingerprint", "ok",
        "summary", "raise_for_errors",
    ),
    "DatasetExportResult": (
        "dataset_uid_full", "destination", "manifest_path", "n_items", "files", "checksums",
        "content_fingerprint", "summary",
    ),
    "ProjectReproducibilityManifest": (
        "schema_version", "snapshot_id", "generated_at_utc", "files", "backends", "seeds",
        "write", "summary", "read",
    ),
    "ReproducibilityVerificationReport": (
        "manifest_path", "recorded_snapshot_id", "current_snapshot_id", "issues", "ok",
        "warnings", "errors", "raise_for_errors", "summary",
    ),
}

INPUT_MEMBER_OVERRIDES = {
    "Material": ("from_file", "from_ase", "summary", "to_ase", "to_file", "characterize"),
    "Potential": (
        "grace", "mace", "from_ase", "available", "info", "calculator", "check",
        "validate", "supports", "unsupported_elements", "fingerprint",
    ),
}

_USER_HIDDEN_TABLE_FIELDS = {
    "authority",
    "payload",
    "contract",
    "contract_status",
    "spec",
    "progress",
    "metadata",
    "failure",
    "backend_identity",
    "identity_algorithm",
    "pair_identity",
    "source_provenance",
    "zur_mcgill_diagnostic",
    "search_identity",
    "pareto_policy_version",
    "pareto_policy",
    "identity_version",
    "pareto_population_scope",
    "pareto_population_size",
    "pareto_d_cell_key",
    "registry_provenance_status",
    "normalization_area_source_status",
    "calculator_compatibility",
}

_FORBIDDEN_VISIBLE_TERMS = (
    "calm.public.",
    "current-schema",
    "durable query view",
    "public Material facade",
    "project projection",
    "persisted payload",
    "serializer",
    "authority",
    "internal workspace state",
    "project-bound dataset record",
    "project-bound campaign record",
    "campaign-run record",
    "saved interface and energy records",
)


def _contract() -> dict[str, Any]:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if payload["schema_version"] != "calm.public_api_contract.v4":
        raise ValueError("Unsupported public API contract schema")
    return payload


def _table_view_contract() -> dict[str, Any]:
    payload = json.loads(TABLE_VIEW_CONTRACT.read_text(encoding="utf-8"))
    if payload["schema_version"] != "calm.public_table_views.v8":
        raise ValueError("Unsupported public table-view contract schema")
    return payload


def _load_symbol(qualified_name: str) -> Any:
    module_name, separator, symbol_name = qualified_name.rpartition(".")
    if not separator:
        raise ValueError(f"Invalid qualified name {qualified_name!r}")
    return getattr(importlib.import_module(module_name), symbol_name)


def _clean_public_text(text: str) -> str:
    replacements = (
        ("identity, authority, and ", "identity and "),
        ("Authoritative materialized surface records", "Generated surfaces"),
        ("Materialized surface records", "Generated surfaces"),
        ("Durable search records", "Saved searches"),
        ("Saved search records", "Saved searches"),
        ("relaxed-interface records", "relaxed interfaces"),
        ("whose records retain", "that retains"),
        ("The project-bound authoritative dataset record", "The saved project dataset"),
        ("The project-bound dataset record", "The saved project dataset"),
        ("project-bound dataset record", "saved project dataset"),
        ("The project-bound authoritative campaign record", "The saved project campaign"),
        ("The project-bound campaign record", "The saved project campaign"),
        ("project-bound campaign record", "saved project campaign"),
        ("The matching campaign-run record", "The matching campaign run"),
        ("matching campaign-run record", "matching campaign run"),
        ("campaign-run record", "campaign run"),
        ("The matching authoritative campaign record", "The matching saved campaign"),
        ("The matching campaign record", "The matching saved campaign"),
        ("matching campaign record", "matching saved campaign"),
        ("Authoritative campaign/run records", "Campaign runs"),
        ("Campaign/run records", "Campaign runs"),
        ("authoritative persisted ", "saved "),
        ("persisted authoritative ", "saved "),
        ("authoritative ", ""),
        ("Persist ", "Save "),
        ("persist ", "save "),
        ("durable ", "saved "),
        ("Durable ", "Saved "),
        ("Complete public ", "Complete "),
        ("Complete typed ", "Complete "),
        (", and authority", ""),
        (" and authority", ""),
        ("Authoritative ", ""),
        ("persisted ", "saved "),
        ("Persisted ", "Saved "),
        ("durable project-bound search view", "saved search"),
        ("durable project view", "saved search"),
        ("durable query view", "saved search"),
        ("directory-backed ", ""),
        ("current-schema", "current-format"),
        ("project projection", "saved project material"),
        ("public Material facade", "material"),
        ("durable view", "saved search"),
        ("Durable view", "Saved search"),
        ("projection", "view"),
        ("Projection", "View"),
        ("identity-bearing", "scientifically defining"),
        ("first-class ", ""),
        ("canonical surface helper", "supported surface workflow"),
        ("canonical settings", "settings"),
        ("canonical operational grid", "default grid"),
        ("canonical operational result limit", "default result limit"),
        ("current operational result limit", "default result limit"),
        ("operational value", "default value"),
        ("Accepted canonical values", "Accepted values"),
        ("Ordered canonical subsequence", "Ordered subsequence"),
        ("canonical potential-energy-density objective", "default potential-energy-density objective"),
        ("records the deliberately narrower identity equivalence", "uses only the identity operation"),
        ("target-specific seed from the run and interface identities", "target-specific seed from the selected run and interface"),
        ("joined-record path", "joined-result path"),
        ("stable public contract", "current public API"),
        ("dataset contract", "dataset settings"),
        ("learning contract", "learning configuration"),
        ("scientific identity", "scientific inputs"),
        ("identity-construction", "implementation"),
        ("Artifact identity", "Artifact identifier"),
        ("Campaign identity", "Campaign identifier"),
        ("Campaign-run identity", "Campaign run identifier"),
        ("Candidate identity and Pareto-policy provenance", "Candidate identifiers and Pareto status"),
        ("Concise dataset identity", "Concise dataset identifiers"),
        ("Dataset identity", "Dataset identifiers"),
        ("Edge identity", "Edge identifier"),
        ("Concise identity and size summary", "Concise identifier and size summary"),
        ("Interface identity", "Interface identifiers"),
        ("Reference identity", "Reference identifiers"),
        ("Run identity", "Run identifiers"),
        ("Search identity", "Search identifiers"),
    )
    result = text.strip()
    for old, new in replacements:
        result = result.replace(old, new)
    result = re.sub(r"\s+", " ", result).strip()
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result


def _purpose(row: dict[str, Any]) -> str:
    return EXPORT_PURPOSES.get(row["name"], _clean_public_text(row["purpose"]))


def _project_purpose(row: dict[str, Any]) -> str:
    return PROJECT_PURPOSE_OVERRIDES.get(row["name"], _clean_public_text(row["purpose"]))


def _workflow_role(row: dict[str, Any]) -> str:
    return WORKFLOW_ROLE_OVERRIDES.get(row["name"], _clean_public_text(row["role"]))


def _format_annotation(annotation: Any) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        text = annotation
    else:
        text = inspect.formatannotation(annotation)
    text = text.replace("typing.", "")
    text = text.replace("_CampaignCaseVariant", "Any")
    text = re.sub(r"'([A-Za-z_][A-Za-z0-9_]*)'", r"\1", text)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"\'", "\""}:
        text = text[1:-1]
    text = re.sub(r"calm(?:\.[A-Za-z_][A-Za-z0-9_]*)+\.([A-Za-z_][A-Za-z0-9_]*)", r"\1", text)
    return text


def _format_parameter(parameter: inspect.Parameter) -> str:
    prefix = ""
    if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
        prefix = "*"
    elif parameter.kind is inspect.Parameter.VAR_KEYWORD:
        prefix = "**"
    text = prefix + parameter.name
    annotation = _format_annotation(parameter.annotation)
    if annotation:
        text += f": {annotation}"
    if parameter.default is not inspect.Parameter.empty:
        default = repr(parameter.default)
        if default == "<factory>":
            default = "<factory>"
        text += f" = {default}"
    return text


def _signature_parts(obj: Any, *, drop_first: bool = False) -> tuple[list[str], str]:
    signature = inspect.signature(obj)
    parameters = list(signature.parameters.values())
    if drop_first and parameters and parameters[0].name in {"self", "cls"}:
        parameters = parameters[1:]

    parts: list[str] = []
    saw_var_positional = False
    positional_only_count = sum(
        parameter.kind is inspect.Parameter.POSITIONAL_ONLY for parameter in parameters
    )
    for index, parameter in enumerate(parameters):
        if (
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and not saw_var_positional
            and "*" not in parts
        ):
            parts.append("*")
        parts.append(_format_parameter(parameter))
        if parameter.kind is inspect.Parameter.VAR_POSITIONAL:
            saw_var_positional = True
        if positional_only_count and index + 1 == positional_only_count:
            parts.append("/")
    returns = _format_annotation(signature.return_annotation)
    return parts, returns


def _signature_text(display_name: str, obj: Any, *, drop_first: bool = False) -> str:
    try:
        parts, returns = _signature_parts(obj, drop_first=drop_first)
    except (TypeError, ValueError):
        return display_name
    one_line = f"{display_name}({', '.join(parts)})"
    if returns:
        one_line += f" -> {returns}"
    if len(one_line) <= 96 and all(len(part) <= 72 for part in parts):
        return one_line
    lines = [f"{display_name}("]
    lines.extend(f"    {part}," for part in parts)
    closing = ")"
    if returns:
        closing += f" -> {returns}"
    lines.append(closing)
    return "\n".join(lines)


def _signature_block(display_name: str, obj: Any, *, drop_first: bool = False) -> str:
    return "```python\n" + _signature_text(display_name, obj, drop_first=drop_first) + "\n```"


def _google_section(docstring: str, section: str) -> list[tuple[str, str]]:
    lines = inspect.cleandoc(docstring or "").splitlines()
    marker = f"{section}:"
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return []

    entries: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    current_name = ""
    for line in lines[start:]:
        if line and not line.startswith(" ") and line.endswith(":"):
            break
        match = re.match(r"^    ([^\s][^:]*):\s*(.*)$", line)
        if match:
            if current is not None:
                entries.append((current_name, current))
            current_name = match.group(1).strip()
            current = [match.group(2).strip()]
            continue
        if current is not None and line.startswith("        "):
            current.append(line.strip())
    if current is not None:
        entries.append((current_name, current))
    return [(name, _clean_public_text(" ".join(parts))) for name, parts in entries]


def _returns_summary(obj: Any) -> str | None:
    entries = _google_section(inspect.getdoc(obj) or "", "Returns")
    if not entries:
        return None
    name, description = entries[0]
    label = name.strip("()")
    return f"`{label}` — {description}" if label else description


def _raises_summary(obj: Any) -> str | None:
    entries = _google_section(inspect.getdoc(obj) or "", "Raises")
    if not entries:
        return None
    names = ", ".join(f"`{name}`" for name, _ in entries)
    return names


def _member_kind(cls: type[Any], name: str) -> str:
    try:
        raw = inspect.getattr_static(cls, name)
    except AttributeError:
        return "attribute"
    if isinstance(raw, property):
        return "attribute"
    value = getattr(cls, name, None)
    return "operation" if callable(value) else "attribute"


def _member_signature(cls: type[Any], name: str) -> str:
    value = getattr(cls, name)
    text = " ".join(_signature_text(name, value, drop_first=True).split())
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r",\s*\)", ")", text)
    return text


def _documented_members(row: dict[str, Any]) -> tuple[str, ...]:
    if row["name"] in WORKFLOW_OBJECT_MEMBERS:
        return WORKFLOW_OBJECT_MEMBERS[row["name"]]
    if row["name"] in INPUT_MEMBER_OVERRIDES:
        return INPUT_MEMBER_OVERRIDES[row["name"]]
    return tuple(row.get("members", ()))


def _documented_columns(spec: Any) -> tuple[str, ...]:
    return tuple(field for field in spec.columns if field not in _USER_HIDDEN_TABLE_FIELDS)


def table_view_inventory() -> list[dict[str, Any]]:
    """Return public table owners and their live view registries."""

    payload = _table_view_contract()
    inventory: list[dict[str, Any]] = []
    for name, contract_row in sorted(payload["current_view_owners"].items()):
        owner = _load_symbol(contract_row["qualified_name"])
        specs = tuple(owner._view_specs)
        if not specs:
            raise ValueError(f"{name} does not define any public table views")
        canonical_names = [spec.name for spec in specs]
        recognized_names = sorted(
            {view_name for spec in specs for view_name in (spec.name, *spec.aliases)}
        )
        if sorted(contract_row["target_views"]) != sorted(canonical_names):
            raise ValueError(f"{name} table views differ from the live registry")
        if contract_row["recognized_views"] != recognized_names:
            raise ValueError(f"{name} recognized table views differ from the live registry")
        if contract_row["default_view"] not in canonical_names:
            raise ValueError(f"{name} default table view is not canonical")
        inventory.append(
            {
                "name": name,
                "default_view": contract_row["default_view"],
                "recognized_views": tuple(recognized_names),
                "specs": specs,
            }
        )
    return inventory


def _view_signature(owner: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(
        (
            spec.name,
            _documented_columns(spec),
            spec.aliases,
            spec.allow_extra_columns,
            spec.description,
        )
        for spec in owner["specs"]
    )


def _table_view_families(owners: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for owner in owners:
        grouped[_view_signature(owner)].append(owner)
    return sorted(grouped.values(), key=lambda rows: tuple(row["name"] for row in rows))


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guide_links(guides: tuple[tuple[str, str], ...]) -> str:
    return "; ".join(f"[{label}]({path})" for label, path in guides)


def _render_related_guides(
    guides: tuple[tuple[str, str], ...],
    *,
    label: str = "Related workflow",
) -> list[str]:
    return [f"**{label}:** {_guide_links(guides)}", ""]


def _attribute_descriptions(obj: Any) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    for raw_name, description in _google_section(inspect.getdoc(obj) or "", "Attributes"):
        name = raw_name.split(" ", 1)[0].strip()
        descriptions[name] = description
    return descriptions


def _render_setting_fields(obj: Any) -> list[str]:
    signature = inspect.signature(obj)
    descriptions = _attribute_descriptions(obj)
    parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.name not in {"self", "cls"}
        and parameter.kind
        not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
    ]
    if not parameters:
        return []

    missing = [parameter.name for parameter in parameters if parameter.name not in descriptions]
    if missing:
        raise ValueError(
            f"{getattr(obj, '__name__', obj)!s} is missing public field descriptions: {missing}"
        )

    lines = [
        "**Fields**",
        "",
        "| Field | Meaning |",
        "| --- | --- |",
    ]
    for parameter in parameters:
        lines.append(
            f"| `{parameter.name}` | "
            f"{_escape_markdown_cell(descriptions[parameter.name])} |"
        )
    lines.append("")
    return lines


def _render_operation_details(obj: Any) -> list[str]:
    lines: list[str] = []
    returns = _returns_summary(obj)
    raises = _raises_summary(obj)
    if returns:
        lines.extend((f"**Returns:** {returns}", ""))
    if raises:
        lines.extend((f"**May raise:** {raises}", ""))
    return lines


def render_project(payload: dict[str, Any]) -> str:
    project_row = next(row for row in payload["exports"] if row["name"] == "Project")
    open_row = next(row for row in payload["exports"] if row["name"] == "open_project")
    project_cls = _load_symbol(project_row["implementation"])
    open_project = _load_symbol(open_row["implementation"])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in payload["project_methods"]:
        grouped[row["group"]].append(row)

    lines = [
        "# Project operations",
        "",
        "Open or create a project with `calm.open_project(...)`. The returned",
        "`calm.Project` object is the entry point for saved workflows, queries,",
        "exports, and provenance inspection.",
        "{: .calm-lede }",
        "",
        "```python",
        "import calm",
        "",
        'project = calm.open_project("study.calm")',
        "```",
        "",
        "Do not construct `calm.Project` directly. Use `calm.open_project()` so CALM",
        "can initialize and validate the saved project correctly.",
        "",
        "Use the [workflow manual](../../use/projects.md) to learn normal sequencing.",
        "Use this page when you already know which operation you need and want its",
        "exact signature, return type, or public exception boundary.",
        "",
        "## Open a project",
        "",
        "<a id=\"open-project\"></a>",
        "",
        _signature_block("calm.open_project", open_project),
        "",
        "An incompatible project format raises `calm.ProjectPersistenceError`. CALM",
        "does not rewrite older project formats in place.",
        "",
        "## Operation index",
        "",
    ]

    for group in PROJECT_GROUPS:
        rows = grouped.get(group, [])
        if not rows:
            continue
        guides = PROJECT_GROUP_GUIDES[group]
        lines.extend(
            (
                f"### {PROJECT_GROUP_TITLES[group]}",
                "",
                f"Workflow guidance: {_guide_links(guides)}.",
                "",
                "| Operation | Purpose |",
                "| --- | --- |",
            )
        )
        for row in rows:
            lines.append(
                f"| [`Project.{row['name']}()`](#project-{row['name'].replace('_', '-')}) "
                f"| {_escape_markdown_cell(_project_purpose(row))} |"
            )
        lines.append("")

    lines.extend(("## Exact signatures", ""))
    for group in PROJECT_GROUPS:
        rows = grouped.get(group, [])
        if not rows:
            continue
        guides = PROJECT_GROUP_GUIDES[group]
        lines.extend(
            (
                f"### {PROJECT_GROUP_TITLES[group]}",
                "",
                f"See {_guide_links(guides)} for normal workflow sequencing and",
                "scientific interpretation.",
                "",
            )
        )
        for row in rows:
            method = getattr(project_cls, row["name"])
            anchor = row["name"].replace("_", "-")
            lines.extend(
                (
                    f"#### `Project.{row['name']}()` {{ #project-{anchor} }}",
                    "",
                    _project_purpose(row),
                    "",
                    _signature_block(f"project.{row['name']}", method, drop_first=True),
                    "",
                )
            )
            lines.extend(_render_operation_details(method))
    return "\n".join(lines).rstrip() + "\n"


def _render_member_list(cls: type[Any], members: tuple[str, ...]) -> list[str]:
    attributes = [name for name in members if _member_kind(cls, name) == "attribute"]
    operations = [name for name in members if _member_kind(cls, name) == "operation"]
    lines: list[str] = []
    if attributes:
        lines.extend(("**Key attributes:** " + ", ".join(f"`{name}`" for name in attributes), ""))
    if operations:
        lines.extend(("**Public operations**", ""))
        lines.extend(f"- `{_member_signature(cls, name)}`" for name in operations)
        lines.append("")
    return lines


def render_inputs_settings(payload: dict[str, Any]) -> str:
    rows_by_name = {row["name"]: row for row in payload["exports"]}
    lines = [
        "# Inputs and settings",
        "",
        "These top-level objects describe structures, calculators, search bounds,",
        "construction choices, relaxation, energies, datasets, and campaigns.",
        "Every import shown here comes from `calm`.",
        "{: .calm-lede }",
        "",
        "```python",
        "from calm import Material, SearchSettings",
        "```",
        "",
        "The exact constructor signatures below come from the installed CALM source.",
        "Use the linked workflow chapters to decide which values are scientifically",
        "appropriate; the reference only defines accepted inputs and defaults.",
        "",
        "## Object index",
        "",
        "| Object | Purpose | Related workflow |",
        "| --- | --- | --- |",
    ]

    for title, names in INPUT_GROUPS:
        guides = INPUT_GROUP_GUIDES[title]
        for name in names:
            row = rows_by_name[name]
            lines.append(
                f"| [`calm.{name}`](#{name.lower()}) | "
                f"{_escape_markdown_cell(_purpose(row))} | {_guide_links(guides)} |"
            )
    lines.append("")

    for title, names in INPUT_GROUPS:
        guides = INPUT_GROUP_GUIDES[title]
        lines.extend((f"## {title}", ""))
        lines.extend(_render_related_guides(guides))
        for name in names:
            row = rows_by_name[name]
            obj = _load_symbol(row["implementation"])
            lines.extend((f"### `calm.{name}` {{ #{name.lower()} }}", "", _purpose(row), ""))
            if name in {"Material", "Potential"}:
                lines.append("Use the supported constructors and factories below.")
                lines.append("")
                lines.extend(_render_member_list(obj, _documented_members(row)))
            else:
                lines.extend((_signature_block(f"calm.{name}", obj), ""))
                lines.extend(_render_setting_fields(obj))
                convenience = tuple(
                    member
                    for member in _documented_members(row)
                    if member in {
                        "from_dict", "from_value", "validate", "to_dict", "resolve_metric",
                        "resolve_alphas", "resolved_settings", "resolved_dataset_settings",
                        "variant", "grid", "schema", "is_learning_dataset",
                    }
                )
                if convenience:
                    lines.extend(_render_member_list(obj, convenience))
    return "\n".join(lines).rstrip() + "\n"


def _render_table_views(owners: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Table views",
        "",
        "Collections and workflow results provide named views for rows, terminal",
        "tables, dataframes, and CSV output. Inspect the live choices before selecting",
        "columns:",
        "",
        "```python",
        "print(result.available_views())",
        'rows = result.to_rows(view="summary")',
        "```",
        "",
        "The lists below show the stable analytical fields published in each view.",
        "Implementation metadata and diagnostic fields are omitted.",
        "Objects may append declared feature, target, dimension, or metric columns when",
        "a view explicitly allows additional columns.",
        "",
        "Candidate `area_A2` is a search-prototype quantity. Interface `area_A2` and",
        "`n_atoms` describe the realized atomistic interface, while",
        "`prototype_area_A2` preserves the source search estimate.",
        "",
        "### Object index",
        "",
        "| Object | Default | Canonical views | Aliases |",
        "| --- | --- | --- | --- |",
    ]
    for owner in owners:
        canonical = [spec.name for spec in owner["specs"]]
        aliases = [alias for spec in owner["specs"] for alias in spec.aliases]
        lines.append(
            f"| `{owner['name']}` | `{owner['default_view']}` | "
            f"{', '.join(f'`{name}`' for name in canonical)} | "
            f"{', '.join(f'`{name}`' for name in aliases) if aliases else '—'} |"
        )

    for family in _table_view_families(owners):
        owner_names = tuple(owner["name"] for owner in family)
        title = " and ".join(f"`{name}`" for name in owner_names)
        defaults = {owner["default_view"] for owner in family}
        lines.extend(("", f"### {title}", ""))
        for spec in family[0]["specs"]:
            marker = " — default" if spec.name in defaults else ""
            fields = ", ".join(f"`{field}`" for field in _documented_columns(spec)) or "—"
            aliases = ", ".join(f"`{alias}`" for alias in spec.aliases) or "none"
            dynamic = "yes" if spec.allow_extra_columns else "no"
            lines.extend(
                (
                    f"#### `{spec.name}`{marker}",
                    "",
                    _clean_public_text(spec.description),
                    "",
                    f"- Fields: {fields}",
                    f"- Aliases: {aliases}",
                    f"- Additional declared columns: {dynamic}",
                    "",
                )
            )
    return lines


def render_returned_objects(payload: dict[str, Any], owners: list[dict[str, Any]]) -> str:
    rows_by_name = {row["name"]: row for row in payload["workflow_objects"]}
    lines = [
        "# Returned objects and collections",
        "",
        "Project operations return typed objects for inspection, filtering, selection,",
        "export, validation, and workflow continuation. Users normally receive these",
        "objects from a `calm.Project`; their constructors are not part of the normal",
        "workflow.",
        "{: .calm-lede }",
        "",
        "Collections share a consistent vocabulary: `where()` filters, `get()` requires",
        "exactly one result, `one_or_none()` permits no result, and `latest()` selects the",
        "most recently created matching result.",
        "",
        "## Object index",
        "",
        "| Object | Role | Related workflow |",
        "| --- | --- | --- |",
    ]

    for title, names in RETURNED_OBJECT_GROUPS:
        guides = RETURNED_OBJECT_GROUP_GUIDES[title]
        for name in names:
            row = rows_by_name[name]
            lines.append(
                f"| [`{name}`](#{name.lower()}) | "
                f"{_escape_markdown_cell(_workflow_role(row))} | {_guide_links(guides)} |"
            )
    lines.append("")

    for title, names in RETURNED_OBJECT_GROUPS:
        guides = RETURNED_OBJECT_GROUP_GUIDES[title]
        lines.extend((f"## {title}", ""))
        lines.extend(_render_related_guides(guides))
        for name in names:
            row = rows_by_name[name]
            cls = _load_symbol(row["implementation"])
            lines.extend(
                (
                    f"### `{name}` {{ #{name.lower()} }}",
                    "",
                    _workflow_role(row),
                    "",
                )
            )
            lines.extend(_render_member_list(cls, _documented_members(row)))

    lines.extend(_render_table_views(owners))
    return "\n".join(lines).rstrip() + "\n"


def render_exceptions_utilities(payload: dict[str, Any]) -> str:
    errors = [row for row in payload["exports"] if row["group"] == "errors"]
    utilities = [row for row in payload["exports"] if row["group"] == "utilities"]
    version = next(row for row in payload["exports"] if row["group"] == "metadata")
    lines = [
        "# Exceptions and utilities",
        "",
        "Catch CALM's public exceptions when an application needs to recover from a",
        "known user-visible condition. File helpers are available from the same",
        "top-level namespace.",
        "{: .calm-lede }",
        "",
        "## Package version",
        "",
        f"`calm.__version__` — {_purpose(version)}",
        "",
        "## Public exceptions",
        "",
        "| Exception | Meaning | Recovery guidance | Direct bases |",
        "| --- | --- | --- | --- |",
    ]
    for row in errors:
        cls = _load_symbol(row["implementation"])
        bases = ", ".join(f"`{base.__name__}`" for base in cls.__bases__)
        guidance = _guide_links(EXCEPTION_GUIDES[row["name"]])
        lines.append(
            f"| `calm.{row['name']}` | {_escape_markdown_cell(_purpose(row))} | "
            f"{guidance} | {bases} |"
        )

    lines.extend(
        (
            "",
            "Catch the narrowest exception that matches the recovery action. Catch",
            "`calm.CalmPublicAPIError` only when one handler genuinely applies to all",
            "CALM workflow errors.",
            "",
            "## Structure and file utilities",
            "",
        )
    )
    for row in utilities:
        obj = _load_symbol(row["implementation"])
        lines.extend(
            (
                f"### `calm.{row['name']}()` {{ #{row['name'].replace('_', '-')} }}",
                "",
                _purpose(row),
                "",
                _signature_block(f"calm.{row['name']}", obj),
                "",
            )
        )
        lines.extend(_render_related_guides(UTILITY_GUIDES[row["name"]]))
        lines.extend(_render_operation_details(obj))
    return "\n".join(lines).rstrip() + "\n"


def rendered_pages() -> dict[Path, str]:
    payload = _contract()
    table_owners = table_view_inventory()
    pages = {
        OUTPUT_ROOT / "project.md": render_project(payload),
        OUTPUT_ROOT / "inputs-settings.md": render_inputs_settings(payload),
        OUTPUT_ROOT / "returned-objects.md": render_returned_objects(payload, table_owners),
        OUTPUT_ROOT / "exceptions-utilities.md": render_exceptions_utilities(payload),
    }
    combined = "\n".join(pages.values())
    leaks = [term for term in _FORBIDDEN_VISIBLE_TERMS if term.lower() in combined.lower()]
    if leaks:
        raise ValueError(f"Internal terminology leaked into API reference: {leaks}")
    return pages
