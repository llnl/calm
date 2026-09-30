# Calculation and data troubleshooting

<p class="calm-lede">
Diagnose calculator construction, relaxation, energy references, datasets, exports, and campaigns without hiding failed scientific states or substituting incompatible results.
</p>

## Purpose

This index covers calculator-backed workflows and downstream study management. CALM often saves per-target failure information before raising an exception, so inspect run and result tables before assuming that no evidence was recorded.

## Canonical import or convention

Start by separating the workflow layers:

```python
project.relaxation_runs().to_table(view="all").display()
project.relaxation_results().to_table(view="all").display()
project.reference_energy_runs().to_table(view="all").display()
project.energy_runs().to_table(view="all").display()
project.energy_results().to_table(view="all").display()
project.thermodynamic_results().to_table(view="all").display()
```

A calculator-construction failure, a relaxation failure, a raw-energy failure, and an unavailable derived quantity are different problems and require different remedies.

## Exact behavior

### Calculator and material-optimization symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| The calculator family is unknown | The family is not registered or is misspelled | Use one of `ase`, `chgnet`, `grace`, `lammps`, or `mace` | [Relax/evaluate: unavailable or incompatible calculator](../use/relax-evaluate.md#the-calculator-is-unavailable-or-incompatible) and [calculator support](calculator-support.md#registered-provider-families) |
| An optional dependency is missing | The provider environment is incomplete | Install and validate the matching environment | [Calculator support: environment validation](calculator-support.md#environment-validation) |
| Calculator construction fails | Model, device, options, external files, or upstream API are incompatible | Inspect the full chained exception and reconstruct the `Potential` explicitly | [Calculator support: provider selection](calculator-support.md#provider-and-model-selection) |
| Material optimization fails immediately | Calculator construction, structure conversion, or property evaluation failed | Inspect the saved material, calculator identity, and traceback | [Materials: optimization failure](../use/materials.md#optimization-fails-immediately) |
| The calculator runs but the result is implausible | The model is outside its scientific domain | Stop interpretation and reassess model suitability, input geometry, constraints, and cell size | [Calculator support: scientific checklist](calculator-support.md#scientific-compatibility-checklist) |

### Relaxation symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| Relaxation does not converge | Poor starting geometry, insufficient steps, unsuitable constraints, or calculator failure | Inspect force history, final residual, overlaps, and per-target status before changing settings | [Relax/evaluate: nonconvergence](../use/relax-evaluate.md#relaxation-does-not-converge) |
| A completed run did not produce a relaxed interface | The terminal residual did not satisfy the declared convergence contract | Inspect the result status and convergence fields; do not relabel it manually | [Energetics: relaxation and convergence](../understand/energetics.md#relaxation-and-convergence) |
| Resume does not reuse a previous result | Calculator identity, settings, source stage, or target identity differs | Compare the exact saved specification; changed controls define different work | [Relax/evaluate: previous runs](../use/relax-evaluate.md#inspect-previous-runs) |
| Variable-cell relaxation fails or behaves poorly | Stress is unsupported or unreliable, or cell degrees of freedom are inappropriate | Return to fixed-cell relaxation unless variable-cell behavior is scientifically justified and supported | [Calculator support](calculator-support.md#calculator-backed-workflow-requirements) |

### Raw energy and reference symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| Raw energy is missing | The selected structure was not eligible or calculator evaluation failed | Inspect `energy_runs()` and `energy_results()` independently | [Relax and evaluate](../use/relax-evaluate.md#inspect-previous-runs) |
| A derived quantity is unavailable | Required raw/reference results are missing, failed, unconverged, or incompatible | Read the unavailable-result explanation and inspect `reference_capability()` | [Relax/evaluate: unavailable quantity](../use/relax-evaluate.md#a-derived-quantity-is-unavailable) |
| Interface and reference calculations use different protocols | Calculator identity, cell constraint, composition, or reference process differs | Recalculate a compatible set under one explicit convention | [Relax/evaluate: protocol mismatch](../use/relax-evaluate.md#reference-and-interface-calculations-use-different-protocols) |
| `work_of_adhesion_relaxed_surfaces` cannot create references | The interface used cell relaxation, lacks a saved structure, or has incompatible calculator evidence | Use a fixed-cell relaxed interface and independently relaxed fixed-cell slab references | [Supported scope: reference workflows](supported-scope.md#supported-energy-reference-workflows) |
| Strained-bulk excess energy rejects the structure | Exact integer formula-unit accounting is unavailable | Use a supported stoichiometric model or a different scientifically justified convention | [Energetics: strained-bulk excess](../understand/energetics.md#strained-bulk-interface-excess-energy) |
| A value has an unexpected sign or magnitude | Formula, area, multiplicity, reference states, termination, strain, registry, or calculator is inconsistent with the intended interpretation | Audit each term before assigning physical meaning | [Relax/evaluate: sign and magnitude](../use/relax-evaluate.md#a-value-has-an-unexpected-sign-or-magnitude) |

### Dataset symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| Dataset validation reports missing fields | Required source results, feature values, targets, structures, or units are absent | Inspect the validation report and source population before export | [Datasets: missing fields](../use/datasets-campaigns.md#dataset-validation-reports-missing-fields) |
| Related structures appear in different splits | The grouping key does not represent the leakage family | Redefine grouping and rebuild the dataset under a new declaration | [Datasets: leakage](../use/datasets-campaigns.md#related-structures-appear-in-different-splits) |
| Dataset creation raises an identity conflict | The name already belongs to different schema or split settings | Reopen the existing dataset or choose a new name for the changed declaration | [Datasets: identity conflict](../use/datasets-campaigns.md#dataset-creation-raises-an-identity-conflict) |
| An export destination already exists | Atomic export refuses accidental replacement | Choose a new destination or pass `overwrite=True` deliberately after validation | [Datasets: export](../use/datasets-campaigns.md#export-the-dataset) |
| ML readiness fails | Required joins, targets, grouping, splits, or structures are incomplete | Read the readiness report; do not edit exported tables as a repair | [Datasets: create and validate](../use/datasets-campaigns.md#create-and-validate-a-dataset) |

### Campaign symptoms

| Symptom | Likely cause | First action | Canonical guidance |
| --- | --- | --- | --- |
| One campaign case fails while others complete | The case has incompatible inputs, calculator behavior, or stage-specific failure | Inspect case-level failures and resume only the unchanged campaign specification | [Campaigns: failed case](../use/datasets-campaigns.md#a-campaign-case-fails-while-others-complete) |
| Campaign creation raises an identity conflict | The same name is bound to different ordered cases, stages, or settings | Reopen the matching campaign or create a new name | [Campaign definition](../use/datasets-campaigns.md#define-and-run-a-campaign) |
| Comparison rankings combine incompatible values | Cases use different formulas, units, calculators, reference processes, or missing metrics | Compare only scientifically compatible columns and leave missing values unranked | [Campaigns: incompatible rankings](../use/datasets-campaigns.md#campaign-rankings-combine-incompatible-values) |
| Resume repeats more work than expected | Case identity or stage settings changed | Compare the exact campaign declaration and saved case states | [Campaigns: resume behavior](../use/datasets-campaigns.md#reopen-campaign-results) |

### Scheduler and portability symptoms

CALM runs synchronously. A scheduler may invoke the same scripts, but it does not make simultaneous writes to one project safe automatically. Use one coordinated writer per project unless a specific workflow has been designed and tested otherwise.

When moving a study, transfer:

- the complete project directory;
- external calculator and potential files;
- model/version information;
- relevant exported structures and tables; and
- the environment information needed to reconstruct the calculator.

After transfer, reopen the project and verify the reproducibility manifest. A calculator family and model label alone do not guarantee that the same external model is available on another machine.

## Related workflow

- [Materials](../use/materials.md)
- [Build and refine interfaces](../use/build-refine.md)
- [Relax and evaluate](../use/relax-evaluate.md)
- [Datasets and campaigns](../use/datasets-campaigns.md)
- [Calculator support](calculator-support.md)
- [Supported scientific scope](supported-scope.md)
- [Public exceptions](api/exceptions-utilities.md)
