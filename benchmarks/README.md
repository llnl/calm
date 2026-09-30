# CALM Benchmark Harness

This folder contains three deliberately separate qualification layers for the
current primitive coupled-pair matcher:

1. **Synthetic cross-tool comparison** with basis-only lattice pairs
   (`run_calm`).
2. **Exact scientific-kernel qualification** with versioned enumeration audits
   and frozen mathematical oracles (`run_coupled_qualification`).
3. **Project-centered public API qualification** from material ingest through a
   persisted `Project.search_interfaces` result
   (`run_public_api_qualification`).

Keeping these layers separate prevents a geometric comparison signature, a
low-level kernel result, and a persisted public candidate from being treated as
interchangeable evidence.

## Preserved legacy baseline

The current benchmark suite is frozen as `legacy_v1` under
`benchmarks/legacy/`. The existing runners remain in place and keep their
current command-line interfaces and output schemas while a claim-oriented
qualification suite is developed in parallel. The compact baseline manifest and
golden summaries document exact schemas, defaults, equal-square oracle
evidence, public-API evidence, and known limitations of the historical ZSL
comparison.

Changes to legacy output semantics require an explicit legacy revision and an
updated before/after comparison. New benchmarks must not silently reinterpret
legacy `match_sig` values or raw CALM/ZSL row counts.

## Claim-oriented qualification suite

A separate, versioned claim-oriented suite is being developed under
`benchmarks/benchmarks/claims/`. Its stable claim registry covers `C1` through
`C8`, including strain-domain enforcement, finite completeness, coupled
identity, representation invariance, search-extension stability, public-API
parity, controlled ZSL comparison, and performance scaling.

Run the implemented claim stages with:

```bash
python -m benchmarks.run_claim_suite --outdir bench_out/claims_v1
```

The suite executes every implemented selected claim and records remaining
roadmap claims explicitly as `not_run`. At the current roadmap stage, `C1`
through `C7` are implemented and `C8` remains a placeholder. The command
writes:

```text
bench_out/claims_v1/
├── benchmark_manifest.json
├── claim_summary.json
├── claim_summary.md
├── C1_gate_domain/
│   ├── benchmark_manifest.json
│   ├── claim_result.json
│   ├── gate_domain_summary.json
│   └── gate_*.csv
├── C2_finite_completeness/
│   ├── benchmark_manifest.json
│   ├── claim_result.json
│   ├── reference_differential_summary.json
│   ├── reference_differential_summary.csv
│   ├── reference_comparisons.jsonl
│   └── reference_fixture_results.jsonl
├── C3_C4_identity_policy/
│   ├── benchmark_manifest.json
│   ├── claim_result_C3.json
│   ├── claim_result_C4.json
│   ├── identity_policy_summary.json
│   ├── identity_policy_summary.csv
│   ├── identity_policy_observations.jsonl
│   └── metamorphic_observations.jsonl
├── C5_extension_stability/
│   ├── benchmark_manifest.json
│   ├── claim_result.json
│   ├── search_extension_summary.json
│   ├── search_extension_summary.csv
│   ├── search_extension_snapshots.jsonl
│   ├── search_extension_transitions.jsonl
│   └── search_extension_fixture_results.jsonl
├── C6_public_api_parity/
│   ├── benchmark_manifest.json
│   ├── claim_result.json
│   ├── public_api_parity_summary.json
│   ├── public_api_parity_summary.csv
│   ├── public_api_parity_fixture_results.jsonl
│   ├── public_api_parity_inventories.jsonl
│   ├── public_api_parity_comparisons.jsonl
│   └── public_api_parity.calm/
└── C7_zsl_comparison/
    ├── benchmark_manifest.json
    ├── claim_result.json
    ├── zsl_oracle_summary.json
    ├── zsl_oracle_summary.csv
    ├── zsl_oracle_comparisons.jsonl
    ├── zsl_oracle_key_observations.jsonl
    ├── zsl_oracle_raw_matches.jsonl
    ├── zsl_oracle_reconstructions.jsonl
    ├── zsl_oracle_metric_projections.jsonl
    └── zsl_oracle_coupled_projections.jsonl
```

Run a subset with repeated `--claim` options. For example, this executes `C1`
and retains `C8` as `not_run` because performance scaling remains a later
roadmap stage:

```bash
python -m benchmarks.run_claim_suite \
  --outdir bench_out/claims_v1 \
  --claim C1 \
  --claim C8
```

This claim suite is intentionally not embedded in `benchmarks.run_full_suite`.
The latter remains the frozen `legacy_v1` workflow until a later combined
orchestrator is introduced.

### Common gate-domain qualification

Roadmap PR 5 implements the first pass/fail claim stage independently of lattice
enumeration:

```bash
python -m benchmarks.run_gate_domain_qualification \
  --outdir bench_out/claims_v1/C1_gate_domain \
  --samples 100000 \
  --seed 20260728
```

The stage contains two complementary populations.

1. An analytic boundary suite constructs prescribed principal logarithmic
   strains across square, hexagonal, and oblique reference cells. It verifies
   CALM's production affine-invariant strain calculation and exact inclusion at
   `max_abs_principal_strain == 0.03`, together with robust inside/outside
   cases. This evidence determines the pass/fail result for `C1`.
