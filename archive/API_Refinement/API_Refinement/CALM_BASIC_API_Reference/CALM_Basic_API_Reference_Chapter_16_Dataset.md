# CALM Basic API Reference

# Chapter 16 — Dataset

## Overview

`Dataset` represents a persisted collection of scientific objects that
have been intentionally assembled for a particular purpose.

Unlike previous scientific objects, a Dataset does not represent a new
physical structure or scientific calculation.

Instead, it represents a reproducible collection of scientific results
together with sufficient metadata to support:

- publication,
- data sharing,
- benchmarking,
- machine learning,
- long-term archival.

Dataset objects are created by the `DatasetsCollection` and retrieved
from the Project rather than instantiated directly by users.

---

# Construction

Dataset objects are not constructed directly.

They are created through the Datasets Collection.

Example:

```python
dataset = project.datasets.create(
    analyses=[
        interface_energy,
        adhesion_energy,
    ],
)
```

---

# Properties

## `id`

Type

```python
ObjectId
```

Persistent scientific identity.

Read-only.

---

## `name`

Type

```python
str
```

Human-readable dataset name.

Read-only.

---

## `materials`

Type

```python
list[Material]
```

Materials included in the Dataset.

Read-only.

---

## `surfaces`

Type

```python
list[Surface]
```

Surface models included in the Dataset.

Read-only.

---

## `matches`

Type

```python
list[Match]
```

Interface matches included in the Dataset.

Read-only.

---

## `interfaces`

Type

```python
list[Interface]
```

Interface structures included in the Dataset.

Read-only.

---

## `relaxations`

Type

```python
list[Relaxation]
```

Relaxations included in the Dataset.

Read-only.

---

## `analyses`

Type

```python
list[Analysis]
```

Scientific analyses included in the Dataset.

Read-only.

---

## `metadata`

Type

```python
Metadata
```

Dataset metadata.

Typical examples include:

- title,
- authors,
- description,
- publication,
- license,
- keywords,
- version.

Read-only.

---

## `project`

Type

```python
Project
```

Owning Project.

Read-only.

---

# Relationships

A Dataset references scientific objects.

It never owns them.

Typical relationships include:

```python
dataset.materials

dataset.interfaces

dataset.relaxations

dataset.analyses
```

All relationships are read-only.

---

# Methods

Datasets intentionally expose very few public methods.

Dataset construction belongs to the
`DatasetsCollection`.

---

## `export`

### Signature

```python
export(
    destination,
    *,
    format=None,
)
```

### Description

Convenience wrapper for

```python
project.datasets.export(
    self,
    destination,
)
```

Export preserves:

- metadata,
- provenance,
- scientific relationships.

The Dataset is never modified.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise summary of the Dataset.

Typical information includes:

- number of Materials,
- number of Interfaces,
- number of Relaxations,
- number of Analyses,
- publication metadata.

---

# Immutability

Datasets are immutable.

A Dataset represents a curated scientific deliverable.

Changes to the contents of a Dataset produce a new Dataset rather than
modifying the existing one.

This guarantees that exported datasets remain reproducible.

---

# Equality

Two Dataset objects are equal if they represent the same persisted
scientific object.

Example:

```python
dataset_a == dataset_b
```

evaluates scientific identity.

---

# Scientific Questions

A Dataset enables users to answer questions such as:

- Which scientific objects belong to this dataset?
- Is this dataset complete?
- Is the dataset reproducible?
- Is it suitable for publication?
- Can it be exported for machine learning?

---

# Examples

## Retrieve a Dataset

```python
dataset = project.datasets.get(
    dataset_id,
)
```

---

## Inspect contents

```python
print(dataset.materials)

print(dataset.interfaces)

print(dataset.analyses)
```

---

## Export

```python
dataset.export(
    "publication_dataset.zip",
)
```

---

# Design Notes

A Dataset is a scientific deliverable.

Unlike every previous scientific object, it does not represent a stage
of computation.

Instead, it records a curated collection of scientific results together
with the metadata necessary to reproduce or distribute those results.

By treating datasets as first-class objects, the Basic API makes
publication, benchmarking, and machine learning workflows natural
extensions of the scientific workflow rather than external post-
processing steps.

---

# See Also

- `Project`
- `DatasetsCollection`
- `Campaign`
- `CampaignsCollection`
- `Analysis`
```
