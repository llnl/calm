# CALM: Canonicalized Affine-invariant Lattice Matching for Interface Modeling

**CALM builds deterministic, symmetry-aware coherent solid-solid interface
models and preserves the scientific workflow that produced them.**

Starting from bulk crystal structures and explicit surface choices, CALM can
search symmetry-distinct commensurate surface cells, partition coherent strain,
construct atomistic interfaces, connect optional relaxation and energetic
analysis, and persist settings, identities, outputs, failures, and lineage in a
reopenable project.

This README is the repository entry point. CALM has a **single public API**
centered on `calm.open_project` and the typed `Project` object; detailed methods,
scientific assumptions, and support boundaries are documented separately.

| | |
| --- | --- |
| **Status** | Stable release |
| **Version** | `1.0.0` |
| **Python** | 3.10-3.12 |
| **Installation** | Source checkout |
| **Project compatibility** | Current format only; preserve and regenerate older incompatible projects |
| **License** | MIT |

## Try CALM

The recommended first experience uses the baseline science environment and does
not require a calculator:

```bash
conda env create -f environments/calm-science.yml
conda activate calm-science
python -m pip install -e . --no-deps
python environments/validate_environment.py --profile science
python examples/tutorials/first_interface.py \
  --work-dir examples/work/first-interface --reset
```

The tutorial loads package-owned LiF and Li2O structures through
`calm.tutorial_structure`, selects explicit `(100)` terminations, searches for
commensurate surface cells, and writes:

```text
examples/work/first-interface/first-interface.calm/  # reopenable scientific project
examples/work/first-interface/outputs/               # interface, table, and run summary
```

The resulting interface is **constructed and unrelaxed**. It is a geometric
starting structure, not an energetic or thermodynamic prediction.

Continue with [Build your first interface](docs/learn/first-interface.md) for
the public API, interpretation, and limits of each step. CALM never silently
chooses among multiple saved surface terminations.

## Workflow at a glance

```text
bulk structures and explicit surface terminations
  -> symmetry-distinct commensurate interface candidates
  -> coherent strain partitioning and interface construction
  -> registry refinement, relaxation, and energetic references
  -> datasets, campaigns, and reproducibility records
```

The first tutorial stops after interface construction. Three independent,
canonical programs under `examples/tutorials/` provide the intended learning
path: construct one interface, compare candidates on the Pareto front, then add
ASE-EMT refinement, relaxation, and explicit energy references. The ten
numbered scripts under [`examples/`](examples/README.md) remain the complete
sequential demonstration workflow.

## Find the right documentation

- **Install CALM:** choose the base, science, or calculator-provider environment in [Install CALM](docs/install.md).
- **Learn CALM:** follow the three-part sequence beginning with [Build your first interface](docs/learn/first-interface.md).
- **Use CALM:** open the workflow chapter for [projects](docs/use/projects.md), [surfaces](docs/use/surfaces.md), [searches](docs/use/searches.md), [construction and refinement](docs/use/build-refine.md), or [datasets and campaigns](docs/use/datasets-campaigns.md).
- **Understand the science:** begin with [Surface models](docs/understand/surface-models.md) and continue through coherent matching, strain, registry, relaxation, and energetics.
- **Look something up:** use the [public API](docs/reference/public-api.md), [supported scope](docs/reference/supported-scope.md), [calculator support](docs/reference/calculator-support.md), or troubleshooting pages.
- **Run the complete demonstration:** use the numbered [examples](examples/README.md).

The [documentation home](docs/index.md) is the entry point for the user manual.
Its Learn, Use CALM, Understand, and Reference paths separate guided learning,
task execution, scientific interpretation, and exact lookup. The remaining
publication gate is the final strict build and clean-environment verification.

## Installation alternatives

### Import-light base package

For project creation, reopening, queries, and reproducibility manifests without
atomistic construction dependencies:

```bash
python -m pip install -e .
python environments/validate_environment.py --profile base
```

The base package requires only NumPy and SQLAlchemy. Atomistic geometry,
crystallography, and matching require the science environment used by the
geometry tutorials.

### Calculator-provider environments

Registered calculator families are `ase`, `chgnet`, `grace`, `mace`, and
`lammps`. Registration, dependency availability, qualification evidence, and
scientific suitability are separate concerns.

The baseline `ase` and `lammps` boundaries start from `calm-science.yml`;
LAMMPS additionally requires an external runtime and compatible potential
files. CALM maintains one source-checkout recipe for each registered pip-managed
ML provider. For example:

```bash
conda env create -f environments/calm-grace.yml
conda activate calm-grace
python -m pip install -e . --no-deps
python environments/validate_environment.py --provider grace
```

The maintained ML-provider recipes are `calm-chgnet.yml`, `calm-grace.yml`, and
`calm-mace.yml`. They are maintained environment definitions derived from
`pyproject.toml`, not lock files or evidence that a model is scientifically
appropriate. See the
[source-environment guide](environments/README.md), [calculator provider support
matrix](docs/reference/calculator-support.md), and [conda package
notes](conda-recipe/README.md).

A package-registry installation command is not documented yet. The tagged Git
source is currently the supported repository distribution; wheel, source-
distribution, and conda-package workflows are not yet the documented user
installation path.

## Scientific and execution boundaries

Geometric suitability does not establish thermodynamic, mechanical, or kinetic
stability. CALM does not silently choose surface terminations, calculators,
reference states, or thermodynamic conventions. Real relaxation and energy
workflows require a user-supplied calculator appropriate for the material
system.

Calculated thermodynamic references require fixed-cell relaxed interfaces. The
supported workflow includes strained-bulk references, unrelaxed isolated-surface
references, and independently relaxed fixed-cell surface references for work of
adhesion. CALM does not fabricate missing reference energies.

Surface characterization does not infer polarity, oxidation states, dipoles,
surface energies, or scientific termination rankings. Broader
scientific-analysis workflows such as bonding, reconstruction, defects, and
charge-transfer analysis remain outside the current scope.

CALM executes **synchronously** in the calling process; it does not contain a
task queue or background worker. The complete capability and limitation
inventory is maintained on the [supported scope](docs/reference/supported-scope.md) page
rather than repeated here.

## Development and support

Install the development and science dependencies from the repository root:

```bash
python -m pip install -e ".[dev,science]"
```

Run the primary local gates with:

```bash
git diff --check
python -m ruff check .
pytest -q
python -m pytest -q
python -m mkdocs build --strict
```

The public API consistency checks and other qualification reports under
`engineering/qualification/` are maintainer-controlled evidence. Documentation
changes do not by themselves broaden the reviewed workflow scope. Report
concrete defects through the project [issue tracker](https://czgitlab.llnl.gov/weitzner/calm/-/issues).

## Contributing

Contributing to CALM is straightforward. Fork the repository, make your updates, and submit a pull request.

Note, your PR must:

1. Make develop the destination branch
2. Pass CALM's unit tests, documentation tests, and package build tests
3. Be PEP 8 compliant

## License

CALM is distributed under the terms of the [MIT License](LICENSE). See [MIT License](LICENSE) and [NOTICE](NOTICE) for details.

All new contributions must be made under the MIT license.

SPDX-License-Identifier: MIT

LLNL-CODE-2024998
