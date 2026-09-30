# CALM Basic API Specification

# Chapter 10 — Datasets and Campaigns Collections

## Purpose

The Datasets and Campaigns Collections provide the public interface for
organizing large scientific investigations, packaging scientific
results, and managing computational campaigns.

These collections represent the highest level of abstraction within the
Basic API.

Unlike previous collections, they do not primarily create new scientific
objects. Instead, they organize, aggregate, and coordinate existing
scientific objects.

---

# Part I — Datasets Collection

## 1. Scientific Object

The Datasets Collection owns the following public scientific object.

```text
Dataset
```

A `Dataset` represents a curated collection of persisted scientific
objects together with sufficient metadata to reproduce or distribute a
scientific study.

A Dataset may include:

- Materials,
- Surfaces,
- Matches,
- Interfaces,
- Relaxations,
- Analyses,
- Metadata,
- Provenance.

---

## 2. Collection Ownership

The Datasets Collection is accessed through the project.

```python
project.datasets
```

Every Dataset belongs to exactly one project.

---

## 3. Lifecycle Responsibilities

The Datasets Collection is responsible for:

- assembling datasets,
- retrieving datasets,
- querying datasets,
- exporting datasets,
- deleting datasets.

It is **not** responsible for generating new scientific objects.

---

## 4. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Datasets are assembled from project objects. |
| `create(...)` | ✓ | Assemble a new dataset. |
| `generate(...)` | ✗ | Not applicable. |
| `list(...)` | ✓ | Enumerate datasets. |
| `get(...)` | ✓ | Retrieve one dataset. |
| `find(...)` | ✓ | Query datasets. |
| `export(...)` | ✓ | Export datasets. |
| `delete(...)` | ✓ | Remove datasets. |

---

## 5. Behavioral Contract

### `create(...)`

Constructs a Dataset from existing project objects.

Inputs may include any combination of:

- Materials,
- Surfaces,
- Matches,
- Interfaces,
- Relaxations,
- Analyses.

Creation never modifies the underlying scientific objects.

---

### `list(...)`

Returns all persisted datasets.

---

### `get(...)`

Returns one persisted Dataset.

---

### `find(...)`

Returns datasets satisfying scientific criteria.

Typical criteria include:

- constituent materials,
- interface system,
- dataset purpose,
- included analyses.

---

### `export(...)`

Exports a complete scientific dataset.

Supported outputs may include:

- archive formats,
- machine learning datasets,
- benchmark datasets,
- publication supplements.

Export shall preserve complete provenance.

---

### `delete(...)`

Removes persisted datasets.

Deletion shall never affect the underlying scientific objects.

---

## 6. Scientific Questions

The Datasets Collection enables users to answer questions such as:

- Which scientific results belong together?
- Is this study reproducible?
- Can these data be shared?
- Can these data be used for machine learning?
- Is all provenance preserved?

---

# Part II — Campaigns Collection

## 7. Scientific Object

The Campaigns Collection owns the following public scientific object.

```text
Campaign
```

A Campaign represents a coordinated scientific investigation composed
of many related workflows.

Campaigns coordinate work.

They do not replace the underlying scientific objects.

---

## 8. Collection Ownership

The Campaigns Collection is accessed through the project.

```python
project.campaigns
```

Every Campaign belongs to exactly one project.

---

## 9. Lifecycle Responsibilities

The Campaigns Collection is responsible for:

- coordinating scientific workflows,
- organizing parameter studies,
- monitoring campaign progress,
- resuming interrupted campaigns,
- querying campaign status,
- exporting campaign summaries.

Campaigns consume all previous scientific collections.

---

## 10. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Campaigns are project-level workflows. |
| `create(...)` | ✓ | Create a new campaign. |
| `generate(...)` | ✗ | Not applicable. |
| `run(...)` | ✓ | Execute a campaign. |
| `resume(...)` | ✓ | Resume an interrupted campaign. |
| `list(...)` | ✓ | Enumerate campaigns. |
| `get(...)` | ✓ | Retrieve one campaign. |
| `find(...)` | ✓ | Query campaigns. |
| `export(...)` | ✓ | Export campaign summaries. |
| `delete(...)` | ✓ | Remove campaigns. |

---

## 11. Behavioral Contract

### `create(...)`

Creates a campaign describing a coordinated scientific investigation.

Campaign configuration may include:

- materials,
- parameter sweeps,
- workflow settings,
- computational resources.

---

### `run(...)`

Executes the configured campaign.

Campaign execution coordinates existing Basic API workflows.

---

### `resume(...)`

Continues an interrupted campaign without losing provenance.

---

### `list(...)`

Returns all campaigns.

---

### `get(...)`

Returns one campaign.

---

### `find(...)`

Returns campaigns satisfying scientific criteria.

Typical criteria include:

- completion status,
- material system,
- workflow stage,
- creation date.

---

### `export(...)`

Exports campaign summaries.

Supported outputs may include:

- reports,
- metadata,
- workflow summaries,
- provenance archives.

---

### `delete(...)`

Removes campaign metadata.

Deletion shall not automatically remove scientific objects created by
the campaign.

---

## 12. Scientific Questions

The Campaigns Collection enables users to answer questions such as:

- What studies have been completed?
- Which calculations remain?
- Which material combinations are being investigated?
- Can an interrupted study be resumed?
- What is the current status of the investigation?

---

# 13. Object Relationships

Datasets aggregate scientific objects.

```text
Material
Surface
Match
Interface
Relaxation
Analysis
        ↓
      Dataset
```

Campaigns coordinate workflows involving all scientific objects.

```text
Project
     ↓
Campaign
     ↓
Materials
Surfaces
Matches
Interfaces
Relaxations
Analyses
Datasets
```

Campaigns organize scientific work.

Datasets organize scientific results.

---

# 14. Example Workflow

```python
project = Project.open("lif_li2o")

campaign = project.campaigns.create(
    name="LiF–Li2O Interface Study",
)

project.campaigns.run(campaign)

dataset = project.datasets.create(
    campaign=campaign,
)

project.datasets.export(
    dataset,
    "lif_li2o_dataset.zip",
)

project.campaigns.export(
    campaign,
    "campaign_summary.pdf",
)
```

---

# 15. Design Rationale

Datasets and Campaigns occupy the highest level of the Basic API.

They do not introduce new scientific phenomena.

Instead, they organize scientific work and scientific results.

Keeping these responsibilities separate from lower-level scientific
collections preserves a clean separation between:

- scientific objects,
- scientific workflows,
- scientific deliverables.

This organization mirrors how computational materials scientists
conduct large research projects while maintaining a consistent,
discoverable public API.

---

# Summary

The Datasets and Campaigns Collections complete the CALM Basic API.

Together with the preceding collection specifications, they provide a
coherent public interface spanning the complete scientific workflow,
from importing materials through producing reproducible scientific
datasets and coordinated computational campaigns.

The ten chapters of the CALM Basic API Specification define a complete,
project-centered public API organized around scientific workflows rather
than implementation details.
