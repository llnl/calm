# Calculator availability checks

CALM’s high-level workflows construct calculators from a serializable [`CalculatorSpec`](../../reference/public_api.md). Whether a given calculator backend is usable depends on two things:

1. The backend family is registered in CALM (i.e. a provider exists).
2. The optional dependencies for that backend are installed in your current environment.

This page shows how to **inspect availability** and **fail fast** with actionable error messages.

## List availability

```python
from calm.calculators import list_calculator_availability

for avail in list_calculator_availability():
    status = "OK" if avail.available else "MISSING"
    detail = "" if avail.available else (avail.error_message or "")
    print(f"{avail.family:8s} {status}  {detail}")
```

You can also print a human-readable summary:

```python
from calm.calculators import print_calculator_availability

print_calculator_availability()
```

## Fail fast in scripts and workflows

If your workflow requires a specific calculator family, validate early:

```python
from calm.calculators import CalculatorSpec
from calm.calculators import require_calculator_spec_available

spec = CalculatorSpec(family="chgnet", model="0.3.0")
require_calculator_spec_available(spec)
```

If the calculator is unavailable, CALM raises a `RuntimeError` with installation guidance.

## Notes

- For MLIP frameworks with strict dependency constraints, prefer the curated conda environments under `environments/`.
  See [Conda environments](../../getting-started/conda_environments.md).
- The `ase` family is intended for lightweight reference calculators (e.g. EMT) and is useful as a baseline smoke test.
