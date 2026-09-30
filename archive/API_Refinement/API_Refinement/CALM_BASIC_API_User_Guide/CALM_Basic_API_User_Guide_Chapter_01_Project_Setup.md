# CALM Basic API User Guide

# Chapter 1 — Project Setup

## Scientific Objective

Every scientific investigation in CALM begins with a **Project**.

The Project is the persistent home of the investigation. It stores every
scientific object generated throughout the workflow, preserves the
relationships between those objects, and records the computational
configuration used to produce them.

By the end of this chapter you will have:

- created a new Project,
- configured the default machine-learned interatomic potential (MLIP),
- reopened an existing Project,
- understood how the Project serves as the canonical source of
  scientific workflow state.

---

## Workflow

### Create a Project

Create a new Project that will contain every scientific object generated
throughout this tutorial.

```python
from calm import Project

project = Project.create(
    "lif_li2o",
)
```

A newly created Project contains no Materials, Surfaces, Matches,
Interfaces, Relaxations, Analyses, Datasets, or Campaigns.

Instead, it establishes the persistent scientific investigation into
which those objects will be added during subsequent workflow stages.

---

### Configure the Project

Configure the default machine-learned interatomic potential that will be
used by future computational workflows.

```python
project.configure(
    mlip="mace-medium",
)
```

Project configuration establishes the default computational environment.

Changing the Project configuration affects only future workflow stages.

Previously generated scientific objects always retain the computational
configuration under which they were originally created.

---

### Reopen an Existing Project

Scientific investigations are expected to span multiple computational
sessions.

To continue a previous investigation, reopen the existing Project.

```python
project = Project.open(
    "lif_li2o",
)
```

Opening a Project restores the complete scientific investigation.

Every previously generated scientific object immediately becomes
available through the Project.

---

## Discussion

The Project is the root object of the CALM Basic API.

Rather than organizing scientific work around individual files, CALM
organizes every investigation around a persistent Project.

Each workflow stage creates new scientific objects within the Project.

Subsequent workflow stages retrieve those persisted objects instead of
reconstructing them.

This persistence model provides several important advantages:

- reproducibility,
- complete scientific provenance,
- workflow continuity,
- discoverability,
- consistent navigation of scientific objects.

Throughout this tutorial, the Project remains the canonical source of
scientific workflow state.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Project can be created | ✓ |
| Project can be reopened | ✓ |
| Default MLIP can be configured | ✓ |
| Workflow requires no implementation knowledge | ✓ |
| Project is the canonical source of scientific state | ✓ |
| No scientific objects are reconstructed | ✓ |
| Workflow follows the project-centered object lifecycle | ✓ |

---

## Summary

In this chapter you established a new CALM Project and configured its
default computational environment.

The Project will remain the persistent home of the scientific
investigation throughout the remainder of this guide.

Every subsequent workflow stage will retrieve previously generated
scientific objects from the Project rather than recreating them.

In the next chapter you will import the bulk crystal structures that
form the foundation of the interface study.
