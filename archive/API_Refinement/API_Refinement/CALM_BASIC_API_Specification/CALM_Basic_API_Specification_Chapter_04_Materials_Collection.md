# CALM Basic API Specification

# Chapter 04 --- Materials Collection

## Purpose

The Materials Collection is the public interface for managing bulk
crystal structures within a CALM project.

It is the canonical owner of every persisted `Material` object and
serves as the entry point for all workflows that begin with crystalline
materials.

The Materials Collection is responsible for importing, creating,
retrieving, querying, exporting, and deleting materials. It is **not**
responsible for generating derived scientific objects such as surfaces
or interfaces.

------------------------------------------------------------------------

# 1. Scientific Object

The Materials Collection owns the following public scientific object.

``` text
Material
```

A `Material` represents a bulk crystalline structure together with its
associated scientific metadata.

The Basic API intentionally does not expose implementation-specific
persistence objects.

------------------------------------------------------------------------

# 2. Collection Ownership

The Materials Collection is accessed through the project.

``` python
project.materials
```

Every persisted `Material` belongs to exactly one project.

Materials are never shared between projects.

------------------------------------------------------------------------

# 3. Lifecycle Responsibilities

The Materials Collection is responsible for:

-   importing structures from external files;
-   creating materials from existing structure objects;
-   retrieving persisted materials;
-   querying materials;
-   exporting materials;
-   deleting materials.

The Materials Collection does **not** generate:

-   surfaces;
-   interface matches;
-   interface structures;
-   relaxations;
-   analyses.

Those responsibilities belong to downstream collections.

------------------------------------------------------------------------

# 4. Supported Operations

  ------------------------------------------------------------------------
  Method                         Supported          Purpose
  ---------------------- -------------------------- ----------------------
  `import(...)`                      ✓              Import a material from
                                                    an external source.

  `create(...)`                      ✓              Create a material from
                                                    an in-memory
                                                    structure.

  `generate(...)`                    ✗              Not applicable.
                                                    Materials are primary
                                                    scientific objects.

  `list(...)`                        ✓              Enumerate persisted
                                                    materials.

  `get(...)`                         ✓              Retrieve a persisted
                                                    material.

  `find(...)`                        ✓              Query materials using
                                                    scientific criteria.

  `export(...)`                      ✓              Export one or more
                                                    materials.

  `delete(...)`                      ✓              Remove persisted
                                                    materials.
  ------------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Behavioral Contract

## `import(...)`

Creates one or more persisted `Material` objects from supported external
structure formats.

## `create(...)`

Creates a persisted `Material` from an existing in-memory structure
object.

## `list(...)`

Returns all persisted materials in the project.

## `get(...)`

Returns exactly one persisted material.

## `find(...)`

Returns materials satisfying scientific search criteria such as
composition, label, crystal system, or space group.

## `export(...)`

Exports one or more persisted materials without modifying the stored
objects.

## `delete(...)`

Removes persisted materials while respecting project provenance and
dependency rules.

------------------------------------------------------------------------

# 6. Object Relationships

``` text
Material
    ↓
Surface
    ↓
Match
    ↓
Interface
```

A `Material` has no scientific parent within the project. Downstream
collections consume materials but never own them.

------------------------------------------------------------------------

# 7. Scientific Questions

The Materials Collection enables users to answer:

-   Which materials are stored in this project?
-   Which polymorphs are available?
-   What is the composition?
-   What is the crystal symmetry?
-   Which materials should be used to generate surfaces?

------------------------------------------------------------------------

# 8. Example Workflow

``` python
project = Project.open("lif_li2o")

project.materials.import("LiF.vasp")
project.materials.import("Li2O.vasp")

materials = project.materials.list()

lif = project.materials.get("LiF")

project.materials.export(lif, "LiF.vasp")
```

------------------------------------------------------------------------

# 9. Design Rationale

The Materials Collection is the root of the scientific workflow. All
downstream workflow stages consume persisted `Material` objects rather
than reconstructing structures in memory.

------------------------------------------------------------------------

# Summary

The Materials Collection owns every persisted `Material`, implements the
common collection contract defined in Chapter 2, and provides the
foundation for all downstream scientific workflows.
