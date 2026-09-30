# CandidateCollection demo

`CandidateCollection` provides a lightweight public facade for querying and
filtering interface candidates after a search or from a project-backed store. It
supports table export, Pareto selection, strain and metadata filters, and bulk
interface-building calls.

This tutorial historically referenced a companion script. For the current
runnable example scripts, consult the Example Scripts guide:
`docs/guides/examples/index.md`.

## Highlights

- Construct a `CandidateCollection` from prototype-like objects or from a
  workspace via `project.candidates()`.
- Chain filters such as `materials(...)`, `miller_pair(...)`, `tags(...)`, and
  `terminations(...)`.
- Compute Pareto-optimal subsets with `pareto()` and select top candidates per
  surface pair with `select(n_per_pair=...)`.
- Build selected candidates in bulk with `build_all(...)` when the wrapped
  prototype objects provide a `build(...)` method.

## Minimal usage

```python
from calm.public.candidate_collections import CandidateCollection

# `prototypes` is a list of prototype-like objects. Each object should provide
# `to_dict()` and may optionally provide `build()`.
candidates = CandidateCollection(prototypes=prototypes)

selected = candidates.materials("LiF", "Li2O").pareto().select(n_per_pair=1)
rows = selected.to_rows(view="strain")
interfaces = selected.build_all(gap=1.5, vacuum=12.0)
```

## Run the example

This tutorial is documentation-first. Consult the Example Scripts guide for
the current runnable scripts: `docs/guides/examples/index.md`.

The script writes:

```text
candidate_collection_rows.csv
candidate_collection_built_interfaces.csv
```

## Project-backed queries

Persistent campaigns can use the same collection facade through a project or
workspace query object:

```python
from calm import open_project

project = open_project("my_run.calm")
candidates = project.candidates()
rows = candidates.pareto().to_rows(view="strain")
```

## Notes

The collection facade is intended for readable public workflows. For advanced
production pipelines, users may still prefer to select prototypes by UID, pass a
full internal build configuration, and persist built interfaces through explicit
workspace mutation APIs.
