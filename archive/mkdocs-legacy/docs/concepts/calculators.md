# Calculators

CALM does not implement an interatomic potential itself. Instead, it delegates **energy/force/stress evaluation** to an [ASE](https://wiki.fysik.dtu.dk/ase/) `Calculator`.

To make this reproducible and serializable in workflows, CALM represents “how to build a calculator” as a small, JSON-serializable spec:

 - [`CalculatorSpec`](../reference/public_api.md) encodes the calculator backend (`family`), model name (`model`), and any backend-specific keyword arguments.
 - [`get_calculator`](../reference/public_api.md) converts a `CalculatorSpec` into a live ASE calculator by dispatching to a registered **provider**.

If you are using CALM with MLIP frameworks, start by choosing an appropriate conda environment recipe (several frameworks pin incompatible dependencies). See [Conda environments](../getting-started/conda_environments.md).

## Built-in calculator families

These are the calculator families currently exposed as first-class backends in CALM. The user-facing source of truth is the [calculator provider support matrix](../reference/calculator_provider_support.md), which is checked against the provider registry by architecture tests.


| `CalculatorSpec.family` | Provider | Notes |
|---|---|---|
| `chgnet` | CHGNet via `chgnet.model.dynamics.CHGNetCalculator` | Pretrained universal MLIP; default model is `0.3.0` |
| `grace` | GRACE / GraceMaker via `tensorpotential` | Foundation-model potential; models can be downloaded via `grace_models …` |
| `mace` | MACE-MP via `mace` | Foundation-model potential; default model is `medium-mpa-0` |
| `lammps` | LAMMPS via ASE | Requires a local/external LAMMPS install and an ASE LAMMPS calculator configuration |
| `ase` | ASE reference calculators | Intended for smoke tests (e.g. `emt`) and lightweight prototyping |

Additional environment recipes are provided under `environments/` for deferred or environment-only frameworks such as Orb, SevenNet, NequIP/Allegro, MatterSim, MatGL, and M3GNet. Those frameworks are installable for experiments or custom scripts, but are not first-class `CalculatorSpec` families unless they appear in the first-class provider table.

## Creating and using calculators

### Minimal example

```python
from calm.calculators import CalculatorSpec, get_calculator

spec = CalculatorSpec(family="grace", model="GRACE-1L-OMAT", device="cpu")
calc = get_calculator(spec)

# `calc` is a standard ASE Calculator
print(type(calc))
```

### Attaching to ASE Atoms

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)

spec = CalculatorSpec(family="ase", model="emt")
atoms.calc = get_calculator(spec)

energy = atoms.get_potential_energy()
forces = atoms.get_forces()
```

## Availability checks

Calculator availability depends on which optional dependencies are installed in your current Python environment.

```python
from calm.calculators import list_calculator_availability

for avail in list_calculator_availability():
    status = "OK" if avail.available else "MISSING"
    detail = "" if avail.available else (avail.error_message or "")
    print(f"{avail.family:8s} {status}  {detail}")
```

For workflow code that should fail fast with a clear error message:

```python
from calm.calculators import CalculatorSpec, require_calculator_spec_available

spec = CalculatorSpec(family="mace", model="medium-mpa-0")
require_calculator_spec_available(spec)
```

## Backend notes

### CHGNet

- **Family:** `chgnet`
- **Typical use:** lightweight pretrained universal MLIP calculations via CHGNet.
- **Dependencies:** `chgnet` and its PyTorch/pymatgen stack.

CALM's CHGNet provider loads pretrained models with `CHGNet.load(model_name=...)` and wraps them in `CHGNetCalculator`. The default model is `0.3.0`; `r2scan` and `0.2.0` are also listed as known upstream aliases.

```python
from calm.calculators import CalculatorSpec, get_calculator

spec = CalculatorSpec(family="chgnet", model="0.3.0", device="cpu")
calc = get_calculator(spec)
```

### Deferred: Orb

Orb remains an environment-level investigation target rather than a first-class CALM calculator family. A validation attempt with `orb-models` showed that its current dependency stack can install `protobuf` versions incompatible with TensorFlow/GraceMaker environments. Keep Orb isolated in a dedicated environment until CALM adds a tested provider and model-cache policy.

### GRACE

- **Family:** `grace`
- **Typical use:** fast, high-quality relaxations/MD as a surrogate for DFT.
- **Dependencies:** `tensorpotential` plus the GraceMaker model package.

Model download is managed by the GraceMaker tooling (for example, `grace_models download all`). See the upstream GraceMaker documentation for the authoritative commands.

### MACE

- **Family:** `mace`
- **Typical use:** fast, high-quality relaxations/MD using MACE-MP.
- **Dependencies:** `mace` / `mace-torch` (and a compatible `e3nn` / PyTorch stack).

CALM’s MACE provider uses `mace.calculators.mace_mp` and defaults to `medium-mpa-0`.

### LAMMPS

- **Family:** `lammps`
- **Model:** `lammpsrun`
- **Typical use:** classical potentials, rapid prototyping, or legacy force fields.

The LAMMPS backend is implemented via ASE’s LAMMPS calculator interface. You must have LAMMPS installed and accessible via a command-line executable.

Example (illustrative; details depend on your LAMMPS build and potential files):

```python
from calm.calculators import CalculatorSpec, get_calculator

spec = CalculatorSpec(
    family="lammps",
    model="lammpsrun",
    # Forwarded to ASE's LAMMPS calculator.
    command="lmp -in in.lammps",
    parameters={"pair_style": "eam", "pair_coeff": ["* * Al.eam"]},
)
calc = get_calculator(spec)
```

### ASE reference calculators

- **Family:** `ase`
- **Model:** `emt`

ASE reference calculators are primarily intended for unit tests, smoke tests, and lightweight experimentation.

## Extending CALM with new calculator families

CALM’s calculator layer is provider-based. To add a new family:

1. Implement a provider that can build an ASE calculator from a `CalculatorSpec`.
2. Register the provider in the calculator registry.
3. Add documentation and an environment recipe if the dependency stack is complex.

The environment recipes in `environments/` are the recommended way to manage mutually-incompatible MLIP dependency stacks.
