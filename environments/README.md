# CALM source-checkout environments

This directory contains the conda environment specifications used to install and
validate CALM from a Git checkout. The Python package metadata in
`pyproject.toml` remains the dependency authority. These recipes are reviewed
projections of that metadata; they are not lock files and do not establish
scientific suitability or provider qualification.

CALM distinguishes three installation layers:

1. the import-light base package, which requires NumPy and SQLAlchemy;
2. the baseline science environment, which adds SciPy, ASE, and spglib; and
3. an optional calculator provider installed in its own environment.

Use one primary provider per environment. Broad `full` or `universal` bundles
are not maintained because TensorFlow, PyTorch, e3nn, accelerator, and model
requirements can conflict independently of CALM.

## Base package only

A plain Python environment is sufficient for project creation, reopening,
queries, and reproducibility manifests:

```bash
python -m pip install -e .
python environments/validate_environment.py --profile base
```

The base package does not install ASE, SciPy, spglib, plotting tools, notebooks,
documentation tools, or calculator runtimes.

## Baseline science environment

Use the single shared science recipe for geometry, crystallography, matching,
and ASE baseline calculators:

```bash
conda env create -f environments/calm-science.yml
conda activate calm-science
python -m pip install -e . --no-deps
python environments/validate_environment.py --profile science
```

The recipe uses only `conda-forge` and explicitly excludes configured default
channels for this environment. It includes `pip` only so the checked-out CALM
package can be installed after the compiled science stack is solved.

## Registered ML provider environments

Three registered provider families have dedicated source-checkout recipes:

| Family | Recipe | Provider package source |
| --- | --- | --- |
| `chgnet` | `calm-chgnet.yml` | `pyproject.toml` extra `chgnet` |
| `grace` | `calm-grace.yml` | `pyproject.toml` extra `grace` |
| `mace` | `calm-mace.yml` | `pyproject.toml` extra `mace` |

For example:

```bash
conda env create -f environments/calm-grace.yml
conda activate calm-grace
python -m pip install -e . --no-deps
python environments/validate_environment.py --provider grace
```

The provider package is installed by the recipe's pip phase from the same
requirement owned by the corresponding project extra. The recipe does not pin a
model, download model data, or prove that the provider is suitable for a
particular material system.

The `ase` provider uses `calm-science.yml`. The `lammps` provider also starts
from `calm-science.yml`, but it additionally requires an external LAMMPS runtime
and compatible potential files. Environment validation can confirm the CALM and
ASE adapter boundary; it cannot validate an external executable, shared
library, model file, accelerator driver, or scientific parameterization.

## Accelerator-specific provider stacks

CALM does not maintain a generic GPU recipe. CUDA, ROCm, Apple MPS, TensorFlow,
and PyTorch accelerator installation must follow the selected provider's
upstream instructions. Install that provider stack in a dedicated environment,
then install CALM without asking pip to resolve it again:

```bash
python -m pip install -e . --no-deps
python environments/validate_environment.py --provider <family>
```

## Development and documentation tools

Developer, test, notebook, and documentation packages are intentionally absent
from every runtime recipe. Install the reviewed project extras only where they
are needed:

```bash
python -m pip install -e ".[dev,science]"
python -m pip install -e ".[docs]"
```

## Frameworks without registered CALM providers

M3GNet, MatGL, SevenNet, NequIP/Allegro, MatterSim, and Orb are not registered
`Potential.family` values in the current CALM contract. CALM therefore does not
maintain source environment recipes for them. An independently managed
framework environment does not create a CALM provider or broaden CALM's
qualification claims.

## Validation boundary

Run one explicit validation profile after installation:

```bash
python environments/validate_environment.py --profile base
python environments/validate_environment.py --profile science
python environments/validate_environment.py --provider chgnet
python environments/validate_environment.py --provider grace
python environments/validate_environment.py --provider mace
python environments/validate_environment.py --provider ase
python environments/validate_environment.py --provider lammps
```

The validator checks the selected dependency layer, import availability, CALM
version identity, registered-provider availability, and a disposable project
create/reopen smoke test. It does not run model inference or certify scientific
adequacy.

Repository maintainers can verify the recipes and ownership contract without
solving the environments:

```bash
python engineering/qualification/check_source_environments.py --show-current
```

See [calculator provider support](../docs/reference/calculator-support.md)
for the distinction between registration, environment availability,
qualification evidence, and scientific responsibility.
