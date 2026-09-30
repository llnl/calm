# CALM Basic API Reference

# Chapter 21 — MatchSearchResult

## Overview

`MatchSearchResult` is an abstraction returned by `MatchesCollection.search(...)`.

It represents the outcome of a single lattice matching search, exposing both
the persisted `Match` objects produced by the search and search-level
reporting helpers.

`MatchSearchResult` is lightweight and iterable; it supports selection,
ranking, plotting, and export helpers that operate on the search outcome.

---

## Construction

Returned by `project.matches.search(...)`.

Users do not construct `MatchSearchResult` directly.

---

## Properties

### `matches`

Type

```python
list[Match]
```

Persisted `Match` objects created by the search.

---

### `metadata`

Type

```python
dict
```

Search-level metadata (parameters, execution time, summary diagnostics).

---

## Methods

### `plot_pareto`

Signature

```python
plot_pareto(save=None) -> Figure
```

Produces a Pareto plot for the search result. If `save` is `None`, returns
an in-memory figure object; if `save` is a path, writes the figure to the
provided destination (defaulting to the project's artifact root when
`save=None` is omitted at the collection/export layer).

---

### `export`

Signature

```python
export(destination=None, format=None)
```

Exports search summaries (tables, plots) to `destination`. If `destination`
is `None`, the Basic API writes outputs to the project's default artifact
root (`CALM_results/`).

---

### Iteration & Selection

`MatchSearchResult` implements iteration and basic selection helpers such as
`top(n)` and `filter(...)` that return sub-views referencing the persisted
`Match` objects.

---

## Example

```python
results = project.matches.search(film=film, substrate=substrate)
results.plot_pareto(save=project.artifacts.root()/"pareto.png")
results.export()  # writes to CALM_results/ by default
```
