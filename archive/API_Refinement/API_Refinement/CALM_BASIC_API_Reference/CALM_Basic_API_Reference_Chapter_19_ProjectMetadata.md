# CALM Basic API Reference

# Chapter 19 — ProjectMetadata

## Overview

`ProjectMetadata` contains descriptive information about a scientific
investigation.

Unlike scientific objects such as `Material` or `Interface`,
ProjectMetadata does not participate directly in scientific workflows.

Instead, it records information describing the Project as a whole.

Every Project owns exactly one `ProjectMetadata` object.

It is accessed through:

```python
project.metadata
```

---

# Purpose

ProjectMetadata provides a consistent location for information describing
the scientific investigation.

Typical information includes:

- project title,
- description,
- authors,
- affiliations,
- keywords,
- creation date,
- last modification date,
- citation information,
- user notes.

ProjectMetadata improves reproducibility, organization, and
discoverability.

---

# Construction

ProjectMetadata objects are created automatically when a Project is
created.

Users do not instantiate ProjectMetadata directly.

Example:

```python
project = Project.create(
    "lif_li2o",
)

metadata = project.metadata
```

---

# Properties

## `title`

Type

```python
str
```

Human-readable project title.

Read/write.

---

## `description`

Type

```python
str | None
```

Optional project description.

Read/write.

---

## `authors`

Type

```python
list[str]
```

Authors responsible for the scientific investigation.

Read/write.

---

## `affiliations`

Type

```python
list[str]
```

Institutional affiliations.

Read/write.

---

## `keywords`

Type

```python
list[str]
```

Keywords describing the investigation.

Read/write.

---

## `created`

Type

```python
datetime
```

Project creation time.

Read-only.

---

## `modified`

Type

```python
datetime
```

Time of the most recent project modification.

Read-only.

---

## `notes`

Type

```python
str | None
```

User-maintained project notes.

Read/write.

---

## `citation`

Type

```python
str | None
```

Recommended citation for the project or associated publication.

Read/write.

---

# Methods

ProjectMetadata intentionally exposes a minimal public interface.

Metadata is primarily manipulated through property assignment.

---

## `summary`

### Signature

```python
summary()
```

### Description

Returns a concise summary of the project metadata.

Typical information includes:

- title,
- authors,
- creation date,
- keywords,
- description.

---

# Examples

## Access project metadata

```python
metadata = project.metadata
```

---

## Set project title

```python
project.metadata.title = "LiF–Li₂O Interface Study"
```

---

## Record authors

```python
project.metadata.authors = [
    "Alice Smith",
    "Bob Jones",
]
```

---

## Add keywords

```python
project.metadata.keywords = [
    "interfaces",
    "LiF",
    "Li2O",
    "MACE",
]
```

---

## Print summary

```python
print(project.metadata.summary())
```

---

# Design Notes

ProjectMetadata intentionally stores only information describing the
scientific investigation.

It does not contain:

- workflow configuration,
- computational defaults,
- scientific objects,
- provenance relationships.

Those responsibilities belong to the Project itself and to the scientific
collections. Users adjust project configuration via `project.configure(...)`.

Separating descriptive metadata from computational configuration keeps
the public API clear and prevents unrelated concepts from becoming
coupled.

---

# See Also

- `Project`
- `ProjectConfiguration`
- `Project`
 - `Project`
