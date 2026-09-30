# Calculator support

<p class="calm-lede">
Distinguish a registered CALM provider from an installed dependency, a constructible calculator, a compatible model, and a scientifically suitable potential.
</p>

## Purpose

Calculator-backed workflows include material optimization, energy-based refinement, structural relaxation, raw total-energy evaluation, and calculated thermodynamic references. This page defines the current provider families and the checks required before interpreting their results.

## Canonical import or convention

Users describe calculators with the top-level `Potential` input:

```python
from calm import Potential, open_project

project = open_project("study.calm")
project.configure(
    mlip="ase",
    calculator=Potential(family="ase", model="EMT"),
)
```

Use the exact lowercase provider family and one model accepted by that provider. Do not import calculator providers from internal CALM modules.

## Exact behavior

### Four separate support questions

Treat these as independent questions:

1. **Registered:** Does CALM have a provider adapter for the family?
2. **Available:** Are the provider package and external runtime installed in this environment?
3. **Compatible:** Can the selected model evaluate the elements, structure, properties, and protocol requested?
4. **Scientifically suitable:** Is the model accurate enough for the material system and conclusion being drawn?

Passing one question does not answer the next.

### Registered provider families

The current registry contains five families.

| Family | CALM boundary | Installation route | Important limitations |
| --- | --- | --- | --- |
| `ase` | ASE built-in `EMT`, `LJ`, and `Morse` calculators | Baseline science environment | Intended for demonstrations, tests, and simple baselines; model element coverage and physical validity are limited |
| `chgnet` | CHGNet pretrained models | `calm-chgnet.yml` or the `chgnet` extra | Requires a supported CHGNet model and its runtime stack |
| `grace` | GRACE foundation models through `tensorpotential` | `calm-grace.yml` or the `grace` extra | Provider/model availability does not establish interface accuracy |
| `mace` | MACE foundation models through `mace_mp` | `calm-mace.yml` or the `mace` extra | Device, model download, precision, and stress support must match the workflow |
| `lammps` | ASE `lammpsrun` or `lammpslib` adapter | Baseline science environment plus an external LAMMPS runtime and potential files | CALM cannot validate external executables, libraries, commands, licensed files, or parameterization |

The source-checkout environment guide at `environments/README.md` gives installation and validation commands for each family.

### Environment validation

From a source checkout, validate one dependency profile explicitly:

```bash
python environments/validate_environment.py --profile base
python environments/validate_environment.py --profile science
python environments/validate_environment.py --provider ase
python environments/validate_environment.py --provider chgnet
python environments/validate_environment.py --provider grace
python environments/validate_environment.py --provider mace
python environments/validate_environment.py --provider lammps
```

The validator checks the selected dependency layer, provider registration and availability, version identity, and a disposable project create/reopen smoke test. It does not run model inference or certify scientific accuracy.

### Provider and model selection

A `Potential` specification should preserve all choices required to reconstruct the calculator:

```python
from calm import Potential

potential = Potential(
    family="mace",
    model="medium-mpa-0",
    device="cpu",
    options={"default_dtype": "float64"},
)
```

The exact accepted options belong to the provider and installed upstream version. CALM rejects unsupported or ambiguous option ownership rather than silently dropping requested settings.

A live calculator object by itself is not a portable calculator specification for a saved workflow. Use a reconstructible `Potential` or the calculator identity already saved with a compatible result.

### Calculator-backed workflow requirements

| Workflow | Calculator requirement |
| --- | --- |
| Project creation, queries, lineage, and manifests | None |
| Material import | None |
| Material optimization | Energy, forces, and any requested stress/cell behavior |
| Surface generation | None |
| Coherent search and interface construction | None |
| Geometric strain-partition scan | None |
| Energy-based strain or registry refinement | Energy support for every sampled structure |
| Fixed-cell atomic relaxation | Energy and force support |
| Variable-cell relaxation | Energy, force, and reliable stress support |
| Raw energy | Energy support |
| Calculated references | The same reconstructible calculator identity required by the selected reference process |

### Scientific compatibility checklist

Before interpreting a calculator-backed result, verify:

- all chemical elements are supported;
- surfaces, strained cells, short contacts, and interface environments are within the model's intended domain;
- the requested stress convention is supported before enabling cell relaxation;
- charge, spin, magnetic state, long-range electrostatics, dispersion, and other relevant physics are represented appropriately;
- energy zeros and reference calculations are internally compatible;
- device and precision choices are recorded;
- model and external potential files are preserved for portability; and
- numerical convergence has been checked independently of model validity.

A model that runs without raising an exception can still give scientifically misleading results.

### Reference-calculation support

All current public energy formulas expose a first-class calculated-reference workflow:

| Formula | Calculated reference kinds | Required scientific consistency |
| --- | --- | --- |
| `interface_excess_strained_bulk` | `strained_bulk_a`, `strained_bulk_b` | Exact strain partition, integer formula-unit counts, compatible calculator identity |
| `work_of_separation_unrelaxed_surfaces` | `isolated_surface_a`, `isolated_surface_b` | Fixed-cell interface state and corresponding unrelaxed cleaved slabs |
| `work_of_adhesion_relaxed_surfaces` | `relaxed_surface_a`, `relaxed_surface_b` | Fixed-cell relaxed interface, independently relaxed fixed-cell surfaces, same calculator identity |

Inspect the live capability rather than maintaining separate assumptions in user code:

```python
capability = convention.reference_capability()
print(capability.summary())
capability.raise_for_calculated_references()
```

When a required reference is missing, failed, unconverged, or incompatible, the derived quantity should remain unavailable with an explanation. Do not replace it with a number from a different calculator or reference process.

### Common provider failures

| Symptom | Likely layer | First action |
| --- | --- | --- |
| Unknown family | Registration/specification | Use one of the five exact registered family names |
| Optional dependency missing | Availability | Install the matching environment or project extra |
| Calculator construction fails | Specification/upstream API | Check model, device, and option names against the selected provider |
| Evaluation fails on a structure | Compatibility/runtime | Check elements, geometry, external files, memory, device, and upstream traceback |
| Relaxation converges to an implausible state | Scientific suitability/model domain | Reassess model, constraints, initial geometry, cell size, and reference calculation |
| Reference result is unavailable | Workflow compatibility | Inspect `reference_capability()`, calculator identity, convergence, cell constraints, and required reference kinds |

## Related workflow

- [Install CALM](../install.md) provides the supported base, science, and calculator-provider installation paths.
- [Materials](../use/materials.md) explains calculator-backed bulk preparation.
- [Build and refine interfaces](../use/build-refine.md) explains calculator-free and calculator-backed refinement metrics.
- [Relax and evaluate](../use/relax-evaluate.md) gives the operational calculator workflow.
- [Supported scientific scope](supported-scope.md) states what calculator completion does and does not establish.
- [Calculation and data troubleshooting](troubleshooting-calculations.md) routes common failure symptoms.
- [Inputs and settings](api/inputs-settings.md) gives the exact `Potential`, `RelaxSettings`, and energy-reference signatures.
