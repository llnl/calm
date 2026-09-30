# CALM Basic API User Guide

# Chapter 8 — Datasets

## Scientific Objective

At this stage of the workflow you have completed the scientific
investigation.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,
- Atomistic Interfaces,
- Structural Relaxations,
- Scientific Analyses.

The next step is to organize those scientific results into a reusable
Dataset suitable for publication, benchmarking, data sharing, and
machine learning.

By the end of this chapter you will be able to:

- assemble a Dataset,
- retrieve persisted Datasets,
- query existing Datasets,
- inspect Dataset contents,
- export a complete scientific Dataset.

---

## Workflow

### Assemble a Dataset

Create a Dataset from the scientific objects generated throughout the
workflow.

```python
dataset = project.datasets.create(
    materials=project.materials.list(),
    surfaces=project.surfaces.list(),
    matches=project.matches.list(),
    interfaces=project.interfaces.list(),
    relaxations=project.relaxations.list(),
    analyses=project.analyses.list(),
)
```

The Dataset becomes a persisted scientific object within the Project.

The source objects remain unchanged.

---

### Retrieve a Dataset

Previously assembled Datasets can be retrieved directly from the
Project.

```python
dataset = project.datasets.get(
    dataset_id,
)
```

Datasets should always be retrieved rather than recreated.

---

### Query Datasets

Locate Datasets using scientific criteria.

```python
datasets = project.datasets.find(
    publication="LiF–Li₂O Interface Study",
)
```

or

```python
datasets = project.datasets.find(
    material="LiF",
)
```

Queries return persisted Dataset objects.

---

### Inspect Dataset Contents

Every Dataset exposes the scientific objects that it contains.

```python
print(dataset.materials)

print(dataset.interfaces)

print(dataset.relaxations)

print(dataset.analyses)
```

These relationships allow users to understand exactly which scientific
objects belong to the Dataset.

---

### Export a Dataset

Export the Dataset for external use.

```python
dataset.export(
    "lif_li2o_dataset.zip",
)
```

or

```python
project.datasets.export(
    dataset,
    "lif_li2o_dataset.zip",
)
```

The exported Dataset preserves:

- scientific objects,
- metadata,
- provenance,
- scientific relationships.

The persisted Dataset remains unchanged.

---

## Discussion

A Dataset represents the scientific deliverable produced by an
investigation.

Unlike previous workflow stages, assembling a Dataset does not perform
new scientific calculations.

Instead, it records a curated collection of previously generated
scientific objects.

The object lifecycle therefore becomes:

```text
Materials
      ↓
Surfaces
      ↓
Matches
      ↓
Interfaces
      ↓
Relaxations
      ↓
Analyses
      ↓
Dataset
```

The Dataset preserves every scientific relationship established during
the investigation.

Because the Dataset references existing scientific objects rather than
copying them, provenance remains complete while duplication is avoided.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Scientific objects can be assembled into a Dataset | ✓ |
| Datasets become persisted scientific objects | ✓ |
| Datasets can be retrieved | ✓ |
| Datasets can be queried | ✓ |
| Dataset contents are directly accessible | ✓ |
| Datasets can be exported | ✓ |
| Dataset export preserves provenance | ✓ |
| Scientific objects are referenced rather than duplicated | ✓ |

---

## Summary

In this chapter you assembled the results of the scientific
investigation into a reproducible Dataset.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,
- Atomistic Interfaces,
- Structural Relaxations,
- Scientific Analyses,
- Datasets,

with complete provenance linking every scientific object throughout the
entire workflow.

The scientific investigation is now reproducible, shareable, and ready
for publication or machine learning.

In the next chapter you will learn how Campaigns organize and coordinate
larger computational studies involving many related scientific
workflows.
