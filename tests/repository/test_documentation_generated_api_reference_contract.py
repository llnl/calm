"""Contracts for CALM's generated user-facing API reference."""

from __future__ import annotations

import ast
import dataclasses
import io
import importlib
import inspect
import json
from pathlib import Path
import re
import runpy
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
DOCUMENTATION_BUILD = ROOT / "engineering" / "documentation"
CONTRACT = ROOT / "engineering" / "architecture" / "current-public-contract.json"
TABLE_VIEW_CONTRACT = (
    ROOT / "engineering" / "architecture" / "current-public-table-views.json"
)
if str(DOCUMENTATION_BUILD) not in sys.path:
    sys.path.insert(0, str(DOCUMENTATION_BUILD))
import api_reference_manifest as manifest  # noqa: E402


EXPECTED_PAGES = {
    Path("reference/api/project.md"),
    Path("reference/api/inputs-settings.md"),
    Path("reference/api/returned-objects.md"),
    Path("reference/api/exceptions-utilities.md"),
}


def _payload() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _documentable_members(target: str) -> set[str]:
    module_name, object_name = target.rsplit(".", 1)
    obj = getattr(importlib.import_module(module_name), object_name)
    members = set(dir(obj))
    for cls in getattr(obj, "__mro__", (obj,)):
        members.update(getattr(cls, "__annotations__", {}))
        members.update(getattr(cls, "__dataclass_fields__", {}))
    return members


def test_generated_pages_are_deterministic_and_cover_the_public_contract() -> None:
    payload = _payload()
    pages = manifest.rendered_pages()
    assert pages == manifest.rendered_pages()
    assert set(pages) == EXPECTED_PAGES
    assert all(not (DOCS / relative).exists() for relative in pages)

    project = pages[Path("reference/api/project.md")]
    inputs = pages[Path("reference/api/inputs-settings.md")]
    returned = pages[Path("reference/api/returned-objects.md")]
    utilities = pages[Path("reference/api/exceptions-utilities.md")]

    assert "calm.open_project" in project
    assert "Do not construct `calm.Project` directly" in project
    for row in payload["project_methods"]:
        assert f"Project.{row['name']}()" in project
        method = getattr(manifest._load_symbol("calm.public.project.Project"), row["name"])
        assert manifest._signature_text(
            f"project.{row['name']}", method, drop_first=True
        ) in project

    for row in payload["exports"]:
        if row["group"] in {"inputs", "settings"}:
            assert f"calm.{row['name']}" in inputs
        elif row["group"] in {"metadata", "errors", "utilities"}:
            assert f"calm.{row['name']}" in utilities
        elif row["name"] in {"Project", "open_project"}:
            assert f"calm.{row['name']}" in project

    for row in payload["workflow_objects"]:
        assert f"`{row['name']}`" in returned

    combined = "\n".join(pages.values())
    assert "::: " not in combined
    for phrase in ("beginner api", "basic api", "advanced api", "frozen beta"):
        assert phrase not in combined.lower()


def test_generated_reference_uses_only_user_facing_names_and_language() -> None:
    payload = _payload()
    combined = "\n".join(manifest.rendered_pages().values())

    for namespace in payload["internal_namespaces"]:
        assert f"from {namespace}" not in combined
        assert f"import {namespace}" not in combined
        assert f"### `{namespace}" not in combined
    for phrase in (
        "current-schema",
        "durable query view",
        "public Material facade",
        "project projection",
        "persisted payload",
        "serializer",
        "database table",
        "internal workspace state",
        "project-bound dataset record",
        "project-bound campaign record",
        "campaign-run record",
        "saved interface and energy records",
    ):
        assert phrase not in combined

    assert re.search(r"\bauthority\b", combined, flags=re.IGNORECASE) is None

    # This string is an exact, user-selectable EnergyConvention value. It may
    # appear in the signature and field explanation, but no prose use of the
    # implementation-oriented adjective is allowed.
    authoritative_tokens = re.findall(r"authoritative[A-Za-z0-9_]*", combined)
    assert authoritative_tokens
    assert set(authoritative_tokens) == {"authoritative_interface_area"}


