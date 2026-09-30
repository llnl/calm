# 08. Calculators

CALM evaluates energies and forces by constructing an **ASE calculator** from a small, serializable specification (`CalculatorSpec`). This tutorial shows:

- how to choose a calculator backend (`family`) and model (`model`),
- how to build the calculator with `get_calculator`, and
- how to check which backends are available in your current environment.

For environment setup (including mutually-incompatible MLIP dependency stacks), see [Conda environments](../getting-started/conda_environments.md).

## Quick reference

### Built-in calculator families

The concise table below lists the first-class families. For the full support and deferral policy, see the [calculator provider support matrix](../reference/calculator_provider_support.md).

| Family | What it builds |
|---|---|
| `chgnet` | CHGNet pretrained universal MLIP calculator |
| `grace` | GRACE / GraceMaker foundation-model calculator |
| `mace` | MACE-MP foundation-model calculator |
| `lammps` | LAMMPS calculator via ASE (requires external LAMMPS install) |
| `ase` | ASE reference calculators (e.g. EMT) |

## Building a calculator

```python
from calm.calculators import CalculatorSpec, get_calculator

spec = CalculatorSpec(family="ase", model="emt")
calc = get_calculator(spec)
```

`calc` is a standard ASE calculator. You can attach it to `ase.Atoms` objects as usual.

## Example: ASE EMT (smoke test)

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)
atoms.calc = get_calculator(CalculatorSpec(family="ase", model="emt"))

print("Energy (eV):", atoms.get_potential_energy())
```

This backend is intentionally lightweight and is useful for verifying your CALM install end-to-end.


## Example: CHGNet

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)

spec = CalculatorSpec(
    family="chgnet",
    model="0.3.0",  # CALM default for CHGNet
    device="cpu",   # or "cuda" / "mps" depending on your platform
)

atoms.calc = get_calculator(spec)
print("Energy (eV):", atoms.get_potential_energy())
```

CHGNet may download/load pretrained assets through its upstream model loader when the calculator is first constructed. Use the curated environment files when combining it with other MLIP frameworks.

## Deferred: Orb

Orb is not currently exposed as a first-class `CalculatorSpec.family` in CALM. Keep `orb-models` in an isolated environment if you are experimenting with it directly, especially when TensorFlow/GraceMaker is installed elsewhere.

## Example: GRACE

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)

spec = CalculatorSpec(
    family="grace",
    model="GRACE-1L-OMAT",
    device="cpu",  # or "cuda" on Linux/NVIDIA
)

atoms.calc = get_calculator(spec)
print("Energy (eV):", atoms.get_potential_energy())
```

GRACE models are managed by the GraceMaker tooling. If your environment is missing models, see the download instructions in [Conda environments](../getting-started/conda_environments.md).

## Example: MACE

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)

spec = CalculatorSpec(
    family="mace",
    model="medium-mpa-0",  # default in CALM if omitted
    device="cpu",         # or "cuda" / "mps" depending on your platform
)

atoms.calc = get_calculator(spec)
print("Energy (eV):", atoms.get_potential_energy())
```

MACE dependency stacks are sensitive to PyTorch/e3nn versions. Use the curated environment file (`environments/calm-mace.yml`) to avoid version conflicts.

## Example: LAMMPS via ASE

The `lammps` backend uses ASE’s LAMMPS calculator interface and requires a working LAMMPS installation.

A minimal example (illustrative only; you must adapt `command` and `parameters` to your LAMMPS build and potential files):

```python
from ase.build import bulk
from calm.calculators import CalculatorSpec, get_calculator

atoms = bulk("Al", cubic=True)

spec = CalculatorSpec(
    family="lammps",
    model="lammpsrun",
    command="lmp -in in.lammps",
    parameters={
        "pair_style": "eam",
        "pair_coeff": ["* * Al.eam"],
    },
)

atoms.calc = get_calculator(spec)
print("Energy (eV):", atoms.get_potential_energy())
```

## Availability checks

CALM can report which calculator families are available in your current Python environment:

```python
from calm.calculators import list_calculator_availability

for avail in list_calculator_availability():
    status = "OK" if avail.available else "MISSING"
    detail = "" if avail.available else (avail.error_message or "")
    print(f"{avail.family:8s} {status}  {detail}")
```

For code paths that should fail fast with a clear error:

```python
from calm.calculators import CalculatorSpec, require_calculator_spec_available

spec = CalculatorSpec(family="mace", model="medium-mpa-0")
require_calculator_spec_available(spec)
```
