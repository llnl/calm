# Warning policy

Warnings are allowed only when they are understood, stable, and documented. The test suite must not hide broad warning categories globally. Accepted warning filters must be narrow, message-specific, and recorded in this file.

## Currently accepted warning categories

The following warning categories are accepted in the current green baseline:

- top-level compatibility alias `DeprecationWarning` messages emitted while inventory tests resolve advanced/core aliases through `calm.__getattr__`;
- slab geometry warnings that preserve nonzero in-plane components of the third lattice vector rather than silently altering lattice geometry;
- deterministic two-dimensional handedness auto-repair warnings in slab/interface smoke paths;
- compatibility-window deprecation warnings for explicit deprecated keyword aliases that are still covered by tests.

## Accepted test warning filters

The concrete warning filters installed by `tests/conftest.py` are part of the engineering contract. Each filter has a stable identifier so architecture tests can verify that the filter is documented here.

| ID | Primary tiers | Warning source | Reason |
| --- | --- | --- | --- |
| `reference-frame-fallback` | `slab`, `interface` | reference-frame fallback warning from `get_ortho_map` | Selected guardrail tests intentionally exercise fallback behavior. The warning remains user-visible outside tests. |
| `surface-cell-handedness-auto-repair` | `slab`, `interface`, `examples` | `niggli_reduce_2d` left-handed 2D basis auto-repair | The warning documents deterministic repair behavior that is intentionally exercised in smoke paths. |
| `third-lattice-vector-xy-preservation` | `slab` | skew-cell third-lattice-vector preservation warning | Selected slab geometry tests intentionally exercise nonzero in-plane components of the third lattice vector; the warning remains user-visible outside tests. |

These filters are intentionally message-specific. New warnings must not be added by broad rules such as `ignore::Warning` or `ignore::DeprecationWarning`.

## Tier-specific expectations

Warnings are reviewed by test tier:

- Public API and numbered-example tests should be warning-clean unless a warning is itself the compatibility behavior under test.
- Architecture tests should avoid broad warning filters; they should expose new import-time or boundary warnings.
- Slab and interface algorithm tests may accept documented numerical or geometry warnings when the warning preserves correctness or signals an intentional repair path.
- Optional calculator/provider tests should skip unavailable backends rather than emitting repeated dependency warnings.
- Documentation tests should not rely on deprecated public imports except where the documentation page is explicitly about compatibility behavior.

## Warning regressions

Treat a warning as a regression when it is:

- new and not listed above;
- emitted from basic-facing examples or tutorials;
- caused by deprecated APIs that are supposed to be removed from shipped code;
- masking optional dependency failures;
- repeated so frequently that it obscures test failures;
- filtered only through a broad category rule instead of a message-specific rule.

## Marker-aware warning cleanup

Warnings should be cleaned up by tier rather than by broad global filters. Automatic tier markers make it easier to run focused warning checks, for example:

```bash
pytest -q -m public
pytest -q -m examples
pytest -q -m arch
pytest -q -m slab
pytest -q -m interface
```

A warning that appears only in an algorithm tier can be accepted temporarily if it is documented and represents intentional repair or preservation behavior. A warning that appears in basic-facing public or example tiers should generally be treated as user-visible and either removed or explicitly tested as compatibility behavior.

## Cleanup policy

Warning cleanup should be performed in focused patches. Do not silence warnings globally unless the warning source is understood and the behavior is covered by tests.

When adding or changing an accepted warning filter:

1. add or update the structured filter in `tests/conftest.py`;
2. document its ID, tier, source, and reason in this file;
3. keep the message regular expression narrow;
4. run `tests/arch/test_warning_policy_contract.py`;
5. prefer removing the warning source over growing the accepted-filter list.
