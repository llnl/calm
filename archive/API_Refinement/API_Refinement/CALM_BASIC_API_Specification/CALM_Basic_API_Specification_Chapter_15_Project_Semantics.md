# CALM Basic API Specification

# Chapter 15 — Project Semantics

## Purpose

This chapter defines the Project as the root object of the CALM Basic
API.

The Project is the persistent representation of a scientific
investigation. It owns every scientific object, coordinates every
workflow stage, and provides the primary entry point into the Basic API.

Unlike other objects in the Basic API, the Project is not merely another
collection owner—it defines the scientific context in which all
collections operate.

---

# 1. Design Goals

The Project shall:

- represent a complete scientific investigation;
- own every persisted scientific object;
- preserve complete scientific provenance;
- coordinate workflow execution;
- provide a consistent entry point to every collection;
- remain independent of persistence implementation details.

---

# 2. Project Responsibilities

The Project is responsible for:

- maintaining scientific state;
- owning all collections;
- preserving provenance;
- coordinating workflow execution;
- managing project metadata;
- managing project configuration;
- exporting project-level artifacts.

The Project is **not** responsible for performing scientific operations
that belong to individual collections.

For example:

- importing materials belongs to `project.materials`;
- generating surfaces belongs to `project.surfaces`;
- matching interfaces belongs to `project.matches`.

---

# 3. Project Collections

Every Project owns one instance of each collection.

```python
project.materials
project.surfaces
project.matches
project.interfaces
project.relaxations
project.analyses
project.datasets
project.campaigns
```

Collections are permanent properties of the Project.

# They are never created or destroyed independently.

## 3.1 Project Artifact Area (default)

When Basic API operations produce exported artifacts (tables, plots, reports,
structure files, dataset archives) and the user does not supply an explicit
destination, the Basic API writes outputs into a discoverable, project-local
artifact directory named `CALM_results/` inside the Project root.

This convention is a user-facing default to improve discoverability and to
support reproducible project export workflows. Implementations may create
subdirectories such as `tables/`, `plots/`, `reports/`, `structures/`, and
`datasets/` under the artifact root. The Project shall provide helpers to
discover the artifact root and list recorded artifacts produced by prior
operations. Users may always supply an explicit destination to `export()` to
override the default.

Example layout (conceptual):

```
<project-root>/CALM_results/
    tables/
    plots/
    reports/
    structures/
    datasets/
```

The artifact root is intended to remain inside the project directory so that
exported deliverables travel with the project when the project directory is
moved or archived.

---

# 4. Project Lifecycle

The Basic API recognizes three project lifecycle operations.

## Create

```python
project = Project.create(...)
```

Creates a new scientific investigation.

A newly created project initially contains no scientific objects.

---

## Open

```python
project = Project.open(...)
```

Opens an existing project together with all persisted scientific objects.

Opening a project restores the complete scientific investigation.

---

## Close

```python
project.close()
```

Terminates access to the project.

Closing a project shall never discard persisted scientific data.

---

# 5. Project Identity

Every Project possesses a unique identity.

Projects are independent scientific investigations.

Scientific objects belong to exactly one Project.

Objects shall never be shared between Projects.

Movement of scientific objects between Projects occurs only through
explicit export and import operations.

---

# 6. Project Metadata

Every Project maintains project-level metadata.

Examples include:

- project name;
- project description;
- creation date;
- authors;
- computational environment;
- default MLIP;
- default computational settings;
- user-defined metadata.

Project metadata describes the investigation as a whole rather than
individual scientific objects.

---

# 7. Project Configuration

Project configuration defines the default behavior of the scientific
workflow.

Examples include:

- default MLIP;
- default calculator;
- default optimization parameters;
- default export preferences;
- default workflow settings.

Collections may inherit these defaults unless explicitly overridden.

---

Note

The Basic API does not expose a separate `ProjectConfiguration` object.
Users should modify project configuration using `project.configure(...)`,
which updates the project's defaults for future workflow stages. Previously
generated scientific objects remain unchanged.

---

# 8. Project Provenance

The Project is the root of the provenance graph.

```text
Project
    ↓
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
Datasets
```

Every persisted scientific object belongs to exactly one provenance
graph rooted at the Project.

---

# 9. Project Queries

The Project serves as the primary navigation point for scientific
objects.

Typical interactions begin with:

```python
project.materials

project.surfaces

project.matches
```

The Project itself should not duplicate collection interfaces.

Instead, it delegates scientific operations to the appropriate
collection.

---

# 10. Project Integrity

The Project shall preserve scientific consistency.

It shall ensure that:

- parent-child relationships remain valid;
- provenance remains complete;
- workflow stages remain connected;
- scientific objects remain discoverable.

Scientific integrity takes precedence over implementation convenience.

---

# 11. Project Export

The Project may export complete investigations.

Examples include:

- complete scientific archives;
- reproducibility bundles;
- publication supplements;
- machine learning datasets.

Project export should preserve:

- scientific objects;
- metadata;
- provenance;
- workflow history.

---

# 12. Scientific Questions

The Project enables users to answer questions such as:

- What scientific investigation am I working on?
- Which scientific objects belong to this study?
- Which workflows have been completed?
- Which computational settings were used?
- Can another researcher reproduce this investigation?

---

# 13. Design Rationale

The Basic API is intentionally project-centered.

Scientists conduct investigations rather than isolated calculations.

Accordingly, the Project is the root object from which every scientific
workflow begins.

By making the Project responsible for persistence, configuration,
provenance, and collection ownership, the Basic API presents a coherent
mental model:

- a Project represents a scientific investigation;
- collections organize scientific objects;
- scientific objects represent workflow stages.

This organization minimizes cognitive load while preserving complete
scientific reproducibility.

---

# Summary

The Project is the root object of the CALM Basic API.

It owns every collection, every persisted scientific object, and the
complete provenance graph describing a scientific investigation.

The Project coordinates—but does not directly perform—scientific
operations, providing a single, consistent entry point for the entire
Basic API.

The next chapter presents **Integrated Workflow Examples**, showing how
the complete Basic API supports end-to-end scientific investigations
using the object model, collections, and lifecycle defined throughout
this specification.