2. A seeded streaming perturbation population uses the manuscript reference
   cell `(a, b, gamma) = (3.1 A, 2.3 A, 70 deg)` with independent length
   perturbations in `[-3%, 3%]` and angle perturbations in
   `[-1.5 deg, 1.5 deg]`. Every predicate is evaluated on exactly the same
   trial cells.

The common-domain comparison reports:

- CALM's direct `max |principal strain| <= 0.03` predicate;
- manuscript reduced-parameter gates with a 3% length tolerance and absolute
  angle tolerances of 0.5, 1.0, and 1.5 degrees;
- a source-compatible replica of pymatgen's current `reduce_vectors` plus
  `is_same_vectors` vector gate in both unidirectional and bidirectional modes.

The pymatgen-native vector comparison deliberately excludes ZSL's separate
area-ratio transformation-set prefilter because that prefilter belongs to
enumeration, not to the vector acceptance predicate. If pymatgen is installed,
the runner checks a retained probe set against the installed implementation and
records the package version and parity result.

`gate_confusion_matrix.csv` stores unrounded TP, FP, FN, and TN counts plus
acceptance fraction, precision, recall, false-positive rate, and Jaccard index.
`gate_convergence.csv` records the same quantities at deterministic prefix
checkpoints. Candidate and decision sample files remain bounded even for a
publication-scale streaming run.

The same streaming pass also accumulates a fixed-bin distribution in ordered
principal-strain space. The binning contract defaults to 200 bins per axis on
`[-0.05, 0.05]` and is fully recorded in `gate_domain_summary.json` and the
benchmark manifest. Portable plotting inputs are written as:

- `principal_strain_histogram_bin_edges.csv`;
- `principal_strain_histogram_summary.csv`;
- `principal_strain_histogram_target.csv`;
- `principal_strain_histogram_calm.csv`;
- `principal_strain_histogram_reduced_0p5deg.csv`;
- `principal_strain_histogram_reduced_1p0deg.csv`;
- `principal_strain_histogram_reduced_1p5deg.csv`.

Each histogram contains every two-dimensional bin, including zero-count bins.
The runner refuses to complete if an accepted candidate falls outside the
declared histogram range. Histogram totals are cross-checked against the exact
confusion counts, so the persisted heat-map source data cannot silently omit an
accepted population.

A publication-scale reproduction of the manuscript's `10^8` trial population
can be run without retaining all candidates in memory:

```bash
python -m benchmarks.run_gate_domain_qualification \
  --outdir bench_out/claims_v1/C1_gate_domain_publication \
  --samples 100000000 \
  --chunk-size 1000000 \
  --checkpoints 100000,1000000,10000000,100000000 \
  --seed 20260728 \
  --require-clean-repository
```

`--require-clean-repository` is recommended for publication evidence. It
refuses to run unless the checkout has a committed `HEAD` and an empty Git
worktree. The resulting manifest records that exact repository state.

After the qualification completes, validate all manifest checksums and render
the generic four-panel principal-strain evidence with:

```bash
python -m benchmarks.plot_gate_domain_evidence \
  --input-dir bench_out/claims_v1/C1_gate_domain_publication \
  --outdir bench_out/claims_v1/C1_gate_domain_publication/plots
```

The plotting stage does not regenerate trial cells. It reads only checksummed
histogram and confusion artifacts, writes PNG/PDF heat maps, and writes
`gate_domain_acceptance_summary.csv` directly from the exact confusion matrix.
The plot uses `Reduced-parameter accepted` for the controlled manuscript gates;
it does not label those idealized predicates as the full pymatgen ZSL workflow.

This stage evaluates `C1` and supplies controlled gate evidence for later `C7`
work, but it **does not complete claim `C7`**. The identity-aware CALM--ZSL
comparison still requires a common finite enumeration domain and the coupled
projection introduced in PR 4.

### Exact production-versus-reference differential qualification

Roadmap PR 6 implements `C2` using a deliberately slow reference that depends
only on the Python standard library. It does not import CALM production
matching, primitiveization, canonicalization, reduction, or symmetry code.
The reference represents primitive lattice metrics as exact rational numbers,
enumerates every HNF pair in the declared finite domain, enumerates every exact
unimodular metric correspondence, primitiveizes each stacked source pair, and
canonicalizes the result independently.

Run the standard fixture matrix with:

```bash
python -m benchmarks.run_reference_differential \
  --outdir bench_out/claims_v1/C2_finite_completeness \
  --profile standard
```

A faster pull-request profile is available with:

```bash
python -m benchmarks.run_reference_differential \
  --outdir bench_out/claims_v1/C2_finite_completeness_smoke \
  --profile smoke \
  --k-max 3
```

The standard matrix covers equal square, rectangular, hexagonal, generic
oblique, near-square, near-hexagonal, strongly sheared, and anisotropic
lattices. It also includes rigidly rotated B-side bases and determinant-one
primitive-basis reparameterizations. Exact surface automorphism groups are
enumerated independently from each rational metric and supplied explicitly to
the production matcher.

For each fixture, pass/fail requires exact agreement in:

- the complete primitive coupled-pair key set;
- source multiplicity per key;
- source-index pairs;
- repeat indices; and
- first-discovery index within the finite bound.

