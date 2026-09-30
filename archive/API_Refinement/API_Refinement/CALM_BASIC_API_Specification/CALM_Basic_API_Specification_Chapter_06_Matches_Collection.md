# CALM Basic API Specification

# Chapter 06 — Matches Collection

## Purpose

The Matches Collection is the public interface for discovering, managing,
retrieving, querying, and exporting coherent interface matches between
persisted surface models.

It is the canonical owner of every persisted `Match` object and represents
the transition from independent surface models to candidate interface
relationships.

The Matches Collection is responsible for performing lattice matching
searches and managing the resulting interface matches. It is not responsible
for constructing interface structures.

---

# 1. Scientific Object

The Matches Collection owns the following public scientific object.

```text
Match
```

A `Match` represents a crystallographic relationship between two persisted
surface models together with the metadata required to reproduce that
relationship.

A `Match` is not an interface structure.

It is a description of how two surfaces may be combined.

---

# 2. Collection Ownership

The Matches Collection is accessed through the project.

```python
project.matches
```

Every persisted `Match` belongs to exactly one project.

Every match has exactly two parent surfaces:

- film surface,
- substrate surface.

---

# 3. Lifecycle Responsibilities

The Matches Collection is responsible for:

- performing lattice matching searches,
- generating persisted matches,
- retrieving persisted matches,
- querying matches,
- filtering matches,
- exporting match summaries,
- generating exploratory visualizations,
- deleting matches.

The Matches Collection does **not**:

- construct interface structures,
- optimize interface registries,
- perform structural relaxations,
- compute interface energetics.

Those responsibilities belong to downstream collections.

---

# 4. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Matches are derived scientific objects. |
| `create(...)` | ✗ | Matches are produced through lattice matching. |
| `generate(...)` | ✗ | Matching is expressed as a scientific search. |
| `search(...)` | ✓ | Perform lattice matching. Returns a `MatchSearchResult` abstraction referencing persisted `Match` objects created by the search. |
| `list(...)` | ✓ | Enumerate persisted matches. |
| `get(...)` | ✓ | Retrieve one persisted match. |
| `find(...)` | ✓ | Query matches using scientific criteria. |
| `export(...)` | ✓ | Export match summaries. |
| `delete(...)` | ✓ | Remove persisted matches. |

---

# 5. Behavioral Contract

## `search(...)`

Performs a lattice matching search between two persisted surface models.

Inputs include:

- film surface,
- substrate surface,
- matching tolerances,
- search parameters.

The search shall produce zero or more persisted `Match` objects and return a
`MatchSearchResult` abstraction that references the persisted matches and
contains search-level metadata (e.g., search parameters, execution time,
pagination, summary statistics).  When no matches are found the result is an
empty `MatchSearchResult` (an empty result is a valid scientific outcome,
not an error).

The parent surfaces shall never be modified.

---

## `list(...)`

Returns all persisted matches stored within the project.

---

## `get(...)`

Returns one persisted match.

---

## `find(...)`

Returns matches satisfying scientific search criteria.

Typical criteria include:

- film material,
- substrate material,
- Miller orientations,
- lattice strain,
- interface area,
- orientation relationship.

---

## `export(...)`

Exports persisted match summaries.

Supported outputs may include:

- tabulated results,
- CSV,
- JSON,
- other structured summary formats.

---

## `delete(...)`

Removes persisted matches while respecting project provenance.

---


# 6. Exploratory Analysis and Reporting

The Matches Collection is the first workflow stage intended primarily for
scientific exploration.  Accordingly, the collection and its `MatchSearchResult`
abstraction shall expose visualization and ranking capabilities and provide
stable table/export helpers for common reporting tasks.

Preferred locations for reporting functionality:

- Search-specific visualizations and traceable summaries (e.g., per-search
  Pareto plots, ranking tables, search metadata) belong on the `MatchSearchResult`.
- Collection-wide summaries and cross-search exports (e.g., global match
  summaries, persistent match tables) belong on `MatchesCollection`.

Typical reporting features include:

- Pareto plots (search-scoped and collection-scoped),
- summary tables (CSV/JSON),
- ranking by scientific metrics,
- filtering and selection helpers for export/build workflows.

All reporting helpers should be implemented so that their outputs can be
written via `export(...)` to an explicit destination or to the project's
default artifact root (`CALM_results/`) when no destination is supplied.

---

# 7. Object Relationships

Every match is derived from exactly two persisted surfaces.

```text
Material
    ↓
Surface
      ↘
        Match
      ↗
Surface
```

Every interface constructed later references exactly one match.

```text
Match
    ↓
Interface
```

---

# 8. Scientific Questions

The Matches Collection enables users to answer questions such as:

- Which interface relationships are possible?
- Which interfaces minimize lattice strain?
- Which interfaces minimize interface area?
- Which candidates are Pareto optimal?
- Which orientation relationships are most favorable?
- How many viable interface matches exist?

---

# 9. Example Workflow

```python
project = Project.open("lif_li2o")

film = project.surfaces.get("LiF (100)")
substrate = project.surfaces.get("Li2O (100)")

search = project.matches.search(
    film=film,
    substrate=substrate,
)

matches = search.results()

matches.plot_pareto()

matches.export("matches.csv")
```

---

# 10. Design Rationale

Unlike previous collections, the primary operation is not
`generate(...)` but `search(...)`.

This distinction reflects the underlying scientific activity.

Scientists perform a search over possible crystallographic
relationships rather than deterministically generating a single object.

The resulting matches become persisted scientific objects that support
subsequent interface construction workflows.

---

# Summary

The Matches Collection owns every persisted `Match` object and provides
the public interface for lattice matching and exploratory analysis.

By representing interface matching as a first-class collection, the
Basic API exposes one of the central scientific workflows in CALM through
a cohesive, discoverable interface while preserving the project-centered
object lifecycle.

The next chapter specifies the **Interfaces Collection**, which consumes
persisted `Match` objects to construct explicit atomistic interface
structures.
