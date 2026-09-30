# CALM Basic API Reference

# Chapter 15 — DatasetsCollection

## Overview

`DatasetsCollection` is the public interface for assembling,
retrieving, querying, exporting, and deleting scientific datasets.

It owns every persisted `Dataset` object.

Unlike previous collections, the Datasets Collection does not create new
scientific results. Instead, it packages previously generated
scientific objects into reproducible datasets suitable for sharing,
publication, benchmarking, and machine learning.

`DatasetsCollection` is accessed through:

```python
project.datasets
```

---

# Purpose

The Datasets Collection is responsible for organizing scientific
results into reusable collections.

It supports:

- dataset assembly,
- retrieval,
- querying,
- export,
- lifecycle management.

It does **not** perform:

- scientific computation,
- structural generation,
- workflow execution.

---

# Methods

## Dataset creation and persistence

Datasets are typically assembled from built interface models produced by
search/build/refinement pipelines and persisted via the Project facade. The
canonical public workflows to assemble and persist datasets are:

- assemble a dataset from a selection/collection of InterfaceModel objects:

```python
dataset = candidate_collection.build_dataset(name="my_ds", gap=1.5, vacuum=15.0)
```

- persist the dataset into the project sidecar (authoritative persistence when
  the workspace supports it) using the public saver:

```python
proj.save(dataset, name="my_ds", campaign_uid_full="campaign:abc:1", campaign_run_uid_full="campaign_run:xyz:1")
```

The `project.datasets()` collection is a query/export surface for persisted
datasets. A `project.datasets.create(...)` object-model helper is currently
aspirational and deferred until the project-backed contract is stabilized.

---

### Parameters

Each parameter accepts one or more persisted scientific objects.

Any omitted category is simply excluded from the Dataset.

---

### Returns

```python
Dataset
```

The newly created Dataset.

---

### Side Effects

Creates one persisted Dataset.

Updates project provenance.

---

### Raises

- `DatasetCreationError`
- `ObjectNotFoundError`

---

## Example

```python
dataset = project.datasets.create(
    analyses=[
        interface_energy,
        adhesion_energy,
    ],
)
```

---

## `list`

### Signature

```python
list() -> list[Dataset]
```

Returns every persisted Dataset.

---

## `get`

### Signature

```python
get(
    identifier,
) -> Dataset
```

Retrieves one persisted Dataset.

---

## `find`

### Signature

```python
find(
    **criteria,
) -> list[Dataset]
```

Returns Datasets satisfying scientific criteria.

Typical criteria include:

- material system,
- included analyses,
- publication,
- campaign,
- tags.

---

## Example

```python
datasets = project.datasets.find(
    publication="LiF–Li₂O Study",
)
```

---

## `export`

### Signature

```python
export(
    dataset,
    destination,
    *,
    format=None,
)
```

### Description

Exports a Dataset.

Supported formats may include:

- archive bundles,
- benchmark datasets,
- machine learning datasets,
- publication supplements.

Export preserves:

- provenance,
- metadata,
- scientific relationships.

---

## Example

```python
project.datasets.export(
    dataset,
    "dataset.zip",
)
```

---

## `delete`

### Signature

```python
delete(
    dataset,
)
```

Removes one persisted Dataset.

Deleting a Dataset never removes the underlying scientific objects.

---

# Collection Properties

`DatasetsCollection` intentionally exposes no public properties.

Its public interface consists entirely of collection operations.

---

# Examples

## Create a Dataset

```python
dataset = project.datasets.create(
    analyses=project.analyses.list(),
)
```

---

## Retrieve a Dataset

```python
dataset = project.datasets.get(
    dataset_id,
)
```

---

## Export a Dataset

```python
project.datasets.export(
    dataset,
    "publication_dataset.zip",
)
```

---

# Design Notes

Datasets are aggregations of existing scientific objects.

They are intentionally separate from computational workflows.

A Dataset never owns the scientific objects it contains.

Instead, it records references to those objects together with sufficient
metadata to reproduce or distribute the scientific investigation.

This separation allows multiple Datasets to reuse the same scientific
objects without duplication.

---

# See Also

- `Project`
- `Dataset`
- `CampaignsCollection`
- `Analysis`
- `AnalysesCollection`
