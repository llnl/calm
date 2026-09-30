# Conda environments

CALM is under active development and supports multiple machine-learning interatomic potential (MLIP) frameworks.
Several MLIP stacks are **mutually incompatible** (usually due to pinned PyTorch and/or e3nn versions).
To keep installations reliable and reproducible, this repository ships **one conda environment recipe per primary MLIP backend**.

Environment recipes live in `environments/`. They are installation targets, not the public calculator API. The first-class provider list is maintained in the [calculator provider support matrix](../reference/calculator_provider_support.md) and is checked against the CALM provider registry by architecture tests.

## Current provider status

CALM currently exposes first-class `CalculatorSpec.family` values for:

```text
ase
chgnet
grace
lammps
mace
```

The environment recipes also cover experimental or deferred framework stacks. Those stacks may be useful for custom scripts, model-cache preparation, or future provider work, but they are not first-class CALM calculator families unless they appear in the support matrix first-class table.

| Recipe | Status in CALM | Notes |
|---|---|---|
| `environments/calm-base.yml` | core / no MLIP provider stack | Structure generation, docs, tests, and ASE smoke workflows. |
| `environments/calm-chgnet.yml` | first-class provider environment | Installs CHGNet for `CalculatorSpec(family="chgnet")`. |
| `environments/calm-grace.yml` | first-class provider environment | TensorFlow / TensorPotential / GraceMaker stack for `family="grace"`. |
| `environments/calm-mace.yml` | first-class provider environment | MACE-MP stack for `family="mace"`; keep isolated from incompatible e3nn stacks. |
| `environments/calm-universal.yml` | compatible first-class bundle | Convenience environment for currently compatible first-class MLIP providers. |
| `environments/calm-full.yml` | broad development environment | Heavy environment for development and compatibility checks; not a promise that every installed framework has a CALM provider. |
| `environments/calm-m3gnet.yml` | environment-only / experimental | Installs framework dependencies; no first-class CALM provider yet. |
| `environments/calm-matgl.yml` | environment-only / experimental | Installs framework dependencies; no first-class CALM provider yet. |
| `environments/calm-sevennet.yml` | environment-only / planned | Useful for direct SevenNet experiments; no first-class CALM provider yet. |
| `environments/calm-nequip.yml` | environment-only / planned | NequIP/Allegro stacks generally require separate checkpoints and are not registered CALM providers yet. |
| `environments/calm-mattersim.yml` | environment-only / planned | Useful for direct MatterSim experiments; no first-class CALM provider yet. |
| `environments/calm-orb.yml` | deferred / isolated | Orb remains isolated after dependency validation showed conflict risk with TensorFlow/GraceMaker protobuf constraints. |

## Model compatibility rules

Follow this simple rule:

- Pick **exactly one** primary incompatible MLIP backend per environment.
- Add only optional models known to be compatible with that environment.
- Treat framework installation recipes separately from first-class CALM calculator-provider support.

For the provider status of each backend, see the [calculator provider support matrix](../reference/calculator_provider_support.md).

### Broadly reusable or environment-specific first-class models

- **ASE** (`family="ase"`) is intended for smoke tests and lightweight reference calculations.
- **LAMMPS via ASE** (`family="lammps"`) is first-class in the CALM registry, but still requires a local LAMMPS executable and potential configuration outside Python packaging.
- **CHGNet** (`family="chgnet"`) is a first-class CALM provider and is usually the easiest PyTorch MLIP provider to add to an existing CALM environment.
- **GraceMaker** (`family="grace"`) is a first-class TensorPotential/TensorFlow provider and should be installed in TensorFlow-compatible environments.
- **MACE-MP** (`family="mace"`) is a first-class PyTorch/e3nn provider, but its dependency pins should be isolated from SevenNet and NequIP/Allegro stacks.

### Deferred or environment-only frameworks

- **Orb** (`pip install orb-models`) is **deferred** as a CALM provider and should be kept isolated from TensorFlow/GraceMaker environments because its current dependency stack can conflict with TensorFlow protobuf constraints.
- **M3GNet**, **MatGL**, **SevenNet**, **NequIP/Allegro**, and **MatterSim** have environment recipes for experimentation or future provider work, but are not first-class CALM `CalculatorSpec.family` values today.

### Mutually incompatible primary backends

Choose **one** per environment:

- **MACE** (PyTorch 2.4.x + e3nn==0.4.4)
- **SevenNet** (PyTorch 2.4.x + e3nn>=0.5.9)
- **NequIP / Allegro** (PyTorch 2.1.x + e3nn 0.5.x)
- **MatterSim** (PyTorch 2.1.x stack)

Common conflict patterns:

| Model Pair | Typical Conflict |
|---|---|
| MACE vs SevenNet | e3nn version (0.4.4 vs >=0.5.9) |
| MACE/SevenNet vs NequIP/Allegro | PyTorch version (2.4.x vs 2.1.x) |
| MatterSim vs others | PyTorch / dependency skew |
| Orb vs GraceMaker/TensorFlow | protobuf / TensorFlow dependency constraints |

