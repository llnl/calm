# CALM Basic API Specification

# Chapter 2 --- Collection Interface Contract

## Purpose

This chapter defines the common public interface that all Basic API
collections shall follow. The objective is to make every collection
predictable and discoverable so that learning one collection naturally
transfers to the others.

------------------------------------------------------------------------

# 1. Design Principles

Every collection shall:

-   present a consistent public interface;
-   expose scientific operations rather than persistence details;
-   operate on persisted project objects;
-   use consistent naming for equivalent operations.

------------------------------------------------------------------------

# 2. Standard Collection Vocabulary

Where applicable, collections shall expose the following methods.

  Method            Purpose
  ----------------- ---------------------------------------
  `import(...)`     Import external scientific data.
  `create(...)`     Create an object directly.
  `generate(...)`   Produce derived scientific objects.
  `list(...)`       Enumerate persisted objects.
  `get(...)`        Retrieve a single persisted object.
  `find(...)`       Query objects by scientific criteria.
  `export(...)`     Export objects to external formats.
  `delete(...)`     Remove persisted objects.

Collections are not required to implement every method. However, when
two collections support the same operation, they shall use the same
method name.

------------------------------------------------------------------------

# 3. Naming Rules

Equivalent operations shall use identical names throughout the Basic
API.

For example:

-   `get(...)` shall be used consistently for single-object retrieval.
-   `list(...)` shall be used consistently for enumeration.
-   `generate(...)` shall be used for creating derived scientific
    objects.

Collections should avoid introducing synonymous methods for identical
behavior.

------------------------------------------------------------------------

# 4. Return Types

Collection methods should return scientific objects or collections of
scientific objects rather than implementation-specific data structures.

Examples:

``` python
materials = project.materials.list()

material = project.materials.get("LiF")

surfaces = project.surfaces.find(material=material)
```

Users should not need to understand internal identifiers or database
records to perform common workflows.

------------------------------------------------------------------------

# 5. Object Identity

Collections shall define stable object identity.

The Basic API should support retrieving persisted objects using
identifiers appropriate to the scientific workflow while avoiding
unnecessary exposure of implementation details.

------------------------------------------------------------------------

# 6. Collection Independence

Knowledge of one collection should transfer naturally to every other
collection.

For example, a user familiar with:

``` python
project.materials.get(...)
project.materials.list(...)
```

should immediately understand:

``` python
project.surfaces.get(...)
project.surfaces.list(...)

project.matches.get(...)
project.matches.list(...)
```

without learning a different interface.

------------------------------------------------------------------------

# Summary

This chapter establishes the common contract shared by all Basic API
collections. Subsequent specification chapters will apply this contract
to the individual scientific collections defined in Chapter 1.
