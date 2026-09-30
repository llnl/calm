# CALM Basic API Reference

# Chapter 7 — MatchesCollection

## Overview

`MatchesCollection` is the public interface for discovering,
retrieving, querying, visualizing, exporting, and deleting interface
matches between persisted surface models.

It owns every persisted `Match` object.

Unlike most collections, the primary scientific operation is
`search(...)` rather than `generate(...)`.

`MatchesCollection` is accessed through:

```python
project.matches
```

---

# Purpose

The Matches Collection performs crystallographic lattice matching between
previously generated Surface objects.

It supports:

- lattice matching,
- exploratory analysis,
- retrieval,
- querying,
- visualization,
- export.

It does **not** construct atomistic interface structures.

---

# Methods

## `search`

### Signature

```python
search(
    *,
    film,
    substrate,
    max_strain=None,
    max_area=None,
    angle_tolerance=None,
    metadata=None,
) -> MatchSearchResult
```

### Description

Performs a lattice matching search between two persisted Surface
objects.

The search returns a `MatchSearchResult` that references zero or more
persisted `Match` objects created during the search.  The `MatchSearchResult`
carries search-level metadata (parameters, timing, summary diagnostics) and
provides convenience methods for ranking, Pareto selection, plotting, and
exporting search summaries.  When no matches are found the result is empty;
an empty result is a valid scientific outcome rather than an error.

Every identified match that meets the search constraints is persisted within
the Project prior to the successful completion of the search operation.

The parent Surface objects are never modified.

---

### Parameters

#### `film`

Type

```python
Surface
```

Film surface.

---

#### `substrate`

Type

```python
Surface
```

Substrate surface.

---

#### `max_strain`

Type

```python
float | None
```

Maximum allowable lattice strain.

---

#### `max_area`

Type

```python
float | None
```

Maximum interface supercell area.

---

#### `angle_tolerance`

Type

```python
float | None
```

Angular tolerance used during matching.

---

#### `metadata`

Optional user metadata.

---

### Returns

```python
MatchSearchResult
```

A search-result abstraction exposing persisted `Match` objects and search-level reporting helpers.

---

### Side Effects

Creates zero or more persisted `Match` objects and records the search metadata in the project's provenance records.

---

### Raises

- `ObjectNotFoundError`
- `SearchError`
- `InvalidSurfaceError`

---

## Example

```python
results = project.matches.search(
    film=film,
    substrate=substrate,
)
```

---

## `list`

### Signature

```python
list() -> list[Match]
```

### Description

Returns every persisted Match contained within the Project.

---

## Example

```python
matches = project.matches.list()
```

---

## `get`

### Signature

```python
get(
    identifier,
) -> Match
```

### Description

Retrieves exactly one persisted Match.

---

### Returns

```python
Match
```

---

### Raises

- `ObjectNotFoundError`

---

## Example

```python
match = project.matches.get(
    match_id,
)
```

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Match]
```

### Description

Returns every Match satisfying scientific search criteria.

---

### Supported Criteria

Examples include:

- film,
- substrate,
- strain,
- interface area,
- Miller orientation,
- orientation relationship.

---

## Example

```python
matches = project.matches.find(
    max_strain=0.05,
)
```

---

## `plot_pareto`

### Signature

```python
plot_pareto(
    matches=None,
)
```

### Description

Generates a Pareto plot for persisted Match objects.

If `matches` is omitted, all persisted matches are included.

---

## Example

```python
project.matches.plot_pareto()
```

---

## `export`

### Signature

```python
export(
    matches,
    destination,
    *,
    format=None,
)
```

### Description

Exports one or more Match objects.

Typical outputs include:

- CSV,
- JSON,
- summary tables.

Export never modifies persisted Match objects.

---

## Example

```python
project.matches.export(
    matches,
    "matches.csv",
)
```

---

## `delete`

### Signature

```python
delete(
    match,
)
```

### Description

Removes one persisted Match from the Project.

Deletion follows the dependency rules defined by the Basic API.

---

## Example

```python
project.matches.delete(
    match,
)
```

---

# Collection Properties

`MatchesCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Perform a lattice matching search

```python
results = project.matches.search(
    film=film,
    substrate=substrate,
)
```

---

## Retrieve one Match

```python
match = project.matches.get(
    match_id,
)
```

---

## Query Matches

```python
matches = project.matches.find(
    film=film,
    max_strain=0.03,
)
```

---

## Generate a Pareto plot

```python
project.matches.plot_pareto()
```

---

## Export summary table

```python
project.matches.export(
    matches,
    "matches.csv",
)
```

---

# Design Notes

Unlike every previous collection, the primary scientific activity is a
**search** rather than deterministic generation.

This distinction is intentional.

Scientists search for crystallographic relationships between two surface
models. The search may produce:

- zero matches,
- one match,
- many matches.

The resulting Match objects become persisted scientific objects that are
subsequently consumed by the Interfaces Collection.

---

# See Also

- `Project`
- `Surface`
- `Match`
- `InterfacesCollection`
```
