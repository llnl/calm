# CALM Basic API Reference

# Chapter 13 — AnalysesCollection

## Overview

`AnalysesCollection` is the public interface for computing,
retrieving, comparing, querying, exporting, and deleting derived
scientific analyses.

It owns every persisted `Analysis` object.

Analyses are derived from previously generated scientific objects,
typically `Relaxation` objects, although some analyses may operate
directly on `Interface`, `Surface`, or `Material` objects.

`AnalysesCollection` is accessed through:

```python
project.analyses
```

---

# Purpose

The Analyses Collection is responsible for transforming computational
results into scientific knowledge.

It supports:

- scientific analysis,
- comparison,
- retrieval,
- querying,
- export,
- lifecycle management.

It does **not**:

- execute atomistic simulations,
- modify parent scientific objects,
- construct interfaces.

---

# Methods

## `run`

### Signature

```python
run(
    analysis,
    *objects,
    metadata=None,
    **parameters,
) -> Analysis
```

### Description

Executes a scientific analysis using one or more persisted scientific
objects.

The parent objects are never modified.

---

### Parameters

#### `analysis`

Type

```python
AnalysisType
```

The analysis to perform.

Examples include:

- `interface_energy`
- `adhesion_energy`
- `strain_analysis`
- `bonding_analysis`
- `charge_analysis`

---

#### `objects`

One or more persisted scientific objects.

Accepted object types depend on the requested analysis.

---

#### `metadata`

Optional user-defined metadata.

---

#### `parameters`

Analysis-specific keyword arguments.

---

### Returns

```python
Analysis
```

A newly persisted Analysis.

---

### Side Effects

Creates one persisted Analysis.

Updates project provenance.

---

### Raises

- `ObjectNotFoundError`
- `InvalidAnalysisError`
- `AnalysisError`

---

## Example

```python
analysis = project.analyses.run(
    interface_energy,
    relaxation,
)
```

---

## `compare`

### Signature

```python
compare(
    *objects,
    analysis=None,
) -> Analysis
```

### Description

Performs comparative analysis between multiple scientific objects.

Typical comparisons include:

- multiple Interfaces,
- multiple Relaxations,
- multiple Analyses.

---

### Returns

```python
Analysis
```

A persisted comparative Analysis.

---

## Example

```python
comparison = project.analyses.compare(
    relaxation1,
    relaxation2,
)
```

---

## `list`

### Signature

```python
list() -> list[Analysis]
```

Returns every persisted Analysis.

---

## `get`

### Signature

```python
get(
    identifier,
) -> Analysis
```

Retrieves one persisted Analysis.

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Analysis]
```

Returns Analyses satisfying scientific criteria.

Supported criteria include:

- analysis type,
- parent object,
- material,
- interface,
- calculator,
- tags.

---

## Example

```python
energies = project.analyses.find(
    type="interface_energy",
)
```

---

## `export`

### Signature

```python
export(
    analysis,
    destination,
    *,
    format=None,
)
```

### Description

Exports one Analysis.

Supported formats may include:

- CSV,
- JSON,
- figures,
- publication tables,
- reports.

Export never modifies the Analysis.

---

## Example

```python
project.analyses.export(
    analysis,
    "analysis.csv",
)
```

---

## `delete`

### Signature

```python
delete(
    analysis,
)
```

Removes one persisted Analysis.

Deletion follows the dependency rules defined by the Basic API.

---

# Collection Properties

`AnalysesCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Compute interface energy

```python
energy = project.analyses.run(
    interface_energy,
    relaxation,
)
```

---

## Compare two Relaxations

```python
comparison = project.analyses.compare(
    relaxation1,
    relaxation2,
)
```

---

## Retrieve an Analysis

```python
analysis = project.analyses.get(
    analysis_id,
)
```

---

## Query analyses

```python
energies = project.analyses.find(
    type="interface_energy",
)
```

---

## Export an Analysis

```python
project.analyses.export(
    analysis,
    "analysis.csv",
)
```

---

# Design Notes

Unlike previous collections, the Analyses Collection performs
interpretive scientific operations rather than structural
transformations.

Its primary responsibility is to compute derived scientific quantities
from existing project objects.

Because analyses are reproducible and non-destructive, multiple analyses
may legitimately be performed on the same scientific object without
creating ambiguity in the project provenance graph.

Analyses are intentionally represented as first-class persisted objects
so that scientific interpretation becomes reproducible, queryable,
comparable, and shareable.

---

# See Also

- `Project`
- `Relaxation`
- `Analysis`
- `RelaxationsCollection`
- `DatasetsCollection`
```
