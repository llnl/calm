# Projects

<p class="calm-lede">
Create a reopenable CALM study, inspect its saved workflow state, trace how results were produced, and preserve enough evidence to reproduce the study later.
</p>

## Outcome

A CALM project is the working record for one scientific study. It saves user inputs, workflow settings, results, and the relationships among them so that work can be reopened rather than reconstructed from filenames or notebook state.

This chapter shows how to:

- create or reopen a project;
- inspect which workflow stages have been completed;
- use names and stable identifiers without guessing;
- trace the lineage of a result;
- write and verify a reproducibility manifest; and
- recover safely when a project was created by an incompatible CALM version.

## When to use it

Use a project whenever later work must refer to an earlier CALM result. Surface generation refers to saved materials, interface searches refer to exact surfaces, and relaxation and energy calculations refer to saved interfaces. A project is therefore the normal boundary for a continuing study.

A temporary in-memory workflow may be useful for experimentation, but it is not a substitute for a saved project when results must be reopened, compared, or audited.

## Prerequisites

Choose a project directory that belongs to the study and is not used as a general output folder. The tutorial programs place their projects beneath `examples/work/`; a research project can live wherever your study data are managed.

```python
from pathlib import Path

from calm import open_project

project_path = Path("interface-study.calm")
project = open_project(project_path)
print(project.summary())
```

Opening the same path later returns the same saved study. `open_project()` creates the project when the directory does not yet exist.

## Scientific decisions

### Define the boundary of one study

A project should contain objects that belong to one coherent scientific investigation. Reusing a project is helpful when results share materials, surfaces, calculator configuration, and provenance. Separate projects are clearer when studies use unrelated material systems or incompatible modeling assumptions.

### Name objects for scientific meaning

User-assigned names should communicate their role, for example:

```text
Cu-reference
Cu-EMT-optimized
Cu-100
cu-ni-100-search
cu-ni-interface_0000
```

Names are convenient selectors. CALM also provides:

- `id_short`, a compact identifier for tables and interactive work; and
- `uid_full`, the complete stable identifier used for exact provenance.

Do not infer scientific equivalence from similar names. Conversely, two labels may refer to structurally different objects.

### Decide what evidence must be portable

A project saves CALM-managed workflow state. Reproducibility may additionally depend on calculator models, external files, software versions, and generated artifacts. The reproducibility manifest summarizes the evidence CALM can identify; it does not embed every external dependency automatically.

## Minimal procedure

### Inspect the current project state

Collections provide tables, filters, and exact lookup operations:

```python
project.materials().to_table(title="Materials").display()
project.surfaces().to_table(title="Surfaces").display()
project.searches().to_table(title="Searches").display()
project.interfaces().to_table(title="Interfaces").display()
```

An empty collection is a valid statement that a stage has not yet produced results.

Retrieve one object by an exact name, short identifier, or full identifier:

```python
material = project.material("Cu-EMT-optimized")
interface = project.interface("cu-ni-interface_0000")
```

CALM raises an ambiguity error rather than selecting arbitrarily when a query matches more than one object.

### Trace a result

```python
lineage = project.lineage(interface, direction="both", depth=3)
for row in lineage.to_rows():
    print(row)
```

Use upstream lineage to answer questions such as:

- Which candidate produced this interface?
- Which surfaces and materials produced that candidate?
- Which relaxation or energy run used this interface?

Use downstream lineage to find calculations and datasets derived from a result.

### Record reproducibility evidence

```python
manifest = project.write_reproducibility_manifest(overwrite=True)
print(manifest.summary())

verification = project.verify_reproducibility_manifest()
print(verification.summary())
verification.raise_for_errors()
```

Write a new manifest after a study reaches a meaningful checkpoint. Verification compares the recorded snapshot with the current project and runtime evidence.

## Inspect the result

A useful project inspection sequence is:

```python
print(project.summary())
print(project.runs(limit=20).to_table())
print(project.artifacts().to_table())
```

For one run, inspect attached files and follow-up work:

```python
run = project.run("<run short ID or full UID>")
project.run_artifacts(run.uid_full).to_table().display()
project.followups(run=run.uid_full).to_table().display()
```

Tables are views of public project objects. They are not instructions to edit files inside the project directory.

## Interpretation

Project persistence communicates **workflow continuity and lineage**, not scientific correctness. Reopening a project tells you which inputs and results CALM saved. It does not establish that the chosen terminations, coherent cell, calculator, reference convention, or finite-size assumptions are physically appropriate.

A successful manifest verification means the checked evidence is consistent with the recorded snapshot. It does not guarantee that an unavailable external calculator model or manually managed input can be reconstructed unless that dependency was preserved separately.

## Common variations

### Save project-wide calculator defaults

```python
from calm import Potential

project.configure(
    mlip="ase",
    calculator=Potential(family="ase", model="EMT"),
)
```

Defaults reduce repetition, but each calculator-backed result should still be interpreted using its saved calculator identity and settings.

### Export selected scientific objects

Use workflow-specific helpers rather than copying files from the project directory:

```python
project.export_materials("Cu-EMT-optimized", directory="exports/materials")
project.export_surfaces("<surface ID>", directory="exports/surfaces")
```

Constructed interface collections provide `write_structures()`, and datasets provide `export()`.

### Inspect only one workflow type or status

```python
completed_relaxations = project.relaxation_runs(status="completed")
failed_energy_runs = project.energy_runs(status="failed")
```

Filtering saved runs is preferable to deciding success from the presence of an output file.

## Common problems

### A lookup matches multiple objects

Use a short or full identifier from the relevant collection table, or add exact filters such as material, Miller index, or termination. CALM does not choose the first match.

### The project is an older or incompatible project

Preserve the original directory unchanged. Create a new project with the current CALM version, then rerun the supported workflows from retained scientific inputs and exports. Do not edit project files in an attempt to convert the project manually.

### A project path exists but is not a CALM project

Choose an empty directory or the directory of an existing CALM project. Do not place a project inside a directory already used for unrelated files.

### Verification reports changes

Read the report before overwriting the manifest. Some differences may be expected after new work; others may indicate changed dependencies, missing artifacts, or altered project state.

## Exact API

- [`open_project`, project state, lineage, and manifests](../reference/api/project.md)
- [Returned collections, lineage graphs, and verification reports](../reference/api/returned-objects.md)
- [Public exceptions](../reference/api/exceptions-utilities.md)