The stage writes:

```text
C2_finite_completeness/
├── benchmark_manifest.json
├── claim_result.json
├── reference_differential_summary.json
├── reference_differential_summary.csv
├── reference_comparisons.jsonl
└── reference_fixture_results.jsonl
```

`reference_comparisons.jsonl` contains the versioned production/reference key
digests and explicit missing or unexpected keys.
`reference_fixture_results.jsonl` retains both complete inventories, reference
point groups, production enumeration audits, timing diagnostics, and any
provenance mismatches. The JSON summary records the exact pass criterion and
fixture hashes.

This first `C2` stage qualifies small exact zero-strain domains. Nonzero-strain
heterogeneous differential fixtures remain a later extension and are stated as
such in the claim result. The command remains parallel to the frozen
`legacy_v1` full-suite runner.

### Coupled-identity policy and metamorphic qualification

Roadmap PR 7 implements `C3` and `C4` directly against CALM's exact primitive
coupled-pair identity:

```bash
python -m benchmarks.run_identity_policy_qualification \
  --outdir bench_out/claims_v1/C3_C4_identity_policy \
  --profile standard
```

The fixtures declare their expected relationships before production evaluation.
They are not generated from the canonicalizer's output. The `C3` observations
verify that physically distinct relationships remain distinct, including the
primitive identity versus primitive Sigma5, an independent B-side basis change,
ordered A/B exchange, and a left operation omitted from the admitted surface
group. The identity and Sigma5 anchor keys are frozen from the independent
equal-square reference.

The `C4` policy matrix verifies both positive and negative controls:

- one common-right `GL(2,Z)` interface-cell relabeling merges, including
  determinant `+1` and `-1` representatives;
- nonprimitive common-right repetitions primitiveize to the same class;
- independently admitted A- and B-side surface operations merge;
- omitted surface operations remain distinct;
- full symmetry merges a reflected relationship that proper symmetry keeps
  distinct;
- material exchange merges only when explicitly enabled;
- mirrored correspondences are rejected under `proper` orientation and admitted
  under `all`;
- point-group ordering and duplicate operations do not affect the key; and
- canonicalization is idempotent within the admitted correspondence domain.

The stage writes:

```text
C3_C4_identity_policy/
├── benchmark_manifest.json
├── claim_result_C3.json
├── claim_result_C4.json
├── identity_policy_summary.json
├── identity_policy_summary.csv
├── identity_policy_observations.jsonl
└── metamorphic_observations.jsonl
```

Run only one claim or the smaller pull-request profile with repeated `--claim`
options and `--profile smoke`. Primitive-parent basis reparameterization and
rigid Cartesian rotation are already qualified at the finite-search level by
`C2`; this stage focuses on the coupled-pair equivalence relation itself. The
command remains parallel to the frozen `legacy_v1` full-suite runner.

### Cumulative search-extension qualification

Roadmap PR 8 implements `C5` by independently rerunning the production matcher
at every cumulative finite bound rather than deriving prefixes from one final
search:

```bash
python -m benchmarks.run_extension_stability_qualification \
  --outdir bench_out/claims_v1/C5_extension_stability \
  --profile standard \
  --workers 8
```

The standard profile evaluates the equal-square fixture at every `K=1` through
`K=30`. It also evaluates equal rectangular, hexagonal, and generic oblique
lattices through smaller `K=8` domains. The pull-request profile is:

```bash
python -m benchmarks.run_extension_stability_qualification \
  --outdir bench_out/claims_v1/C5_extension_stability_smoke \
  --profile smoke
```

For each adjacent pair of cumulative bounds, the stage requires:

- `keys(K)` to be a subset of `keys(K+1)`;
- complete policy-qualified identity payloads to remain unchanged;
- source counts to be nondecreasing;
- prior source-index pairs and repeat indices to remain present;
- first-discovery indices to remain stable;
- each new class to report the bound at which it actually first appeared; and
- cumulative enumeration-audit counts to be nondecreasing.

The equal-square sequence is additionally checked against the frozen full-D4
inventory at every bound through `K=30`, including first discoveries at
`1, 5, 13, 17, 25, 29`. The stage writes:

```text
C5_extension_stability/
├── benchmark_manifest.json
├── claim_result.json
├── search_extension_summary.json
├── search_extension_summary.csv
├── search_extension_snapshots.jsonl
├── search_extension_transitions.jsonl
└── search_extension_fixture_results.jsonl
```

`search_extension_snapshots.jsonl` preserves the complete primitive-key
inventory, identity digest, source provenance, and cumulative audit totals for
every bound. `search_extension_transitions.jsonl` records every adjacent-bound
check and any precise violation. Independent cumulative searches can be
distributed across worker processes; output ordering and scientific key and
identity digests remain deterministic. This command remains parallel to the frozen
`legacy_v1` suite and does not alter its existing endpoint qualification.

### Direct-kernel and public-API parity qualification

Roadmap PR 9 implements `C6` as an atomistic parity test across four independently
observed layers:

1. direct `calm.interface.pipeline.find_prototypes` execution;
2. the first persisted `Project.search_interfaces` result;
3. the completed-search resume/reuse path; and
4. a newly reopened project reading the persisted run and prototypes.

