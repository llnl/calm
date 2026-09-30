# Legacy benchmark baseline

This directory freezes the CALM benchmark and qualification suite that existed
when the claim-oriented benchmark roadmap was introduced. The frozen baseline
is named `legacy_v1`.

"Legacy" refers to the benchmark harness, output schemas, and comparison
semantics preserved here. It does **not** mean that the runners call a retired
CALM matcher. The frozen CALM runners use the production
`primitive_coupled_pair_v2` implementation.

## Preservation policy

The existing modules remain in their current locations and keep their current
command-line interfaces:

```text
benchmarks.run_calm
benchmarks.run_pymatgen_zsl
benchmarks.run_all
benchmarks.plot_benchmarks
benchmarks.diagnose_pair
benchmarks.run_coupled_qualification
benchmarks.run_public_api_qualification
benchmarks.run_full_suite
```

New claim-oriented benchmarks must be added in parallel. They must not:

- overwrite legacy output files;
- rename or reinterpret legacy columns;
- modify the legacy synthetic lattice fixtures;
- replace `match_sig` with a different identity while retaining the same name;
- remove or redirect an existing command-line entry point; or
- make a legacy runner depend on the new claim-oriented framework.

A behavior-changing correction to the legacy suite requires a new legacy
revision, updated compact golden evidence, and a documented before/after
comparison.

## Frozen evidence

`baseline_manifest.json` records the command entry points, default execution
profiles, output schemas, and known interpretation limits.

The `golden/` directory contains compact deterministic evidence rather than
large benchmark products:

- `coupled_smoke_headers.json` freezes the coupled-qualification CSV schema;
- `equal_square_k5_summary.json` freezes the exact full-D4 inventory and
  index-five funnel through `K=5`;
- `equal_square_k30_summary.json` freezes the cumulative full-D4 inventory
  through `K=30`; and
- `public_api_summary.json` freezes the stable public-workflow result from the
  LiF(100)-Li2O(100) qualification fixture.

The repository contract test validates these files against the current legacy
modules and exact fixtures.

## Interpretation limits

The legacy cross-tool outputs remain useful historical diagnostics, but they do
not place CALM and pymatgen ZSL on a common coupled-pair identity:

1. CALM rows are primitive coupled-pair classes; pymatgen rows are raw ZSL
   match descriptions.
2. `match_sig` independently projects the two one-sided lattice metrics and is
   not CALM's coupled identity.
3. The legacy ZSL runner independently canonicalizes the film and substrate
   superlattices before computing comparison metrics.
4. Raw match counts and legacy Pareto overlays therefore compare differently
   defined populations.
5. The legacy suite does not preserve the full raw ZSL transformation pair or
   project ZSL results onto CALM's primitive coupled-pair equivalence relation.

These limitations are intentionally preserved for reproducibility. The new
claim-oriented suite will address them without silently changing legacy output
semantics.
