# Geometry and project troubleshooting

<p class="calm-lede">
Start from the user-visible symptom, perform the smallest safe diagnostic, and continue in the workflow chapter that owns the remedy.
</p>

## Purpose

This index covers project access, structure input, surfaces, searches, interface construction, and geometric refinement. It deliberately links to contextual explanations instead of duplicating complete procedures.

## Canonical import or convention

When diagnosing a saved workflow:

1. preserve the project directory;
2. inspect public collections and run tables;
3. use exact names or identifiers;
4. change settings under a new scientific identity when the problem definition changes; and
5. never repair a project by editing its internal files.

Useful first inspections are:

```python
print(project.summary())
project.materials().to_table().display()
project.surfaces().to_table().display()
project.searches().to_table().display()
project.interfaces().to_table().display()
```

## Exact behavior

### Project and lookup symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| A project path exists but CALM will not open it | The directory is not a current CALM project, is incomplete, or is incompatible | Preserve it unchanged and inspect the exact exception | [Projects: project path problems](../use/projects.md#a-project-path-exists-but-is-not-a-calm-project) |
| The project is older or incompatible | The saved format is outside the current compatibility boundary | Preserve the original, create a new project, and rerun supported workflows | [Projects: incompatible projects](../use/projects.md#the-project-is-an-older-or-incompatible-project) |
| A query matches more than one object | The name or filter is not unique | Inspect the collection table and select by `id_short` or `uid_full` | [Projects: ambiguous lookup](../use/projects.md#a-lookup-matches-multiple-objects) |
| A reproducibility check reports changes | Project state, artifacts, dependencies, or environment evidence changed | Read the report before writing a replacement manifest | [Projects: verification changes](../use/projects.md#verification-reports-changes) |
| An expected object is absent | The producing workflow did not complete, failed, or used a different project/name | Inspect the relevant collection and run tables | [Projects: inspect state](../use/projects.md#inspect-the-current-project-state) |

### Material and structure symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| A structure cannot be loaded | Unsupported format, missing ASE, invalid cell, or malformed file | Load it independently, inspect the traceback, and verify periodicity and cell vectors | [Materials: structure loading](../use/materials.md#the-structure-cannot-be-loaded) |
| A periodic bulk structure has a zero or singular cell | The input is not a valid three-dimensional periodic source | Correct the source structure before importing it | [Materials: periodicity](../use/materials.md#verify-periodicity-and-cell-meaning) |
| An optimized cell is physically unreasonable | Calculator, stress, constraints, or initial structure is unsuitable | Compare the input/output cells and reassess the calculator and relaxation settings | [Materials: unreasonable optimized cell](../use/materials.md#an-optimized-cell-is-physically-unreasonable) |
| Two material names are confusingly similar | Human-readable labels are not unique enough for interpretation | Rename future inputs and select existing objects by stable identifier | [Materials: similar names](../use/materials.md#two-materials-have-confusingly-similar-names) |

### Surface symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| More terminations were generated than expected | One Miller orientation admits several cleavage shifts or ordered face pairs | Inspect top/bottom labels and shifts before selecting one exact surface | [Surfaces: multiple terminations](../use/surfaces.md#more-terminations-were-generated-than-expected) |
| A surface query is ambiguous | Several surfaces share the material and Miller index | Add exact termination filters or use a stable identifier | [Surfaces: ambiguous query](../use/surfaces.md#a-surface-query-is-ambiguous) |
| The slab is empty or has incompatible periodicity | Invalid thickness/layer settings or a malformed source cell | Inspect the source material, orientation, layer count, and periodic flags | [Surfaces: invalid slab](../use/surfaces.md#the-slab-is-empty-or-has-incompatible-periodicity) |
| The wrong chemical face contacts the other material | The selected top/bottom orientation is reversed | Reinspect the ordered faces; side A uses top and side B uses bottom | [Surfaces: reversed contact face](../use/surfaces.md#the-chosen-contact-face-is-reversed) |
| The slab interacts with its periodic image | Vacuum is insufficient for the selected calculator or property | Increase vacuum and repeat a convergence check | [Surface-model limitations](../understand/surface-models.md#assumptions-and-limitations) |

### Search and candidate symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| No candidates were found | Bounds are too restrictive or the selected surfaces have no small coherent match | Inspect strain, supercell, atom, area, and candidate limits one at a time | [Searches: no candidates](../use/searches.md#no-candidates-were-found) |
| The search is reported as not buildable | Candidate geometry or required atomistic surface data is incomplete | Inspect buildability fields and the selected surfaces | [Searches: buildability](../use/searches.md#the-search-is-not-buildable) |
| Reusing a search name raises a conflict | The same name is already bound to different defining inputs | Reopen the matching search or choose a new name for changed settings | [Searches: identity conflict](../use/searches.md#reusing-a-name-raises-a-conflict) |
| The candidate population is unexpectedly large | Search bounds admit many supercell pairs or truncation occurs late | Reduce the scientific domain deliberately; do not rely on arbitrary post hoc deletion | [Searches: large populations](../use/searches.md#the-candidate-population-is-unexpectedly-large) |
| A preferred candidate disappears after filtering | A filter or view excludes it | Inspect the complete candidate collection, Pareto set, and each additional filter separately | [Compare candidates](../learn/compare-candidates.md#interpretation) |

### Construction and refinement symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| Atoms overlap after construction | Initial gap, contact faces, or registry is unsuitable | Inspect the interface geometry and adjust the scientifically meaningful construction setting | [Build/refine: overlaps](../use/build-refine.md#atoms-overlap-after-construction) |
| Refinement reports no eligible interfaces | The requested source stage or collection is empty | Inspect built and strain-partitioned interface collections before refining | [Build/refine: no eligible interfaces](../use/build-refine.md#refinement-reports-no-eligible-interfaces) |
| Registry results change between runs | Seed or stochastic controls differ | Record and reuse the complete `RegistrySettings`, including the seed | [Build/refine: reproducibility](../use/build-refine.md#registry-refinement-is-irreproducible) |
| The requested refinement metric is unavailable | A calculator-backed metric was selected without compatible calculator results | Use a geometric metric or configure a scientifically suitable calculator | [Build/refine: unavailable metric](../use/build-refine.md#the-refinement-metric-is-unavailable) |
| A built model is larger than expected | Candidate area and slab thickness combine multiplicatively | Inspect candidate size before construction and tighten the search bounds if scientifically justified | [Surface supercells: user controls](../understand/surface-supercells.md#what-the-user-controls) |

### Escalating a reproducible defect

When the contextual remedy does not explain the failure, preserve:

- the CALM and Python versions;
- the public script or smallest reproducing code;
- the complete traceback;
- the public settings and object identifiers;
- whether ASE, SciPy, spglib, plotting, and calculator dependencies are installed; and
- a small non-sensitive structure or project when sharing is permitted.

Do not publish credentials, licensed potential files, access-controlled models, or sensitive project data.

## Related workflow

- [Projects](../use/projects.md)
- [Materials](../use/materials.md)
- [Surfaces and terminations](../use/surfaces.md)
- [Searches and candidates](../use/searches.md)
- [Build and refine interfaces](../use/build-refine.md)
- [Supported scientific scope](supported-scope.md)
- [Public exceptions](api/exceptions-utilities.md)