Run the standard fixture matrix with:

```bash
python -m benchmarks.run_public_api_parity_qualification \
  --outdir bench_out/claims_v1/C6_public_api_parity \
  --profile standard
```

A smaller dependency-enabled pull-request profile is available with:

```bash
python -m benchmarks.run_public_api_parity_qualification \
  --outdir bench_out/claims_v1/C6_public_api_parity_smoke \
  --profile smoke
```

Every comparison requires exact equality of:

- complete versioned primitive coupled-pair identities;
- ranked identity order and retained candidate count;
- primitive A- and B-side supercell recipes;
- bounded source provenance and repeat factors;
- prototype and persisted surface UIDs; and
- authoritative Pareto membership, rank, policy, population scope, and
  population size.

Floating ranking and mismatch diagnostics are compared separately using the
declared absolute and relative tolerances. The persisted run specification must
also preserve the exact `SearchSettings`, scientific search identity, selected
surface UIDs, and `primitive_coupled_pair_v2` implementation identifier. The
completed-search resume path must reuse the same run UID, and the reopened
project must reproduce the same candidate inventory.

The standard matrix covers a high-symmetry LiF(100) homointerface, LiF/Li2O
heterointerfaces, two distinct Li2O(100) terminations, two polar LiF(111)
terminations, a rectangular (110) pair, deterministic output truncation, and a
completed empty search caused by an atom-count limit. The stage writes:

```text
C6_public_api_parity/
├── benchmark_manifest.json
├── claim_result.json
├── public_api_parity_summary.json
├── public_api_parity_summary.csv
├── public_api_parity_fixture_results.jsonl
├── public_api_parity_inventories.jsonl
├── public_api_parity_comparisons.jsonl
└── public_api_parity.calm/
```

`public_api_parity_inventories.jsonl` retains normalized scientific records for
every execution layer. `public_api_parity_comparisons.jsonl` records missing or
unexpected identities, exact build/provenance mismatches, ranked-order changes,
and tolerance-qualified metric differences. This command requires ASE, spglib,
SQLAlchemy, and CALM's normal science dependencies. It remains parallel to the
frozen `legacy_v1` runner.

### Controlled ZSL oracle comparison

Roadmap PR 10 implements `C7` as a descriptive external comparison under
common finite source bounds, explicit strain gates, and CALM's primitive
coupled-pair identity:

```bash
python -m benchmarks.run_zsl_oracle_comparison \
  --outdir bench_out/claims_v1/C7_zsl_comparison \
  --profile standard \
  --directionality both
```

The standard profile includes the equal-square exact inventory at `K=5`, the
frozen six-class equal-square inventory through `K=30`, and small exact
rectangular, hexagonal, and oblique domains. For every case, CALM's production
inventory is first required to agree with the exact or frozen oracle. ZSL
results are then preserved, reconstructed as integer source pairs, and
classified under the same full point groups, proper-correspondence policy,
ordered-material policy, and primitive coupled-pair identity.

Two populations are reported separately:

- an effectively exact principal-strain subset used for overlap with the
  zero-strain finite oracle; and
- a common `max_abs_principal_strain <= 0.03` subset used to describe
  additional nonzero-strain relationships without incorrectly labeling them
  as oracle failures.

Every comparison uses the common source bound
`film_source_index <= K` and `substrate_source_index <= K`. Raw ZSL
descriptions, reconstruction failures, projection failures, multiplicity per
primitive key, exact-oracle recall, and common-gate nonoracle classes are all
retained. The stage writes:

```text
C7_zsl_comparison/
├── benchmark_manifest.json
├── claim_result.json
├── zsl_oracle_summary.json
├── zsl_oracle_summary.csv
├── zsl_oracle_comparisons.jsonl
├── zsl_oracle_key_observations.jsonl
├── zsl_oracle_raw_matches.jsonl
├── zsl_oracle_reconstructions.jsonl
├── zsl_oracle_metric_projections.jsonl
└── zsl_oracle_coupled_projections.jsonl
```

A successful `C7` run reports `descriptive_only`, not `pass`, because pymatgen
ZSL is an external scientific comparator rather than a correctness oracle for
CALM. The command fails only when CALM's internal production/oracle guard
disagrees or the comparison cannot be constructed. The frozen `legacy_v1`
CALM--ZSL CSV and plotting workflow remains unchanged.

### Source-preserving pymatgen ZSL capture

Roadmap PR 3 adds a parallel data-capture command for the controlled ZSL
comparison:

```bash
python -m benchmarks.run_zsl_source_capture \
  --outdir bench_out/claims_v1/C7_zsl_comparison/source_capture \
  --max-areas 50,100,200,400
```

This command preserves every raw pymatgen `ZSLMatch` before any CALM-specific
normalization. It records the film and substrate transformations, primitive
vectors, reduced superlattice vectors, match transformation, match area,
generator settings, raw output order, external object type, and MSON payload
when available. Missing or unreadable external fields are recorded explicitly.

The capture writes:

```text
source_capture/
├── benchmark_manifest.json
├── raw_zsl_matches.jsonl
├── zsl_source_reconstruction.jsonl
└── source_capture_summary.json
```

