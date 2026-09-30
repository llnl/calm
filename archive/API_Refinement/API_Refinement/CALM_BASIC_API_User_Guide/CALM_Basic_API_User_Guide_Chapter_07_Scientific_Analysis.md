# CALM Basic API User Guide

# Chapter 7 — Scientific Analysis

## Scientific Objective

The structural relaxation completed in the previous chapter produced a
physically relaxed interface.

The next step is to transform that structural information into
scientific understanding.

In this chapter you will retrieve a persisted Relaxation, compute
derived scientific quantities, compare scientific results, inspect the
resulting Analysis objects, and export the results for publication.

By the end of this chapter you will be able to:

- retrieve persisted Relaxations,
- compute scientific analyses,
- compare scientific results,
- retrieve Analysis objects,
- query Analyses,
- export scientific results.

The resulting Analysis objects become the foundation for reproducible
scientific datasets.

---

## Workflow

### Retrieve a Relaxation

Scientific analysis always begins with a previously completed
Relaxation.

```python
relaxation = project.relaxations.get(
    relaxation_id,
)
```

The Relaxation is retrieved directly from the Project.

No structural relaxation is repeated.

---

### Compute Interface Energy

Compute the interface energy.

```python
interface_energy = project.analyses.run(
    interface_energy,
    relaxation,
)
```

A new persisted Analysis is created.

The parent Relaxation remains unchanged.

---

### Compute Adhesion Energy

Compute the adhesion energy for the relaxed Interface.

```python
adhesion_energy = project.analyses.run(
    adhesion_energy,
    relaxation,
)
```

Like every Analysis, the result is immediately persisted within the
Project.

---

### Compute Strain Analysis

Analyze the distribution of strain within the relaxed Interface.

```python
strain = project.analyses.run(
    strain_analysis,
    relaxation,
)
```

Additional analyses may be performed independently without modifying
either the Relaxation or previously generated Analysis objects.

---

### Retrieve an Analysis

Previously computed analyses can be retrieved directly from the Project.

```python
analysis = project.analyses.get(
    analysis_id,
)
```

Retrieval is preferred over recomputing existing scientific results.

---

### Query Analyses

Locate Analyses using scientific criteria.

```python
energies = project.analyses.find(
    type="interface_energy",
)
```

or

```python
analyses = project.analyses.find(
    relaxation=relaxation,
)
```

Queries return persisted Analysis objects.

---

### Compare Scientific Results

Compare multiple scientific objects.

```python
comparison = project.analyses.compare(
    interface_energy,
    adhesion_energy,
)
```

Comparative analyses are themselves persisted Analysis objects.

---

### Inspect Analysis Results

Every Analysis exposes both the scientific inputs and the resulting
derived quantities.

```python
print(analysis.type)

print(analysis.inputs)

print(analysis.results)
```

These properties describe the complete scientific interpretation.

---

### Export Scientific Results

Export an Analysis.

```python
analysis.export(
    "interface_energy.csv",
)
```

or

```python
project.analyses.export(
    analysis,
    "interface_energy.csv",
)
```

Export never modifies the persisted Analysis.

---

## Discussion

Scientific analysis represents the final computational stage of the
workflow.

Unlike previous stages, no new atomic structures are created.

Instead, existing scientific objects are interpreted to produce new
scientific knowledge.

The Basic API therefore treats an Analysis as its own persisted
scientific object.

```text
Relaxation
      ↓
Analysis
```

This provides several important advantages:

- analyses are reproducible,
- analyses can be repeated independently,
- multiple analyses may consume the same Relaxation,
- every scientific result preserves complete provenance.

Scientific interpretation therefore becomes a first-class component of
the Project rather than an external post-processing step.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Persisted Relaxations can be retrieved | ✓ |
| Scientific analyses can be executed | ✓ |
| Analyses become persisted scientific objects | ✓ |
| Analyses can be retrieved | ✓ |
| Analyses can be queried | ✓ |
| Scientific results can be compared | ✓ |
| Analysis properties are directly accessible | ✓ |
| Analysis results can be exported | ✓ |
| Scientific interpretation preserves complete provenance | ✓ |

---

## Summary

In this chapter you transformed a relaxed Interface into reproducible
scientific knowledge.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,
- Atomistic Interfaces,
- Structural Relaxations,
- Scientific Analyses,

with complete provenance linking every Analysis to the scientific
objects from which it was derived.

The Project now contains all of the scientific information required to
create a reusable dataset.

In the next chapter you will assemble these scientific objects into a
Dataset suitable for publication, data sharing, benchmarking, and
machine learning.
