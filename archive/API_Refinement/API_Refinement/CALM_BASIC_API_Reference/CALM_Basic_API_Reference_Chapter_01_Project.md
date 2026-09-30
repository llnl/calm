# CALM Basic API Reference

# Chapter 1 — Project

## Overview

`Project` is the root object of the CALM Basic API.

A Project represents a complete scientific investigation and is the
entry point for every public workflow.

Every persisted scientific object belongs to exactly one Project.

---

# Construction

## `Project.create`

### Signature

```python
Project.create(
    path,
    *,
    name=None,
    mlip=None,
    metadata=None,
) -> Project
```

### Description

Creates a new CALM project.

A newly created project contains no scientific objects.

The project is immediately ready for scientific workflows.

### Parameters

#### `path`

Filesystem location of the project.

---

#### `name`

Optional project name.

If omitted, CALM derives the project name from `path`.

---

#### `mlip`

Optional default machine-learned interatomic potential.

If supplied, it becomes the default computational model for subsequent
workflow stages.

---

#### `metadata`

Optional project metadata.

---

### Returns

A newly created `Project`.

---

### Side Effects

Creates a persistent CALM project.

Initializes project metadata.

Initializes all public collections.

---

### Raises

- `ProjectAlreadyExistsError`
- `ProjectCreationError`

---

## Examples

```python
project = Project.create(
    "lif_li2o",
)
```

---

# Opening Projects

## `Project.open`

### Signature

```python
Project.open(
    path,
) -> Project
```

### Description

Opens an existing project.

Every previously persisted scientific object immediately becomes
available through the project's collections.

---

### Parameters

#### `path`

Filesystem location of the project.

---

### Returns

A `Project`.

---

### Raises

- `ProjectNotFoundError`
- `ProjectVersionError`

---

## Example

```python
project = Project.open(
    "lif_li2o",
)
```

---

# Project Properties

## `materials`

Type

```python
MaterialsCollection
```

The collection of persisted materials.

---

## `surfaces`

Type

```python
SurfacesCollection
```

The collection of persisted surfaces.

---

## `matches`

Type

```python
MatchesCollection
```

The collection of persisted interface matches.

---

## `interfaces`

Type

```python
InterfacesCollection
```

The collection of persisted interface structures.

---

## `relaxations`

Type

```python
RelaxationsCollection
```

The collection of persisted relaxations.

---

## `analyses`

Type

```python
AnalysesCollection
```

The collection of persisted analyses.

---

## `datasets`

Type

```python
DatasetsCollection
```

The collection of persisted datasets.

---

## `campaigns`

Type

```python
CampaignsCollection
```

The collection of persisted campaigns.

---

## `metadata`

Type

```python
ProjectMetadata
```

Project-level metadata.

---

Note

The Basic API does not expose a separate `ProjectConfiguration` object.
Users should modify project configuration using `project.configure(...)`,
which updates the project's defaults for future workflow stages. Previously
generated scientific objects remain unchanged.

---

# Project Methods

## `configure`

### Signature

```python
project.configure(
    *,
    mlip=None,
    calculator=None,
    defaults=None,
)
```

### Description

Updates the project's default computational configuration.

Configuration changes affect future workflow stages.

Previously generated scientific objects remain unchanged.

---

## `export`

### Signature

```python
project.export(
    destination,
)
```

### Description

Exports the complete scientific investigation.

Export preserves:

- scientific objects,
- metadata,
- provenance,
- workflow history.

---

## `close`

### Signature

```python
project.close()
```

### Description

Closes the project.

Closing a project never deletes persisted scientific objects.

---

# Object Relationships

A Project owns every scientific collection.

```text
Project
├── materials
├── surfaces
├── matches
├── interfaces
├── relaxations
├── analyses
├── datasets
└── campaigns
```

Every scientific object belongs to exactly one Project.

---

# Examples

## Creating a project

```python
project = Project.create(
    "lif_li2o",
)
```

---

## Opening a project

```python
project = Project.open(
    "lif_li2o",
)
```

---

## Configuring a project

```python
project.configure(
    mlip="mace-medium",
)
```

---

## Beginning a workflow

```python
project.materials.import(
    "LiF.vasp",
)
```

---

# Design Notes

`Project` is intentionally lightweight.

Its responsibilities are:

- project lifecycle,
- configuration,
- metadata,
- collection ownership.

Scientific operations belong to the appropriate collection rather than
to `Project` itself.
