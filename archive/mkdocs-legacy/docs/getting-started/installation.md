# Installation

CALM is under active development and is typically installed from source.

If you plan to use CALM with machine-learning interatomic potential (MLIP) backends, we recommend installing CALM into a **backend-specific conda environment**. Many MLIP frameworks have mutually incompatible dependency constraints (most commonly PyTorch/e3nn and, on GPUs, CUDA toolchain constraints).

For a detailed backend matrix and the available environment recipes, see:

- [Conda environments for MLIP backends](conda_environments.md)

## Prerequisites

- Python **3.10+**
- A working conda installation (Miniforge/Mambaforge recommended)

## Recommended: conda environment + source install

From the repository root:

```bash
# 1) Create ONE backend-specific environment
conda env create -f environments/calm-base.yml
conda activate calm-base

# 2) Install CALM from source
pip install -e . --no-deps
```

You can substitute `calm-base.yml` with any backend environment file (for example, `calm-mace.yml`, `calm-sevennet.yml`, `calm-nequip.yml`, etc.).

### Verify the install

```bash
python -c "import calm; print('calm import OK')"
```

## Alternative: pip-only install

If you only need the core CALM functionality and want a pure pip workflow, you can install CALM into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

Optional dependency groups are defined in `pyproject.toml` under `[project.optional-dependencies]`.

Backends that are currently exposed as first-class `CalculatorSpec` families are also listed in the [calculator provider support matrix](../reference/calculator_provider_support.md):

- `ase` and `lammps` are available from the base install today; `lammps` still requires a usable local/external LAMMPS runtime configuration.
- `pip install -e ".[chgnet]"` (CHGNet; family `chgnet`)
- `pip install -e ".[grace]"` (GRACE / GraceMaker; family `grace`)
- `pip install -e ".[mace]"` (MACE-MP; family `mace`)

Additional extras such as `m3gnet` install framework dependencies for experimentation and for curated conda recipes, but are not currently first-class CALM calculator families. Orb remains deferred and should be kept in an isolated environment until its dependency policy is finalized.

In practice, we still recommend the conda environment recipes for MLIP backends because they make dependency constraints explicit and reproducible.
