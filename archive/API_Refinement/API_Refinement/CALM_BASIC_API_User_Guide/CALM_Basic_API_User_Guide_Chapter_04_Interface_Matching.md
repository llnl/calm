# CALM Basic API User Guide

# Chapter 4 — Interface Matching

## Scientific Objective

Having generated crystallographic Surface models, the next step is to
determine whether two surfaces can form coherent interfaces.

In this chapter you will retrieve previously generated Surface objects
from the Project, perform an interface matching search, and identify
candidate interface relationships for later interface construction.

By the end of this chapter you will be able to:

- retrieve persisted Surface models,
- perform an interface matching search,
- inspect Match objects,
- identify promising interface candidates,
- visualize the search results,
- export match summaries.

The resulting Match objects become the foundation for constructing
atomistic interface structures.

---

## Workflow

### Retrieve Surface Models

Interface matching always begins with previously generated Surface
objects.

```python
film = project.surfaces.get(
    "LiF (100)",
)

substrate = project.surfaces.get(
    "Li2O (100)",
)
```

The Surface objects are retrieved directly from the Project.

No new Surface models are generated during this workflow.

---

### Perform an Interface Matching Search

Search for coherent lattice matches between the two persisted Surface
models.

```python
results = project.matches.search(
    film=film,
    substrate=substrate,
)
```

The search creates one or more persisted `Match` objects describing the
crystallographic relationships identified during the search.

Neither parent Surface is modified.

---

### Inspect Search Results

The search result provides access to every Match generated during the
search.

```python
matches = results.matches
```

Each Match is immediately available as a persisted scientific object.

---

### Retrieve a Match

Retrieve one persisted Match from the Project.

```python
match = project.matches.get(
    match_id,
)
```

or select one directly from the search results.

```python
match = results.best()
```

The selected Match becomes the parent object for interface
construction.

---

### Query Existing Matches

Previously generated Match objects can be queried using scientific
criteria.

```python
matches = project.matches.find(
    film=film,
    substrate=substrate,
    max_strain=0.03,
)
```

Queries return persisted Match objects rather than repeating the
matching calculation.

---

### Generate a Pareto Plot

Visualize the trade-off between competing matching criteria.

```python
project.matches.plot_pareto(
    matches,
)
```

The Pareto plot provides a convenient overview of the candidate Match
objects.

---

### Export Match Summaries

Export the search results.

```python
project.matches.export(
    matches,
    "matches.csv",
)
```

Export never modifies the persisted Match objects.

---

### Inspect Match Properties

Every Match exposes the scientific information required to evaluate the
quality of the interface relationship.

```python
print(match.film)

print(match.substrate)

print(match.strain)

print(match.interface_area)

print(match.orientation_relationship)
```

These properties describe the persisted Match.

---

### Retrieve Constructed Interfaces

At this stage no Interfaces have yet been constructed.

Nevertheless, every Match exposes the relationship to the Interface
objects that will later be derived from it.

```python
interfaces = match.interfaces
```

Initially this collection is empty.

After the next chapter it will contain every Interface constructed from
this Match.

---

## Discussion

Interface matching is fundamentally different from previous workflow
stages.

Surface generation deterministically derives new scientific objects.

Interface matching performs a scientific search.

Consequently, the Basic API expresses this workflow using:

```python
project.matches.search(...)
```

rather than

```python
project.matches.generate(...)
```

The search may produce:

- zero Matches,
- one Match,
- many Matches.

Every identified Match becomes a persisted scientific object within the
Project.

Subsequent workflow stages retrieve those Match objects rather than
repeating the search.

This preserves reproducibility while allowing scientists to explore the
results before committing to interface construction.

---

## Basic API Validation

This chapter validates the following aspects of the Basic API.

| Requirement | Status |
|--------------|:------:|
| Persisted Surfaces can be retrieved | ✓ |
| Interface matching is performed through the Matches Collection | ✓ |
| Matching creates persisted Match objects | ✓ |
| Match objects can be retrieved | ✓ |
| Match objects can be queried | ✓ |
| Pareto visualization is available | ✓ |
| Match summaries can be exported | ✓ |
| Match properties are directly accessible | ✓ |
| Downstream workflows retrieve persisted Matches rather than repeating the search | ✓ |

---

## Summary

In this chapter you performed a crystallographic interface matching
search using previously generated Surface models.

The Project now contains:

- Materials,
- Surface models,
- Interface Matches,

together with complete provenance linking every Match to its parent
Surface models.

These persisted Match objects become the inputs for atomistic interface
construction.

In the next chapter you will retrieve a Match from the Project and use
it to construct explicit atomistic Interface structures suitable for
simulation.