## Base environment

If you only need structure generation, query/reporting workflows, docs, or tests, use the base environment:

- Env file: `environments/calm-base.yml`
- Purpose: core CALM dependencies **without** any MLIP backend

Create and install CALM:

```bash
conda env create -f environments/calm-base.yml
conda activate calm-base
python -m pip install -U pip
python -m pip install -e . --no-deps
```

The environment recipes intentionally include **IPython**, **Jupyter**, and **MkDocs** so you can run notebooks and build documentation without adding extra packages by hand.

## First-class provider environments

### CHGNet

- Env file: `environments/calm-chgnet.yml`
- CALM family: `chgnet`
- Default CALM model: `0.3.0`

Create and install CALM:

```bash
conda env create -f environments/calm-chgnet.yml
conda activate calm-chgnet
python -m pip install -U pip
python -m pip install -e . --no-deps
```

Warm the pretrained model cache:

```python
from chgnet.model import CHGNet

_ = CHGNet.load(model_name="0.3.0")
```

### GRACE / GraceMaker

- Env file: `environments/calm-grace.yml`
- CALM family: `grace`
- Default CALM model: `GRACE-1L-OMAT`

Create and install CALM:

```bash
conda env create -f environments/calm-grace.yml
conda activate calm-grace
python -m pip install -U pip
python -m pip install -e . --no-deps
```

GraceMaker manages model files through its own tooling. Use the upstream GraceMaker commands for the exact model download workflow. A common local preparation step is:

```bash
grace_models download all
```

### MACE

- Env file: `environments/calm-mace.yml`
- CALM family: `mace`
- Default CALM model: `medium-mpa-0`
- Install strategy: conda-forge where possible, to avoid pip resolution/build issues on macOS/arm64

Create and install CALM:

```bash
conda env create -f environments/calm-mace.yml
conda activate calm-mace
python -m pip install -U pip
python -m pip install -e . --no-deps
```

Warm the pretrained model cache:

```python
from mace.calculators import mace_mp

_ = mace_mp(model="medium", device="cpu")
```

### LAMMPS via ASE

- CALM family: `lammps`
- Env route: base CALM dependencies plus an external LAMMPS runtime

The CALM provider uses ASE's LAMMPS calculator interface. Python packaging can install ASE, but it cannot guarantee that your local `lmp` executable, MPI runtime, or potential files are configured correctly. Validate LAMMPS outside CALM before running production workflows.

## Environment-only recipes

The following sections are for direct framework experimentation or future provider development. They are not first-class CALM `CalculatorSpec.family` values today.

### M3GNet / MatGL

- Env files: `environments/calm-m3gnet.yml`, `environments/calm-matgl.yml`
- Status: dependency-only / experimental

Use these recipes when testing framework imports or custom scripts. Do not write basic examples that pass M3GNet or MatGL as CALM calculator families unless a first-class provider has been added and documented.

### SevenNet

- Env file: `environments/calm-sevennet.yml`
- Status: environment-only / planned

Warm the pretrained model cache for direct SevenNet experiments:

```python
from sevenn.calculator import SevenNetCalculator

_ = SevenNetCalculator("7net-omni", modal="mpa")
```

### NequIP / Allegro

- Env file: `environments/calm-nequip.yml`
- Status: environment-only / planned

NequIP/Allegro are training/inference frameworks; there is no single canonical foundation model download. You typically provide a checkpoint path.

### MatterSim

- Env file: `environments/calm-mattersim.yml`
- Status: environment-only / planned

Warm the pretrained model cache for direct MatterSim experiments:

```python
from mattersim.forcefield import MatterSimCalculator

_ = MatterSimCalculator(device="cpu")
```

### Orb

- Env file: `environments/calm-orb.yml`
- Status: deferred / isolated

Keep Orb isolated from TensorFlow/GraceMaker environments until CALM has an explicit provider and model-cache policy. Do not present Orb as a supported CALM calculator family in user-facing workflows.

## CUDA notes (Linux / NVIDIA)

The shipped environment recipes are **CPU/MPS-first** so they work unmodified on macOS and CPU machines.

On Linux with an NVIDIA GPU, install a CUDA-enabled PyTorch build appropriate for your backend, driver, and hardware. For example:

```bash
# After creating + activating your chosen environment
conda install -c pytorch -c nvidia pytorch-cuda=11.8
```

Exact CUDA/PyTorch combinations depend on your driver and hardware. Consult the PyTorch installation selector and the upstream framework documentation when you need a different CUDA version.

## Full environment matrix

See `environments/README.md` for the complete recipe list and `docs/../reference/calculator_provider_support.md` for the authoritative first-class/deferred provider split.
