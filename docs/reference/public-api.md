# Public API

<p class="calm-lede">
Use one supported Python namespace, one project entry point, and four exact-reference pages to look up CALM inputs, operations, results, exceptions, and utilities.
</p>

## Purpose

CALM's public Python interface is available from the top-level `calm` namespace. A normal workflow has three parts:

1. create user-authored inputs and settings;
2. call an operation on a project; and
3. inspect the typed object or collection returned by that operation.

```python
import calm

project = calm.open_project("study.calm")
settings = calm.SearchSettings(max_principal_strain=0.06)
```

Use only names documented as `calm.<name>`. Package submodules are implementation details and are not supported import paths for user code.

## Canonical import or convention

### Open a project

```python
project = calm.open_project("study.calm")
```

A `calm.Project` is the normal entry point for saved materials, surfaces, searches, interfaces, calculations, datasets, campaigns, exports, and lineage. Obtain it through `calm.open_project()` rather than constructing it directly.

### Create inputs and settings

```python
material = calm.Material.from_file("POSCAR", name="Cu")
search_settings = calm.SearchSettings(
    max_principal_strain=0.06,
    max_supercell_index=12,
    max_atoms=800,
)
```

Inputs describe structures or calculators. Settings make workflow choices explicit and reusable. Their exact constructors and defaults are listed in [Inputs and settings](api/inputs-settings.md).

### Continue through returned objects

```python
search = project.search_interfaces(
    "Cu-100",
    "Ni-100",
    name="cu-ni-100",
    settings=search_settings,
)

pareto = search.candidates().select(pareto=True)
pareto.to_table(title="Pareto candidates").display()
```

Collections and workflow results are returned by project operations. Users normally inspect, filter, select, export, or continue workflows from these objects rather than constructing them directly.

## Exact behavior

### Exact-reference pages

| Page | Use it to look up |
| --- | --- |
| [Project operations](api/project.md) | Every supported `Project` operation, grouped by workflow stage, with its exact signature, return information, and public exceptions. |
| [Inputs and settings](api/inputs-settings.md) | Supported structure and calculator inputs, settings constructors, field meanings, defaults, and convenience operations. |
| [Returned objects and tables](api/returned-objects.md) | Curated attributes and operations on collections and results, plus the fields published by named table views. |
| [Exceptions and utilities](api/exceptions-utilities.md) | Public exception classes, tutorial structures, structure I/O, JSON output, and the installed version string. |

The generated pages are lookup material. Use the [Use CALM](../use/projects.md) chapters for normal operation sequences and the [Understand](../understand/surface-models.md) chapters for scientific interpretation.

### How to read exact signatures

Generated signatures are taken from the installed CALM source. They define accepted parameter names, keyword-only boundaries, annotations, and defaults.

A signature answers questions such as:

- Which arguments are required?
- Which settings have defaults?
- What object is returned?
- Which public exception may be raised?

A signature does **not** decide whether a value is scientifically appropriate. For example, `max_principal_strain` accepts a numerical limit, but the suitable limit depends on the material system and modeling purpose. The workflow and scientific chapters own that interpretation.

### Returned collections and table views

Many returned objects support a common inspection vocabulary:

- `where(...)` filters a collection;
- `get(...)` requires exactly one match;
- `one_or_none(...)` permits no match;
- `latest(...)` selects the most recently created matching result;
- `available_views()` lists named table views;
- `to_rows()`, `to_table()`, `to_dataframe()`, and `write_table()` expose the selected view.

```python
candidates = project.search("cu-ni-100").candidates()
print(candidates.available_views())
rows = candidates.to_rows(view="summary")
```

The [Returned objects and tables](api/returned-objects.md) page lists stable public fields for each named view. Implementation metadata is intentionally omitted.

### Exceptions and recovery

Catch the narrowest public exception that corresponds to an action your program can take:

```python
try:
    material = project.material("Cu")
except calm.AmbiguousProjectQueryError as exc:
    print(exc)
```

The exception reference links each class to the workflow or troubleshooting page that explains the appropriate recovery. Do not catch broad exceptions merely to suppress an unexplained scientific or project-state failure.

### Supported boundary

The public API consists of:

- top-level names deliberately exported by `calm`;
- documented operations on `calm.Project`;
- curated operations and attributes on objects returned by those workflows; and
- documented table views and utility functions.

Names absent from this reference may change without notice. File layouts inside a project, implementation classes, and package submodules are not user interfaces.

## Related workflow

- [Projects](../use/projects.md) explains the project lifecycle, names, identifiers, lineage, and compatibility boundary.
- [Materials](../use/materials.md) explains structure and calculator inputs.
- [Searches and candidates](../use/searches.md) explains search settings and candidate collections.
- [Relax and evaluate](../use/relax-evaluate.md) explains relaxation, energies, references, and result objects.
- [Datasets and campaigns](../use/datasets-campaigns.md) explains advanced declarations and returned results.
