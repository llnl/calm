# Example Scripts

The repository includes runnable example scripts under `examples/`.

These scripts are source files in the repository, not MkDocs pages. Use them
as copyable starting points for local workflows. Some scripts depend on the
outputs of earlier examples and some require optional scientific dependencies.

## Current example sequence (canonical inventory)

| Script | Purpose | Notes |
|---|---|---|
| `examples/01_revised_example_1.py` | Introductory public workflow example | Project setup, material import, optimization, export |
| `examples/02_reopen_and_generate_surfaces.py` | Reopen a project/workspace and generate surfaces | Re-opens workspace created in Example 01 |
| `examples/03_match_interfaces.py` | Match interfaces from generated surfaces | Produces candidate tables and plots |
| `examples/04_compare_interface_searches.py` | Compare interface-search results | Comparison/analysis of search runs |
| `examples/05_build_interfaces.py` | Build selected interfaces | Builds and writes interface structure files |
| `examples/06_strain_partition_and_registry_search.py` | Strain partitioning and registry search demo | Advanced workflow; may need optional deps |

## Running examples

Run examples from the repository root. Example scripts may require optional
dependencies and input files. Inspect the script docstring/header for
requirements before running:

```bash
python examples/01_revised_example_1.py
```

## Relationship to tutorials

Tutorials are explanatory learning documents and may include code snippets and
conceptual discussions. The example scripts are runnable end-to-end scripts and
are listed above as the canonical inventory. Tutorials point to this page for
current runnable scripts rather than linking directly to repository-root paths.