def test_curated_members_exist_and_hide_low_level_record_fields() -> None:
    payload = _payload()
    rows = {row["name"]: row for row in payload["workflow_objects"]}
    returned = manifest.rendered_pages()[Path("reference/api/returned-objects.md")]

    for name, members in manifest.WORKFLOW_OBJECT_MEMBERS.items():
        row = rows[name]
        available = _documentable_members(row["implementation"])
        missing = sorted(set(members) - available)
        assert missing == [], f"{name} has unknown curated members: {missing}"

    for hidden in ("payload", "authority", "spec", "progress", "metadata"):
        assert f"`{hidden}`" not in returned

    assert "Do not construct" not in returned
    assert "their constructors are not part of the normal workflow" in " ".join(
        returned.split()
    )


def test_generated_table_view_reference_matches_live_registries_compactly() -> None:
    payload = json.loads(TABLE_VIEW_CONTRACT.read_text(encoding="utf-8"))
    owners = manifest.table_view_inventory()
    page = manifest.rendered_pages()[Path("reference/api/returned-objects.md")]

    assert len(owners) == len(payload["current_view_owners"]) == 25
    assert "## Table views" in page
    assert "print(result.available_views())" in page
    assert "Candidate `area_A2` is a search-prototype quantity" in page
    assert "`prototype_area_A2` preserves the source search estimate" in page
    assert "| Interpretation |" not in page
    assert len(page.split()) < 5000

    for owner in owners:
        contract_row = payload["current_view_owners"][owner["name"]]
        assert owner["default_view"] == contract_row["default_view"]
        assert sorted(spec.name for spec in owner["specs"]) == contract_row[
            "target_views"
        ]
        assert f"`{owner['name']}` | `{owner['default_view']}`" in page
        for spec in owner["specs"]:
            assert f"#### `{spec.name}`" in page
            for field in manifest._documented_columns(spec):
                assert f"`{field}`" in page
            for field in manifest._USER_HIDDEN_TABLE_FIELDS.intersection(spec.columns):
                assert f"`{field}`" not in page


def test_settings_reference_uses_live_constructor_signatures() -> None:
    payload = _payload()
    page = manifest.rendered_pages()[Path("reference/api/inputs-settings.md")]
    for row in payload["exports"]:
        if row["group"] != "settings":
            continue
        cls = manifest._load_symbol(row["implementation"])
        assert dataclasses.is_dataclass(cls), row["implementation"]
        assert manifest._signature_text(f"calm.{row['name']}", cls) in page
        for field in dataclasses.fields(cls):
            assert field.name in page

    material = next(row for row in payload["exports"] if row["name"] == "Material")
    potential = next(row for row in payload["exports"] if row["name"] == "Potential")
    assert "calm.Material(" not in page
    assert "calm.Potential(" not in page
    for row in (material, potential):
        for member in manifest._documented_members(row):
            assert f"{member}(" in page
    assert "_calculator" not in page
    assert "_external_calculator" not in page
    assert "authority:" not in page


def test_mkdocs_emits_every_virtual_page_without_mkdocstrings(monkeypatch) -> None:
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "engineering/documentation/generate_api_reference.py" in mkdocs
    assert all(relative.as_posix() in mkdocs for relative in EXPECTED_PAGES)
    assert "mkdocstrings" not in mkdocs
    assert "mkdocstrings" not in pyproject

    emitted: dict[Path, str] = {}

    class Capture(io.StringIO):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = Path(path)

        def __enter__(self) -> "Capture":
            return self

        def __exit__(self, *args: object) -> None:
            emitted[self.path] = self.getvalue()
            self.close()

    monkeypatch.setitem(
        sys.modules,
        "mkdocs_gen_files",
        SimpleNamespace(open=lambda path, mode: Capture(path)),
    )
    runpy.run_path(
        str(DOCUMENTATION_BUILD / "generate_api_reference.py"),
        run_name="__main__",
    )
    assert emitted == manifest.rendered_pages()