The reconstruction stage solves for the integer source maps directly from the
two row vectors embedded in Cartesian space. It reports CALM's column-right
convention `S = A @ N`, determinant, source index, orientation sign, absolute
and relative residuals, and consistency with pymatgen's declared
transformations. Failed reconstructions remain in both JSONL files with their
nearest-integer diagnostics; they are never silently discarded.

This source-capture stage **does not evaluate claim `C7`**. It preserves the
external evidence and reconstructs source transformations, but it does not
classify those sources or calculate a controlled CALM-versus-ZSL overlap. The
command is therefore not part of the frozen `legacy_v1` full-suite runner.

Use repeated `--pair` options to capture selected fixtures and
`--bidirectional` to exercise pymatgen's alternate search direction. The raw
output records the complete generator configuration in either case.

### Separate ZSL metric and coupled-identity projections

Roadmap PR 4 consumes a completed source-capture directory without rerunning
pymatgen:

```bash
python -m benchmarks.run_zsl_projection \
  --capture-dir bench_out/claims_v1/C7_zsl_comparison/source_capture \
  --outdir bench_out/claims_v1/C7_zsl_comparison/projection
```

The command emits two deliberately different projections:

1. `zsl_metric_projection.jsonl` independently canonicalizes the film and
   substrate metrics. Its `metric_pair_signature` is suitable for geometric
   overlap and compatibility with the legacy `match_sig` analysis, but it is
   not a coupled A/B identity.
2. `zsl_coupled_projection.jsonl` takes the verified integer source pair,
   applies direct primitiveization, and classifies it under CALM's declared
   primitive coupled-pair equivalence relation. It records the source pair,
   repeat factor, primitive matrix, canonical key, and complete
   canonicalization witnesses.

Mechanical strain diagnostics in the metric projection are evaluated from the
retained ordered ZSL vector pair before any independent one-sided reduction.
This prevents independent basis changes from altering the coupled deformation
being measured.

The projection output is:

```text
projection/
├── benchmark_manifest.json
├── zsl_metric_projection.jsonl
├── zsl_coupled_projection.jsonl
└── projection_summary.json
```

The summary keeps separate counts for raw descriptions, unique one-sided metric
pairs, unique reconstructed source pairs, and unique primitive coupled-pair
keys. These counts have different scientific meanings and must not be plotted
as interchangeable populations.

By default, basis-only fixtures use explicit identity-only surface groups. A
fixture-specific JSON file can supply validated A- and B-side groups:

```json
{
  "schema": "calm.zsl_projection_point_groups/v1",
  "fixtures": {
    "equal_square": {
      "A": [[[1, 0], [0, 1]]],
      "B": [[[1, 0], [0, 1]]]
    }
  }
}
```

Pass that file with `--point-groups`. The selected pair-symmetry,
correspondence-orientation, material-exchange, key-version, surface-group, and
metric-signature settings are recorded in the manifest.

This projection stage still **does not evaluate claim `C7`**. It classifies the
retained ZSL evidence, but it does not yet compare that projected inventory with
CALM on a harmonized finite source domain and common final gate. The ZSL keys
must be described as external results projected onto CALM's equivalence
relation, not as identities produced by pymatgen itself.

## Measure compute performance for roadmap 0337

The compute-performance harness is separate from the scientific benchmark
suite. It measures the production coupled matcher repeatedly while reusing the
existing frozen correctness oracle; it does not contain an alternate matching
implementation.

List the reviewed workloads:

```bash
python -m benchmarks.run_performance_qualification --list
```

Run the complete 0337a matrix from a clean committed checkout:

```bash
python -m benchmarks.run_performance_qualification \
  --out build/performance/0337a-baseline.json \
  --measure-memory \
  --profile \
  --profile-outdir build/performance/profiles \
  --require-clean
```

The matrix records two distinct modes:

- `cold_process`: every recorded trial runs in a fresh Python interpreter;
- `warm_process`: explicit warm-up runs and recorded trials share one process.

For a focused development comparison, select one or more workload identifiers:

```bash
python -m benchmarks.run_performance_qualification \
  --out build/performance/equal-square-k20.json \
  --benchmark coupled_equal_square_k20 \
  --repeats 5 \
  --profile \
  --profile-outdir build/performance/profiles
```

Timing trials and optional Python-allocation trials are executed separately so
`tracemalloc` does not contaminate the wall-time distribution. Raw measurements
and summary statistics are retained separately. Timing trials also record the
process-lifetime resident-set high-water mark through `ru_maxrss` when the
platform provides it. The resident-set metric is trial-isolated only for
`cold_process` workers; warm-process values share one process and are retained
as diagnostic evidence rather than a comparable per-trial peak.

`peak_python_bytes` is a Python-allocation metric, not a total-memory metric.
It can expose retained tuple, dictionary, and cache state, but it does not
comprehensively measure native allocations owned by NumPy or other compiled
dependencies. Memory acceptance should therefore use same-host cold-process
`peak_process_bytes`, with `peak_python_bytes` retained to explain allocation
composition.

Every trial must reproduce the configured exact fields, including
`pair_key_sha256`,
`pair_identity_sha256`, class and source counts, and correspondence-funnel
counts. Cold, warm, and profiled executions must agree exactly before a report
is written.

