# Calculator provider support matrix

This page is the user-facing source of truth for CALM calculator-provider support.

CALM distinguishes between two related but different concepts:

1. a **registered calculator provider**, which can be used through `CalculatorSpec.family`; and
2. an **environment recipe**, which installs a framework stack but does not necessarily mean CALM has a first-class provider for that framework.

If a framework is not listed in the first-class table below, do not present it as a supported `CalculatorSpec.family` in user-facing docs or examples.

## First-class registered providers

The `Family` values below are the strings accepted by `CalculatorSpec.family` in the default CALM provider registry.

<!-- CALM_FIRST_CLASS_CALCULATOR_PROVIDERS_START -->
| Family | Provider | Default / common model | Install support | Notes |
|---|---|---|---|---|
| `ase` | ASE built-in calculators | `EMT` | base dependency or `calm[science]` | Lightweight smoke-test and baseline calculators. |
| `chgnet` | CHGNet via `chgnet.model.dynamics.CHGNetCalculator` | `0.3.0` | `calm[chgnet]` or `environments/calm-chgnet.yml` | First-class PyTorch MLIP provider. |
| `grace` | GRACE / GraceMaker via `tensorpotential.calculator.grace_fm` | `GRACE-1L-OMAT` | `calm[grace]` or `environments/calm-grace.yml` | TensorFlow-backed provider; keep dependency stack isolated from incompatible PyTorch stacks when needed. |
| `lammps` | ASE LAMMPS calculator interface | `lammpsrun` | base dependency plus local LAMMPS runtime | Requires a working LAMMPS executable and potential configuration. |
| `mace` | MACE-MP via `mace.calculators.mace_mp` | `medium-mpa-0` | `calm[mace]` or `environments/calm-mace.yml` | First-class MACE provider; use the curated environment for PyTorch/e3nn compatibility. |
<!-- CALM_FIRST_CLASS_CALCULATOR_PROVIDERS_END -->

## Environment-only, experimental, or deferred frameworks

The frameworks below may have environment files or optional extras for experimentation, but they are not first-class `CalculatorSpec.family` providers unless and until they appear in the first-class table above.

<!-- CALM_DEFERRED_CALCULATOR_FRAMEWORKS_START -->
| Framework / family | Environment or install route | Status | Notes |
|---|---|---|---|
| `orb` | `environments/calm-orb.yml` | deferred / isolated | Deferred after `orb-models` dependency validation showed potential conflicts with TensorFlow/GraceMaker protobuf constraints. |
| `m3gnet` | `calm[m3gnet]` or `environments/calm-m3gnet.yml` | environment-only / experimental | Dependency route exists, but no first-class CALM provider is registered yet. |
| `matgl` | environment recipe / custom install | environment-only / planned | Not registered as a first-class CALM provider. |
| `sevennet` | `environments/calm-sevennet.yml` | environment-only / planned | Requires a dependency stack separate from MACE in many environments. |
| `nequip` | `environments/calm-nequip.yml` | environment-only / planned | NequIP/Allegro support is planned but not registered in the default provider registry. |
| `allegro` | `environments/calm-nequip.yml` | environment-only / planned | Treated with NequIP for environment planning. |
| `mattersim` | `environments/calm-mattersim.yml` | environment-only / planned | Not registered as a first-class CALM provider. |
<!-- CALM_DEFERRED_CALCULATOR_FRAMEWORKS_END -->

## Maintenance contract

When a provider is added, removed, or deferred, the same update should change all of the following:

- the provider registry in `calm.calculators`;
- optional extras in `pyproject.toml`, if applicable;
- relevant environment recipes under `environments/`;
- calculator concept and tutorial documentation;
- this support matrix;
- architecture tests that check docs/provider consistency.

The architecture test `tests/arch/test_packaging_docs_consistency.py` checks that the first-class table above matches the default provider registry and that deferred frameworks are not simultaneously registered providers.
