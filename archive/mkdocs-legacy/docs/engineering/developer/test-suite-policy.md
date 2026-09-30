# Test-suite policy

This document defines the coarse test tiers used during CALM architecture cleanup. It complements the public API inventory and warning policy. The goal is not to force every test into a directory immediately, but to make the purpose of each test tier explicit before further refactors.

## Test tiers

| Tier | Primary location | Purpose |
| --- | --- | --- |
| `public` | `tests/public/` | Basic-facing and documented public API contracts. |
| `examples` | `tests/examples/` | Runnable numbered examples, output artifacts, and example hygiene. |
| `docs` | `tests/test_docs_*.py` | MkDocs snippets, public documentation imports, anchors, and docs/example consistency. |
| `arch` | `tests/arch/` | Import boundaries, optional backend import hygiene, removed-shim guardrails, repository-artifact hygiene, and ownership invariants. |
| `slab` | `tests/slab/` and slab-focused root tests | Modern oriented-slab and primitive surface-cell algorithm invariants. |
| `interface` | interface-focused root tests and future `tests/interface/` | Interface enumeration, strain partitioning, build kernels, registry search, and interfacial-energy kernels. |
| `project` | project/workspace root tests and future `tests/project/` | Durable workspace, unit-of-work, schema, queue, provenance, and public project persistence. |
| `calculators` | calculator-focused root tests and future `tests/calculators/` | Calculator specs, registry behavior, provider construction, and optional backend availability checks. |
| `optional` | any tier | Tests that construct, emulate, or require optional science, MLIP, or platform-specific backends and must skip cleanly when unavailable. |
| `slow` | any tier | Tests that are useful but should not be part of a minimal smoke loop. |

## Marker policy

Pytest marker declarations live in both `pytest.ini` and `pyproject.toml` because some local environments read one file preferentially. The marker sets must stay synchronized. Architecture tests enforce this.

The coarse marker set is:

```text
arch
calculators
docs
examples
interface
legacy
optional
project
public
slab
slow
smoke
v2
```

A test does not need a marker just because it is located in a tier directory. Markers are for cross-cutting selection, slow/optional gating, and explicit contract clarity.


## Automatic tier marking

Pytest applies coarse markers automatically for the strongest directory-based tiers. The automatic rules live in `tests/conftest.py` and are intentionally conservative. They mark tests under:

```text
tests/arch/      -> arch
tests/public/    -> public
tests/examples/  -> examples
tests/slab/      -> slab
tests/legacy/    -> legacy
```

Root-level tests are being migrated gradually. Architecture-policy tests belong under `tests/arch/`; broad root-level architecture-policy filename families such as `test_architecture_*`, `test_import_*`, and `test_no_*` were retired in `0098`. Until other domain tests are moved, established filename families receive automatic markers such as:

```text
test_docs_*            -> docs
test_calculator*       -> calculators
test_backfill_*        -> project
test_job_queue*        -> project
test_project_*         -> project
test_schema_*          -> project
test_tilt_metadata_*   -> project
test_transaction_*     -> project
test_workspace_*       -> project
test_slab_*            -> slab
test_oriented_slab_*   -> slab
test_interface_*       -> interface
test_registry_search_* -> interface
```

Automatic markers are not a replacement for explicit test names or directory organization. They provide reliable selection while the suite is incrementally reorganized. New broad root-level filename rules should be added only when the ownership is obvious and the rule is covered by an architecture guardrail test.

## Recommended command groups

Fast public/docs smoke loop:

```bash
pytest -q tests/public tests/examples tests/test_docs_public_api_imports.py tests/test_docs_python_code_blocks_compile.py tests/test_docs_and_examples_no_project.py
```

Architecture guardrails:

```bash
pytest -q tests/arch
```

Full local validation:

```bash
mkdocs build --strict
pytest -q
```

Optional MLIP/provider validation should be run in backend-specific environments and should not be required by the default suite.

## Warning expectations

Warnings should be reviewed by tier:

- Public and example tests should generally be warning-clean unless the warning is an explicitly tested compatibility behavior.
- Architecture tests should not suppress warnings globally.
- Algorithm tests may accept documented numerical or geometry warnings when the warning is the intended safety behavior.
- Optional provider tests should skip unavailable backends rather than warning repeatedly.
Project-persistence tests that require SQLAlchemy must skip cleanly when SQLAlchemy is unavailable in a lightweight validation environment.

Accepted warning filters are now data-driven in `tests/conftest.py` and documented by stable IDs in `warning-policy.md`. Architecture tests verify that warning filters are narrow, documented, and not broad category-level ignores.

Useful focused checks:

```bash
pytest -q tests/arch/test_warning_policy_contract.py
pytest -q -m public
pytest -q -m arch
```

## Cleanup policy

During architecture cleanup:

1. prefer adding a tier/marker policy before moving tests;
2. avoid broad test relocation in the same patch as behavior changes;
3. keep contract tests near the public surface they protect;
4. keep algorithm tests close to their technical domain;
5. record any intentionally accepted warning category in the warning policy.