Performance conclusions must use same-host ratios between reports produced
with controlled dependency versions and thread settings. The contract does not
define universal absolute-time pass thresholds. A report from a dirty tree is
valid exploratory evidence only; `--require-clean` is required for a committed
baseline or release qualification claim.

Shared execution mechanics for the coupled, direct-correspondence, and registry
qualification runners live in
`benchmarks/benchmarks/_performance_support.py`. That private owner provides
source and environment evidence, subprocess workers, resident-memory
normalization, measurement summaries, exact repeated-trial comparison, profile
extraction, workload selection, and stable JSON report writing. Scientific
workload definitions and correctness oracles remain in their family-specific
runners, and all three report schemas remain unchanged.

The machine-readable workload and correctness contract is
`engineering/qualification/performance-matrix.json`. Its static consistency is
checked with:

```bash
python engineering/qualification/check_performance_contract.py
```

## Run the complete benchmark and qualification suite

Run all commands from the repository root. Install CALM with the scientific,
table, plotting, and development dependencies, then install pymatgen for the
external ZSL comparison:

```bash
python -m pip install -e ".[science,dataframe,plot,dev]"
python -m pip install pymatgen
```

The complete suite has one authoritative entry point:

```bash
python -m benchmarks.run_full_suite --outdir bench_out
```

It runs, in order:

1. the benchmark unit and repository contract tests;
2. the CALM-versus-pymatgen ZSL comparison, plots, and diagnostics;
3. the four-case coupled-kernel smoke qualification at `K=5`;
4. the frozen equal-square oracle qualification at `K=5` and `K=30`; and
5. the fresh-project public API qualification through
   `Project.search_interfaces`.

The contract-test stage is equivalent to:

```bash
python -m pytest -q \
  tests/unit/benchmarks \
  tests/repository/test_public_api_qualification_contract.py \
  tests/repository/test_benchmark_documentation_contract.py \
  tests/repository/test_performance_qualification_contract.py \
  tests/repository/test_legacy_benchmark_contract.py
```

`benchmarks.run_all` is only the cross-tool CALM-versus-ZSL stage. It does not
run the exact coupled-kernel oracle or the project-centered public API
qualification and must not be described as the complete qualification suite.
Run that stage alone only when needed:

```bash
python -m benchmarks.run_all \
  --outdir bench_out/cross_tool \
  --max-areas 50,100,200,400 \
  --pareto-area 400
```

The default run writes:

```text
bench_out/
├── cross_tool/
│   ├── results_calm.csv
│   ├── results_pymatgen.csv
│   ├── figs/
│   └── diag_oblique_tradeoff_area_400_*.csv
├── coupled-smoke.csv
├── coupled-square-scaling.csv
├── public_api_qualification.calm/
└── public_api_qualification.json
```

The command stops at the first failing stage and returns that stage's exit
code. It uses `--reset` only for the benchmark-owned public API project under
the selected output directory.

Inspect the exact commands without running them:

```bash
python -m benchmarks.run_full_suite --outdir bench_out --dry-run
```

Individual stages can be omitted for targeted reruns with `--skip-tests`,
`--skip-cross-tool`, `--skip-smoke`, `--skip-square-oracle`, or
`--skip-public-api`. A complete qualification run should not use those flags.

The `K=5` and `K=30` rows in `coupled-square-scaling.csv` must report
`oracle_status=pass`. The public API JSON must report
`implementation=primitive_coupled_pair_v2` and a positive candidate count.

The historical SlabGen distribution is available only through the explicitly
named `run_slabgen` external-comparison runner. It is not a CALM implementation
or compatibility path.

## 1. Generate detailed synthetic comparison CSVs

From the repository root:

```bash
# Pymatgen ZSL
python -m benchmarks.run_pymatgen_zsl \
  --out results_pymatgen.csv \
  --max-areas 50,100,200,400 \
  --max-length-tol 0.03 \
  --max-angle-tol 0.01

# Production coupled CALM kernel on the same basis-only cases
python -m benchmarks.run_calm \
  --out results_calm.csv \
  --max-areas 50,100,200,400 \
  --eps-principal-max 0.03
```

`run_calm` calls the complete production
`search_primitive_match_classes()` kernel and emits one row per exact primitive
pair class retained by the requested area envelope. These inputs contain only
2D lattice bases, not atomistic surfaces, so the default surface equivalence is
explicitly `identity_only`. This runner is therefore appropriate for controlled
cross-tool comparisons, not for validating atomistic surface-symmetry
discovery.

Each CALM row records:

- `pair_key_version` and the complete policy-qualified `pair_identity`;
- the bare eight-integer `pair_key` for exact-key analyses;
- surface-symmetry mode, status, and operation counts;
- all source index pairs and repeat indices aggregated into the primitive
  class; and
- `match_sig`, a lower-fidelity geometric projection retained only for
  cross-tool set comparisons.

`match_sig` is not CALM's deduplication identity. `--tau-max` is an optional
post-search `|log(A_A/A_B)|` reporting filter; it is not an alternate matcher,
identity rule, or deduplication mode.

The default condition-number limit is imported from current CALM
(`1e6`) rather than duplicated in the benchmark harness. Pair-symmetry,
correspondence-orientation, material-exchange, and correspondence-domain
controls are exposed explicitly on the command line.