def test_documented_project_operations_have_docstrings() -> None:
    project_source = ROOT / "calm" / "public" / "project.py"
    tree = ast.parse(project_source.read_text(encoding="utf-8"))
    project = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    docstrings = {
        node.name: ast.get_docstring(node)
        for node in project.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [
        row["name"] for row in _payload()["project_methods"] if not docstrings.get(row["name"])
    ]
    assert missing == []


def test_unannotated_project_returns_have_typed_docstring_entries() -> None:
    """Keep return information available to the compact signature generator."""

    project_source = ROOT / "calm" / "public" / "project.py"
    tree = ast.parse(project_source.read_text(encoding="utf-8"))
    project = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    public_operations = {row["name"] for row in _payload()["project_methods"]}

    malformed: list[str] = []
    for node in project.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in public_operations or node.returns is not None:
            continue
        docstring = ast.get_docstring(node) or ""
        lines = docstring.splitlines()
        try:
            returns_index = next(
                index for index, line in enumerate(lines) if line.strip() == "Returns:"
            )
        except StopIteration:
            continue
        first_value = next(
            (line.strip() for line in lines[returns_index + 1 :] if line.strip()), ""
        )
        closing = first_value.find("):")
        if not (first_value.startswith("(") and closing > 1):
            malformed.append(node.name)
    assert malformed == []


PRINCIPAL_WORKFLOW_METHODS = {
    "add_material",
    "search",
    "search_interfaces",
    "build_interfaces",
    "refine_interfaces",
    "refine_registry",
    "relax_interfaces",
    "evaluate_reference_energies",
    "evaluate_energies",
    "create_dataset",
    "validate_ml_dataset",
    "create_campaign",
    "run_campaign",
    "optimize_material",
    "generate_surfaces",
}


def _google_section_entries(docstring: str, section: str) -> dict[str, str]:
    lines = inspect.cleandoc(docstring).splitlines()
    marker = f"{section}:"
    try:
        start = lines.index(marker) + 1
    except ValueError:
        return {}

    entries: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start:]:
        if line and not line.startswith(" ") and line.endswith(":"):
            break
        match = re.match(r"^    ([A-Za-z_][A-Za-z0-9_]*)(?: \([^)]*\))?:\s*(.*)$", line)
        if match:
            current = match.group(1)
            entries[current] = [match.group(2)]
            continue
        typed_return = re.match(r"^    \(([^)]+)\):\s*(.*)$", line)
        if typed_return:
            current = f"({typed_return.group(1)})"
            entries[current] = [typed_return.group(2)]
            continue
        if current is not None and line.startswith("        "):
            entries[current].append(line.strip())
    return {name: " ".join(parts).strip() for name, parts in entries.items()}


def test_public_settings_document_every_field_and_default() -> None:
    failures: list[str] = []
    for row in _payload()["exports"]:
        if row["group"] != "settings":
            continue
        module_name, object_name = row["implementation"].rsplit(".", 1)
        cls = getattr(importlib.import_module(module_name), object_name)
        entries = _google_section_entries(inspect.getdoc(cls) or "", "Attributes")
        for field in dataclasses.fields(cls):
            description = entries.get(field.name)
            if not description:
                failures.append(f"{row['name']}.{field.name}: undocumented")
                continue
            has_default = (
                field.default is not dataclasses.MISSING
                or field.default_factory is not dataclasses.MISSING
            )
            if has_default and "default" not in description.lower():
                failures.append(f"{row['name']}.{field.name}: default omitted")
    assert failures == []


def test_principal_workflows_document_arguments_returns_and_exceptions() -> None:
    project_source = ROOT / "calm" / "public" / "project.py"
    tree = ast.parse(project_source.read_text(encoding="utf-8"))
    project = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Project"
    )
    methods = {
        node.name: node
        for node in project.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    failures: list[str] = []
    for name in sorted(PRINCIPAL_WORKFLOW_METHODS):
        node = methods[name]
        docstring = ast.get_docstring(node) or ""
        args = _google_section_entries(docstring, "Args")
        arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        parameters = [argument.arg for argument in arguments if argument.arg != "self"]
        missing = sorted(set(parameters) - set(args))
        if missing:
            failures.append(f"Project.{name}: missing Args entries {missing}")
        if not _google_section_entries(docstring, "Returns"):
            failures.append(f"Project.{name}: missing typed Returns entry")
        if not _google_section_entries(docstring, "Raises"):
            failures.append(f"Project.{name}: missing Raises entries")
    assert failures == []
