# CALM Basic API Specification

# Chapter 11 — Query Language

## Purpose

This chapter defines the common query language for the CALM Basic API.

The objective is to ensure that every scientific collection can be
searched in a consistent, discoverable manner. Users should not need to
learn a different query interface for every collection.

The query language is intentionally scientific rather than
implementation-oriented.

---

# 1. Design Goals

The query language shall:

- use scientific terminology;
- be consistent across every collection;
- support simple and expressive queries;
- hide persistence implementation details;
- return scientific objects rather than database records.

---

# 2. Fundamental Query Operations

Every collection shall support two complementary retrieval methods.

## `get(...)`

Retrieves exactly one persisted object.

Examples:

```python
material = project.materials.get("LiF")

surface = project.surfaces.get(surface_id)

match = project.matches.get(match_id)
```

If no object exists, the operation shall report that condition using the
Basic API error semantics defined elsewhere.

---

## `find(...)`

Returns zero or more objects satisfying scientific search criteria.

Examples:

```python
project.materials.find(...)

project.surfaces.find(...)

project.matches.find(...)

project.interfaces.find(...)
```

Unlike `get(...)`, `find(...)` always returns a collection of scientific
objects.

---

# 3. Query Semantics

Queries should be expressed using scientific properties rather than
implementation identifiers.

Examples include:

- material name,
- chemical composition,
- crystal system,
- Miller orientation,
- lattice strain,
- interface area,
- convergence status.

Users should not be required to query database fields directly.

---

# 4. Collection-Specific Query Criteria

Each collection defines its own scientific query vocabulary.

## Materials

Typical criteria include:

- name,
- composition,
- space group,
- crystal system,
- label.

---

## Surfaces

Typical criteria include:

- parent material,
- Miller index,
- termination,
- polarity,
- slab thickness.

---

## Matches

Typical criteria include:

- film,
- substrate,
- lattice strain,
- interface area,
- orientation relationship.

---

## Interfaces

Typical criteria include:

- parent match,
- constituent materials,
- interface area,
- strain partitioning,
- registry state.

---

## Relaxations

Typical criteria include:

- parent interface,
- convergence status,
- optimizer,
- calculator,
- completion status.

---

## Analyses

Typical criteria include:

- analysis type,
- parent object,
- constituent materials,
- calculation method.

---

## Datasets

Typical criteria include:

- included materials,
- included analyses,
- campaign,
- publication label.

---

## Campaigns

Typical criteria include:

- campaign name,
- status,
- material system,
- workflow stage,
- completion date.

---

# 5. Query Composition

Queries should support combining multiple scientific criteria.

Example:

```python
project.surfaces.find(
    material="LiF",
    miller=(1, 0, 0),
    termination="stoichiometric",
)
```

Another example:

```python
project.matches.find(
    film="LiF",
    substrate="Li2O",
    max_strain=0.05,
)
```

The exact syntax for expressing logical combinations is implementation
dependent but should remain consistent throughout the Basic API.

---

# 6. Returned Objects

Queries shall return scientific objects.

For example:

```python
surfaces = project.surfaces.find(...)

for surface in surfaces:
    ...
```

The Basic API shall not require users to manipulate database rows,
primary keys, or persistence records.

## 10. Retrieving persisted results and reporting

The Project exposes persisted scientific objects through its collections.
Users reopen a Project via `Project.open(path)` and discover previously
generated objects using `list(...)`, `get(...)`, and `find(...)` on the
appropriate collection. Users should never need to access database tables or
implementation-specific identifiers to find previously created scientific
objects.

Reporting artifacts such as tables, plots, and reports are produced either by
collection/search-result convenience methods (e.g., `plot_pareto()` on a
search result) or by calling `export(...)` with an explicit destination. When
no explicit destination is supplied, the Basic API writes artifacts to the
project's default artifact root (`CALM_results/` inside the project directory)
and Project helpers may be used to discover these outputs.

Typical retrieval workflow after reopening a project:

```python
project = Project.open("my_project.calm")
matches = project.matches.find(film=surface)
fig = matches.plot_pareto(save=None)  # returns a figure object
project.matches.export(matches, destination=None)  # writes to CALM_results/ by default
```

---

# 7. Ordering

Collections should define predictable ordering for query results.

Unless otherwise requested, results should be ordered using the most
natural scientific ordering for that collection.

Examples include:

- alphabetical material names,
- increasing Miller index,
- increasing lattice strain,
- increasing interface energy,
- chronological execution time.

Collections may provide optional sorting criteria where scientifically
appropriate.

---

# 8. Scientific Questions

The query language enables users to answer questions such as:

- Which materials satisfy these criteria?
- Which surfaces have already been generated?
- Which interface matches are Pareto optimal?
- Which interfaces have been relaxed?
- Which calculations failed?
- Which datasets include a given material?

---

# 9. Design Rationale

The query language is intentionally scientific rather than relational.

Scientists should formulate questions in terms of:

- materials,
- surfaces,
- interfaces,
- scientific properties,

rather than:

- tables,
- rows,
- joins,
- database identifiers.

A consistent query interface across all collections minimizes cognitive
load and makes the Basic API easier to learn.

---

# Summary

The Basic API query language provides a uniform mechanism for retrieving
scientific objects from every collection.

By standardizing `get(...)` and `find(...)` while allowing each
collection to define its own scientific search vocabulary, the Basic API
supports expressive scientific workflows without exposing persistence
implementation details.

The next chapter specifies **Object Identity**, defining how persisted
scientific objects are uniquely identified and referenced throughout the
Basic API.