## 2. Plot match counts and Pareto overlays

```bash
python -m benchmarks.plot_benchmarks \
  --pymatgen results_pymatgen.csv \
  --calm results_calm.csv \
  --pareto-area 400 \
  --outdir figs
```

The optional unique-count plots use `match_sig` only because external tools do
not provide CALM's exact coupled-pair identity. Do not interpret those counts as
an independent validation of CALM deduplication.

## 3. Diagnose discrepancies for one pair

```bash
python -m benchmarks.diagnose_pair \
  --pymatgen results_pymatgen.csv \
  --calm results_calm.csv \
  --pair oblique_tradeoff \
  --max-area 400 \
  --outdir diagnose_out
```

## 4. Paper figure helpers

### Hencky strain histogram

```bash
python -m benchmarks.figure_hencky_hist \
  --pair oblique_tradeoff \
  --max-area 400 \
  --max-length-tol 0.03 \
  --max-angle-tol 0.01 \
  --epsilon-max 0.03 \
  --tau-max 0.06 \
  --percent --density --dump-csv \
  --outdir figs
```

### Gate diagnostics

```bash
python -m benchmarks.plot_gate_diagnostics \
  --pymatgen results_pymatgen.csv \
  --calm results_calm.csv \
  --pair oblique_tradeoff \
  --max-area 400 \
  --max-angle-tol 0.01 \
  --eps-principal-max 0.03 \
  --percent \
  --outdir figs
```

### Three-panel Hencky figure

```bash
python -m benchmarks.figure_hencky_triptych \
  --pair oblique_tradeoff \
  --max-area 400 \
  --max-length-tol 0.03 \
  --max-angle-tol 0.01 \
  --epsilon-max 0.03 \
  --tau-max 0.06 \
  --percent --density \
  --outdir figs
```

These figure helpers consume the modern coupled-kernel runner, but their
cross-tool geometric projections are not substitutes for the exact oracle
qualification below.

## 5. Exact coupled-v2 scientific qualification

Run the four-case smoke matrix:

```bash
python -m benchmarks.run_coupled_qualification \
  --out coupled-smoke.csv \
  --k-max 5
```

The default policy is case-aware:

- `equal_square` supplies the full eight-operation D4 point group explicitly,
  uses an effectively exact principal-strain tolerance (`1e-10`), and checks a
  frozen oracle;
- rectangular, near-hexagonal, and oblique basis-only cases use
  `identity_only` surface symmetry unless explicitly overridden.

For `equal_square`, the command fails rather than writing apparently successful
evidence if the production algorithm disagrees with the frozen manuscript/SI
oracle. The checks include:

- the exact index-five funnel: six HNFs per side, three comparison orbits per
  side, nine orbit pairs, three admitted orbit pairs, twelve expanded member
  pairs, thirty-two strain-admissible proper correspondences, and one newly
  created primitive class at index five;
- identity and Sigma-5 as the complete cumulative class inventory through
  `K=5`; and
- the complete six-class inventory and first-discovery indices
  `1, 5, 13, 17, 25, 29` through `K=30`.

Run the exact square scaling qualification with:

```bash
python -m benchmarks.run_coupled_qualification \
  --out coupled-square-scaling.csv \
  --case equal_square \
  --k-max 5 \
  --k-max 30 \
  --k-max 50 \
  --measure-memory
```

Rows through `K=30` report `oracle_status=pass` when all exact checks agree.
The frozen inventory is intentionally not extrapolated beyond `K=30`; larger
runs remain deterministic scaling evidence and are marked not applicable to the
frozen oracle.

The qualification CSV contains both a bare pair-key digest and a digest of the
complete versioned pair identities. `correspondence_entry_limit` is unbounded by
default, so qualification runs do not silently truncate the proven finite
correspondence domain.

## 6. Project-centered public API qualification

This end-to-end command uses only supported top-level imports from `calm`,
creates a fresh current-schema project, generates atomistic LiF(100) and
Li2O(100) surfaces, and calls `Project.search_interfaces`:

```bash
python -m benchmarks.run_public_api_qualification \
  --project benchmark_public_api.calm \
  --out public_api_qualification.json \
  --reset
```

It verifies that:

- retired top-level `calm.Surface` and `calm.search_interfaces` entry points are
  absent;
- the identity-bearing persisted run specification reports
  `primitive_coupled_pair_v2`, preserves the exact search identity and settings,
  and references the selected persisted surfaces;
- lifecycle progress reports a completed run and a candidate count that agrees
  with the authoritative persisted candidate population;
- every persisted candidate payload independently reports
  `identity_algorithm="primitive_coupled_pair_v2"`;
- every public candidate carries a complete, positive-version,
  policy-qualified `pair_identity`;
- exact identities are unique in the public candidate population; and
- all candidates agree on authoritative Pareto-population provenance.

The public project run intentionally keeps scientific identity in `run.spec`
and lifecycle state in `run.progress`. Resolved surface-symmetry operations and
the complete primitive-key inventory are qualified by
`run_coupled_qualification`; they are not duplicated into public-run progress.

This command requires CALM's science dependencies (`ase`, `spglib`, and
associated numerical dependencies) plus SQLAlchemy. It always creates a fresh
project because current CALM intentionally does not migrate historical project
databases.

