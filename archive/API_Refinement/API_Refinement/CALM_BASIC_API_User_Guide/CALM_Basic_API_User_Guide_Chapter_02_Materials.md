# CALM Basic API User Guide

# Chapter 2 — Materials

## Scientific Objective

Every interface study begins by identifying the materials that will
participate in the investigation.

In this chapter you will import bulk crystal structures into your
Project and learn how to retrieve, inspect, query, and export persisted
Materials.

By the end of this chapter you will be able to:

- import bulk crystal structures,
- retrieve persisted Materials,
- list all Materials in the Project,
- search for Materials,
- inspect Material properties,
- export Materials.

These Materials become the foundation for every subsequent workflow
stage.

---

## Workflow

### Import Bulk Crystal Structures

Import the bulk structures that will participate in the interface study.

```python
lif = project.materials.import(
    "LiF.vasp",
)

li2o = project.materials.import(
    "Li2O.vasp",
)
```

Each imported structure immediately becomes a persisted `Material`
contained within the Project.

The returned objects represent the canonical bulk structures for the
remainder of the investigation.

---

### List Materials

Retrieve every Material currently stored in the Project.

```python
materials = project.materials.list()
```

Each object in the returned collection is a persisted `Material`.

---

### Retrieve a Material

Retrieve one Material by name.

```python
lif = project.materials.get(
    "LiF",
)
```

Retrieving Materials from the Project is the preferred workflow.

Scientific objects should not be reconstructed once they have been
persisted.

---

### Find Materials

Search for Materials using scientific criteria.

```python
fluorides = project.materials.find(
    composition="LiF",
)
```

Scientific queries return persisted Material objects rather than
database records or identifiers.

---

### Inspect Material Properties

Every Material exposes commonly used crystallographic information.

```python
print(lif.name)

print(lif.composition)

print(lif.space_group)

print(lif.crystal_system)
```

These properties describe the persisted scientific object.

---

### Retrieve Derived Surfaces

Although no surfaces have been generated yet, every Material exposes the
relationship to its derived Surface objects.

```python
surfaces = lif.surfaces
```

At this stage the collection is empty.

After generating surfaces in the next chapter, this relationship will be
populated automatically.

---

### Export a Material

Export a persisted Material.

```python
lif.export(
    "LiF.vasp",
)
```

or equivalently

```python
project.materials.export(
    lif,
    "LiF.vasp",
)
```

Export never modifies the persisted Material.

---

## Discussion

Materials are the root scientific objects within the CALM workflow.

Every downstream scientific object ultimately derives from one or more
persisted Materials.

The Basic API therefore encourages a simple pattern:

1. Import a Material once.
2. Persist it within the Project.
3. Retrieve it whenever it is needed.

This avoids duplicated structures, preserves provenance, and ensures
that every workflow stage operates on the same scientific objects.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Bulk structures can be imported | ✓ |
| Imported structures become persisted Materials | ✓ |
| Materials can be listed | ✓ |
| Materials can be retrieved | ✓ |
| Materials can be queried using scientific properties | ✓ |
| Material properties are directly accessible | ✓ |
| Materials can be exported | ✓ |
| Downstream workflows retrieve Materials rather than reconstructing them | ✓ |

---

## Summary

In this chapter you imported the bulk crystal structures that will be
used throughout the remainder of the investigation.

The Project now contains two persisted Materials:

- LiF
- Li₂O

These Materials are the canonical scientific objects from which all
subsequent Surface models will be generated.

In the next chapter you will retrieve these persisted Materials and use
them to generate crystallographic Surface models.
