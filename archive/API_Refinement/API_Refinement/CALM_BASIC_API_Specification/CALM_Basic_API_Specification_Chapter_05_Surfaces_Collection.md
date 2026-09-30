# CALM Basic API Specification

# Chapter 05 — Surfaces Collection

## Purpose

The Surfaces Collection is the public interface for generating, managing,
retrieving, querying, exporting, and deleting surface models within a CALM
project.

It is the canonical owner of every persisted `Surface` object and is responsible
for all surface-generation workflows derived from persisted `Material` objects.

The Surfaces Collection is responsible for producing new scientific objects from
existing materials. It is not responsible for interface matching or interface
construction.

---

# 1. Scientific Object

The Surfaces Collection owns the following public scientific object.

```text
Surface
```

A `Surface` represents a crystallographic surface derived from a persisted
`Material`, together with the metadata required to reproduce that surface.

---

# 2. Collection Ownership

The Surfaces Collection is accessed through the project.

```python
project.surfaces
```

Every persisted `Surface` belongs to exactly one project.

Every surface has exactly one parent `Material`.

---

# 3. Lifecycle Responsibilities

The Surfaces Collection is responsible for:

- generating surfaces from persisted materials;
- enumerating crystallographic orientations;
- enumerating surface terminations;
- retrieving persisted surfaces;
- querying surfaces;
- exporting surfaces;
- deleting surfaces.

The Surfaces Collection does **not** perform:

- interface matching;
- interface construction;
- structural relaxation;
- scientific analysis.

Those responsibilities belong to downstream collections.

---

# 4. Supported Operations

| Method | Supported | Purpose |
|---------|:---------:|---------|
| `import(...)` | ✗ | Surface models are derived objects. |
| `create(...)` | ✗ | Surface construction should occur through generation. |
| `generate(...)` | ✓ | Generate surfaces from a persisted material. One call may produce multiple persisted Surface objects; each persisted Surface is uniquely identified by the parent Material, Miller orientation, termination, and any generation parameters that affect the persisted slab geometry. |
| `list(...)` | ✓ | Enumerate persisted surfaces. |
| `get(...)` | ✓ | Retrieve one persisted surface. |
| `find(...)` | ✓ | Query surfaces by scientific criteria. |
| `export(...)` | ✓ | Export one or more surfaces. |
| `delete(...)` | ✓ | Remove persisted surfaces. |

---

# 5. Behavioral Contract

## `generate(...)`

Produces one or more persisted `Surface` objects from a persisted
`Material`.

Typical generation parameters include:

- Miller indices,
- slab thickness,
- vacuum thickness,
- termination enumeration,
- symmetry options.

Generation shall never modify the parent material.

---

## `list(...)`

Returns all persisted surfaces in the project.

---

## `get(...)`

Returns one persisted surface.

---

## `find(...)`

Returns surfaces satisfying scientific search criteria.

Typical criteria include:

- parent material,
- Miller orientation,
- termination,
- slab size,
- polarity.

---

## `export(...)`

Exports persisted surfaces to external structure formats.

Export shall never modify stored objects.

---

## `delete(...)`

Removes persisted surfaces while respecting project provenance rules.

---

# 6. Object Relationships

Every surface is derived from exactly one material.

```text
Material
    ↓
Surface
```

A surface may subsequently participate in one or more interface matches.

```text
Material
    ↓
Surface
    ↓
Match
```

---

# 7. Scientific Questions

The Surfaces Collection enables users to answer questions such as:

- Which surface orientations have been generated?
- Which Miller indices are available?
- Which surface terminations exist?
- Which surfaces are polar?
- Which surfaces are symmetry equivalent?
- Which surfaces minimize surface cell size?

---

# 8. Example Workflow

```python
project = Project.open("lif_li2o")

lif = project.materials.get("LiF")

project.surfaces.generate(
    material=lif,
    millers=[
        (1, 0, 0),
        (1, 1, 0),
        (1, 1, 1),
    ],
    enumerate_terminations=True,
)

surfaces = project.surfaces.list()

surface = project.surfaces.get("LiF (100)")

project.surfaces.export(surface, "LiF_100.vasp")
```

---

# 9. Design Rationale

Surface generation is the first derived stage of the scientific workflow.

By assigning ownership of all surface operations to the Surfaces Collection, the
Basic API presents a cohesive, discoverable interface while preserving the
project-centered persistence model established in earlier specification
chapters.

---

# Summary

The Surfaces Collection owns every persisted `Surface`, implements the common
collection contract defined in Chapter 2, and provides the bridge between bulk
materials and interface matching. Subsequent workflow stages consume persisted
surface models rather than regenerating them, preserving provenance and
supporting a consistent scientific object lifecycle.