## 7. Explicit external SlabGen comparison

Historical comparisons with the external SlabGen package use the explicitly
named runner:

```bash
python -m benchmarks.benchmarks.run_slabgen \
  --out results_slabgen.csv \
  --max-areas 50,100,200,400
```

Those rows are external-tool results and must not be labeled as CALM.

## 8. Direct correspondence-enumeration qualification

Roadmap update 0337d measures the production basis-correspondence enumerator
without running the complete coupled matcher. The direct matrix freezes one
small skew sentinel and two large correspondence domains with exact transform,
deterministic generalized-eigenvalue reference, and rejection-funnel signatures.

List the reviewed workloads:

```bash
python -m benchmarks.run_correspondence_performance_qualification --list
```

Run the complete direct matrix from a clean committed checkout:

```bash
python -m benchmarks.run_correspondence_performance_qualification \
  --out build/performance/0337d-correspondence.json \
  --measure-memory \
  --profile \
  --profile-outdir build/performance/profiles-0337d \
  --require-clean
```

The direct runner distinguishes two cache states:

- `cold_cache` clears the production correspondence LRU before each trial;
- `warm_cache` reuses the production LRU after explicit warm-up runs.

These modes are not process-isolation claims. They measure the direct kernel in
one interpreter, while the coupled qualification runner retains the separate
`cold_process` and `warm_process` policy. Timing and optional `tracemalloc`
measurements are separated so Python-allocation tracing does not contaminate
the wall-time distribution.

Each report freezes `transform_key_sha256`, `reference_record_sha256`,
candidate-column counts, Cartesian-product size, determinant admissions, and
strain admissions. The reference record digest is derived from deterministic
high-precision generalized metric eigenvalues rather than platform-specific
transcendental bit patterns. Every observed principal strain must agree with
that reference within the reviewed `strain_reference_atol=1e-10`.

`observed_record_sha256`, `max_abs_strain_reference_error`, and the
implementation-selected `determinant_chunks` are diagnostic fields. The
observed bitwise digest may differ across supported NumPy/libm platforms and is
not a cross-platform correctness oracle. Performance conclusions use same-host
ratios and exact portable signature agreement; the matrix does not define
universal absolute-time thresholds.

The machine-readable workload contract is
`engineering/qualification/correspondence-performance-matrix.json`. It is
validated together with the coupled matrix by:

```bash
python engineering/qualification/check_performance_contract.py
```

## 9. Registry evaluator qualification

Roadmap update 0337e measures the translation-only registry objective with a
cheap deterministic calculator. The runner compares the historical
`rebuild_each_evaluation` composition with the production `prepared_once`
composition in separate fresh processes.

List the reviewed workloads:

```bash
python -m benchmarks.run_registry_performance_qualification --list
```

Run the complete matrix from a clean committed checkout:

```bash
python -m benchmarks.run_registry_performance_qualification \
  --out build/performance/0337e-registry.json \
  --measure-memory \
  --profile \
  --profile-outdir build/performance/profiles-0337e \
  --require-clean
```

The three workloads cover a short 64-atom sentinel, a primary 600-atom
400-step trajectory, and a 2,400-atom copy-scaling case. Every rebuild and
prepared trial on the same host must reproduce the exact proposal trace,
accepted-state trajectory, score trace, best state, and objective-evaluation
counts. The cross-platform matrix freezes the accepted trajectory and
scientific result fields. Exact rejected-proposal float bits are retained as
`observed_proposal_trace_sha256`, a same-host diagnostic, because supported
NumPy/libm combinations can differ in rejected Gaussian proposal bits without
changing an accepted state. The report also records the number of fixed-geometry
preparations and calculator constructions.

`rebuild_each_evaluation` reconstructs the supercell, gauge, strain, stacking,
and fixed cell for every objective call. `prepared_once` performs those steps
once and creates each trial from a private immutable template. Both modes build
fresh trial atoms and reuse one calculator instance, so the benchmark does not
assume backend-specific in-place mutation semantics.

The dependency-light calculator isolates CALM orchestration costs. It is not a
substitute for representative real-backend validation, which remains a
supported-environment qualification requirement. Timing conclusions use
same-host ratios; the contract defines no universal absolute-time threshold.

The machine-readable workload contract is
`engineering/qualification/registry-performance-matrix.json` and is validated
by `python engineering/qualification/check_performance_contract.py`.

## 10. Generated artifacts

Benchmark CSVs, JSON summaries, diagnostics, figures, and temporary project
directories are generated outputs and are not versioned. Regenerate them from
the current runners whenever benchmark evidence is needed for analysis,
documentation, or a manuscript. Historical evidence tied to the removed
independent-surface matcher is intentionally not retained.

### Claim benchmark mechanical ownership

Shared claim-evidence mechanics live in
`benchmarks/benchmarks/claims/_support.py`. This private module owns atomic
JSONL/CSV writing, stable integer-key text, exact matrix payload conversion,
and the minimal basis-only slab fixture. Claim modules continue to own their
scientific policies, fixtures, schemas, digests, projections, comparisons, and
golden outputs. The support module must not import CALM scientific packages or
pymatgen.
