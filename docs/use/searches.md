# Searches and candidates

<p class="calm-lede">
Run a bounded coherent-interface search, inspect the admitted candidate population, interpret size and strain tradeoffs, and select models for construction without treating a geometric ranking as a thermodynamic prediction.
</p>

## Outcome

The project contains a named interface search and a queryable candidate collection. You can explain why no candidates were found, inspect buildability, identify the Pareto front, apply additional scientific limits, and retain one or more candidates for construction.

## When to use it

Use this workflow after selecting one exact surface for side A and one exact surface for side B. Rerun a search when changing:

- either surface or contact termination;
- the maximum admitted principal strain;
- supercell enumeration limits;
- atom-count or candidate limits; or
- the geometric ranking weight.

Do not rerun matching merely to change the initial interface gap, vacuum, or registry; those are construction choices.

## Prerequisites

Select exact surfaces first:

```python
surface_a = project.surface(
    material="LiF",
    miller=(1, 0, 0),
    termination="LiF",
    termination_shift=0,
)
surface_b = project.surface(
    material="Li2O",
    miller=(1, 0, 0),
    termination_bottom="O",
    termination_shift=1,
)
```

The search is calculator-free. It operates on periodic surface lattices and bounded atomistic-size estimates.

## Scientific decisions

### Set a physically defensible strain limit

`max_principal_strain` limits the largest absolute principal Hencky strain admitted by the search. A permissive limit may find compact but highly strained cells; a strict limit may eliminate all candidates.

The limit is a modeling decision, not a universal material constant. Consider elastic response, cell size, downstream calculator cost, and whether coherent accommodation is plausible.

### Bound the combinatorial search

- `max_supercell_index` controls how far surface supercells are enumerated.
- `max_atoms` rejects candidates estimated to exceed the chosen interface size.
- `max_candidates` limits retained candidates after admission and ranking.

Increasing bounds can reveal better low-strain matches but increases search time and downstream model size.

### Decide how candidates will be selected

CALM provides geometric descriptors and a Pareto classification. The final selection may also depend on termination chemistry, elastic asymmetry, intended strain allocation, reconstruction freedom, or the cost of later relaxation.

## Minimal procedure

### Run or resume a search

```python
from calm import SearchSettings

settings = SearchSettings(
    max_principal_strain=0.10,
    max_supercell_index=16,
    max_atoms=1200,
    max_candidates=750,
    mismatch_weight=0.5,
)

search = project.search_interfaces(
    surface_a,
    surface_b,
    settings=settings,
    name="lif-li2o-100",
    resume=True,
)
```

Using the same name and identical scientific inputs can resume or reuse the saved search. Reusing the same name for a different search raises an identity conflict rather than overwriting the earlier result.

### Check the result before filtering

```python
if search.empty:
    raise RuntimeError(search.explain())

buildability = search.buildability_summary()
if not buildability.ok:
    raise RuntimeError(buildability.explain())

print(search.summary())
```

### Inspect and shortlist candidates

```python
candidates = search.candidates()
candidates.to_table().display()

pareto = candidates.select(pareto=True)
shortlist = pareto.where(
    max_principal_strain=(None, 0.08),
).select_top(5, by="score")

shortlist.write_table("exports/candidate-shortlist.csv")
```

The three steps answer different questions:

1. the full collection shows every admitted candidate;
2. the Pareto collection removes candidates dominated in the saved size–mismatch objectives; and
3. the additional filter and ranking express your modeling objective.

## Inspect the result

Useful candidate fields include:

| Field | Meaning |
|---|---|
| `candidate_id` | Short identifier used for selection and tracing. |
| `n_atoms_estimate` | Estimated interface atom count. |
| `d_cell` | Dimensionless cell mismatch measure. |
| `d_area` | Area-change contribution to cell mismatch. |
| `d_shape` | Shape-change contribution to cell mismatch. |
| `max_principal_strain` | Largest absolute principal strain required by the coherent mapping. |
| `score` | Configured geometric ranking; not an energy. |
| `is_pareto` | Membership in the saved full-population Pareto front. |

Write separate views for audit and selection:

```python
candidates.write_table("exports/candidates-all.csv")
pareto.write_table("exports/candidates-pareto.csv")
shortlist.write_table("exports/candidates-shortlist.csv")
```

When plotting dependencies are installed:

```python
candidates.plot_pareto(
    x="n_atoms_estimate",
    y="d_cell",
    save="exports/candidate-pareto.png",
)
```

## Interpretation

A candidate states that two bounded surface supercells can be represented by one coherent periodic interface cell under the admitted deformation and size limits.

Pareto optimality means no other admitted candidate is at least as good in all saved objectives and strictly better in one. It removes clearly inferior geometric tradeoffs. It does not identify a unique stable interface.

The search score combines configured geometric objectives. It is not a calculator energy, interface energy, work of adhesion, or experimental likelihood.

## Common variations

### Prefer smaller models

Lower `max_atoms`, inspect `n_atoms_estimate`, or rank an eligible set by size. Verify that the resulting strain remains acceptable.

### Prefer lower strain

Tighten `max_principal_strain` or filter the Pareto front after the search. Broader supercell enumeration may be needed to find low-strain alternatives.

### Build several tradeoffs

Keep several Pareto candidates rather than collapsing the search to one model. Later registry, relaxation, and energy stages can change their ordering.

### Compare saved searches

```python
project.searches().to_table().display()
first = project.search("lif-li2o-small")
second = project.search("lif-li2o-broad")
```

Give each settings family a descriptive name so the comparison remains interpretable.

## Common problems

### No candidates were found

Check, in order:

1. that the intended exact surfaces and contact faces were selected;
2. whether the strain limit is too strict;
3. whether supercell bounds are too small;
4. whether the atom limit rejects all feasible cells; and
5. whether a coherent periodic model is plausible for this pair.

Broaden one bound at a time and record the scientific reason.

### The search is not buildable

Use `buildability_summary().explain()` to identify missing or incompatible candidate information. Do not bypass the check and attempt construction from incomplete data.

### Reusing a name raises a conflict

The saved search with that name has different identity-bearing inputs. Choose a new descriptive name or restore the original settings and surfaces.

### The candidate population is unexpectedly large

Tighten strain, supercell, atom, or candidate limits. Export the complete table before applying a narrower scientific filter.

## Exact API

- [`SearchSettings` and construction settings](../reference/api/inputs-settings.md)
- [`Project.search_interfaces`, `search`, `searches`, and `candidates`](../reference/api/project.md)
- [Saved searches and candidate collections](../reference/api/returned-objects.md)
- [Coherent matching and Pareto interpretation](../understand/coherent-matching.md)
