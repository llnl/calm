# CALM examples

This README is the execution guide for the three canonical tutorials, the
ten numbered scripts, and the standalone analysis examples. The numbered scripts form one sequential workflow and share one
persistent project. The [tutorial sequence](../docs/learn/first-interface.md)
teaches the workflow progressively, while the
[workflow API index](../docs/reference/public-api.md) defines the public
operations.


## Canonical greenfield tutorials

The three tutorial programs are independent: each creates its own project, uses
package-owned structures through `calm.tutorial_structure`, accepts an explicit
output directory, and writes `outputs/run-summary.json` for verification.

```bash
python examples/tutorials/first_interface.py \
  --work-dir examples/work/first-interface --reset

python examples/tutorials/compare_candidates.py \
  --work-dir examples/work/compare-candidates --reset

python examples/tutorials/refine_relax_evaluate.py \
  --work-dir examples/work/refine-relax-evaluate --reset
```

The first two programs use packaged LiF and Li2O structures and require no
calculator. The third uses packaged Cu and Ni structures with the registered ASE
provider and EMT. EMT demonstrates workflow mechanics and reference bookkeeping;
it is not evidence that EMT is scientifically suitable for another interface.

Expected-output contracts are stored under `examples/tutorials/expected/`. Set
`CALM_RUN_CALCULATOR_TUTORIAL=1` only when opting the calculator-backed program
into the automated test suite. The programs are the canonical executable sources for the published
[Learn tutorials](../docs/learn/first-interface.md); handwritten parallel
notebook implementations are not maintained.

## Standalone deformation-accounting example

Run the NumPy-only mathematical walkthrough from the repository root:

```bash
python examples/deformation_accounting.py
```

It distinguishes a rigid matching gauge from physical construction shear,
incremental coherent matching, and later cell relaxation. It prints the
composed deformation gradients, principal Hencky strains, and the equivalent
ASE row-cell update. The derivation is in [Frames, gauges, and deformation
accounting](../docs/understand/coherent-matching.md).

## Low-index redundancy audit

After completing the low-index LiF/Li2O search workflow, audit its persisted
enumeration records without rerunning matching:

```bash
python examples/lif_li2o_low_index_redundancy_audit.py
```

The script writes separate tables for the finite HNF-pair filters, enumeration
work counters, and exact coupled-identity quotient. Keeping those populations
separate prevents unlike units from being presented as one reduction funnel.
Searches carrying the legacy v1 audit must be rerun with `resume=False` before
the exact identity counts can be reported.

## Sequential workflow

Run the scripts in order from the repository root:

```bash
python examples/01_optimize_materials.py
python examples/02_generate_surfaces.py
python examples/03_search_interfaces.py
python examples/04_compare_interface_searches.py
python examples/05_build_interfaces.py
python examples/06_refine_interfaces.py
python examples/07_relax_interfaces.py
python examples/08_evaluate_interface_energetics.py
python examples/09_build_interface_dataset.py
python examples/10_run_interface_campaign.py
```

The first successful calculator-backed optimization locks the shared project to
one MLIP family and one exact calculator identity.
`open_project(..., summarize=True)` reports that project-level configuration
once; reader-facing material, surface, and interface tables omit the redundant
calculator column. Examples 01 and 02 consume collection-owned `characterization` views, while
Examples 03 and 05 consume the shared candidate `summary` view. Their terminal
and CSV schemas are centrally defined rather than repeated in the scripts.
Example 05 displays only the top Pareto candidates that its construction
workflow will consume. Candidate strain diagnostics, provenance, and complete
normalized rows remain available through `view="strain"`,
`view="provenance"`, and `view="all"`. Exact calculator provenance remains
persisted and available in full rows and the reproducibility manifest.
Examples 05-07 additionally export the centrally owned interface `strain`
view, which separates source-slab construction strain, incremental matching
strain, current total strain, and relaxation-cell strain. Examples 06-08 use
centrally owned result `summary` views for refinement, relaxation,
reference-energy, raw-energy, and thermodynamic CSVs. Their run, backend,
formula, and artifact lineage remains available through `view="provenance"`,
while `view="all"` retains the complete public result projection. Example 09
writes the project-bound dataset's `learning` view by
default, while dataset-item `summary` and `provenance` views remain available
for membership inspection. Example 10 writes a concise campaign-case `summary`
and a separate dynamic `comparison` table for grid dimensions and scalar stage
metrics.

The independent advanced tutorial under `examples/tutorials/` is the
canonical source for the [refine, relax, and evaluate](../docs/learn/refine-relax-evaluate.md)
chapter. Examples 06-08 remain the more detailed sequential demonstrations used
to exercise additional workflow options.

## Sequential workflow inventory

- `01_optimize_materials.py` — create the shared project, optimize and characterize materials, and export optimized structures.
- `02_generate_surfaces.py` — generate and characterize persisted surface terminations, select explicit terminations, and export slab structures.
- `03_search_interfaces.py` — search one explicitly selected pair of persisted surface terminations and write candidate tables and a Pareto plot.
- `04_compare_interface_searches.py` — run a second search, write discrete per-search Pareto plots, and compare search-local staircase envelopes with the aggregate staircase envelope.
- `05_build_interfaces.py` — display the top-scoring Pareto construction selection, build those interfaces, and write structures plus construction and strain tables.
- `06_refine_interfaces.py` — refine built interfaces using an explicit strain objective and operational registry settings, then write one `06_`-prefixed output bundle with construction and strain tables for both persisted refinement stages.
- `07_relax_interfaces.py` — relax authoritative registry-refined interfaces through the typed persisted workflow and write result, interface-summary, and strain tables.
- `08_evaluate_interface_energetics.py` — inspect the frozen reference capability, calculate supported per-interface references, persist raw total energies, and derive a convention-bearing thermodynamic quantity; work of adhesion can use calculated independently relaxed fixed-cell surfaces or explicit manual references.
- `09_build_interface_dataset.py` — join relaxed structures, relaxation results, raw energies, and thermodynamic targets; declare features and targets; assign prototype-preserving train/validation/test splits; validate ML readiness; and atomically export the bundle.
- `10_run_interface_campaign.py` — generate a typed case grid, reuse one compatible persisted search across downstream variants, execute exact case-specific stage lineage synchronously with deterministic resume, export datasets, write a ranked comparison table, and write and immediately verify the final project reproducibility manifest.

## Working layout

The canonical tutorial commands write beneath `examples/work/`. The scripts
also default to that repository-owned location when `--work-dir` is omitted.
They do not read repository-relative input structures, and the generated work
directories are ignored by Git. The numbered Examples 01-10 continue to share the
sibling `example_project.calm/` and `outputs/` paths for the advanced sequential
demonstration.

```text
examples/
├── tutorials/
│   ├── first_interface.py
│   ├── compare_candidates.py
│   ├── refine_relax_evaluate.py
│   └── expected/
├── work/                       # generated canonical tutorial projects
├── 01_optimize_materials.py
├── ...
├── 10_run_interface_campaign.py
├── deformation_accounting.py
├── lif_li2o_low_index_redundancy_audit.py
├── Structures/
├── example_project.calm/        # generated by Example 01
└── outputs/                     # generated by Examples 01-10
```

Generated tutorial directories are disposable. Use `--reset` to replace only
the selected tutorial directory. To restart the sequential workflow, remove
`examples/example_project.calm/` and `examples/outputs/`, then rerun from
Example 01.

The first-interface tutorial and Examples 05-06 write interface tables with
the centrally owned interface `construction` view. The export reports durable interface
identity, source search and candidate, strain partition, fractional registry
placement, gap and vacuum in angstroms, atom count, and area without dumping
complete persistence provenance. Examples 05-07 also write the interface
`strain` view so construction, matching, total, and relaxation-cell deformation
remain distinguishable at each lifecycle stage. Example 06 prefixes every
table, trace, and plot in its refinement bundle with `06_`, so its generated
artifacts remain identifiable inside the shared output directory.

## Low-index method comparison

The manuscript-oriented comparison reruns the nine persisted LiF/Li2O
low-index searches while privately recording every correspondence admitted
before CALM aggregates equivalent descriptions:

```bash
python examples/lif_li2o_low_index_dedup_comparison.py
```

Pass `--project-dir` when the completed low-index project is elsewhere. The
script applies each comparator to the same recorded population and writes
method-typed tables beneath its output directory. Before reporting a search,
it requires the exact persisted candidate pair-key set to equal the fresh
rerun's final pair-key set; both set digests are retained in `run-metadata.json`.
CALM rows are exact equivalence quotients; InterOptimus- and Ogre-style rows
are heuristic clusters; the Jelver-style row is a generation filter; and
InterMat and InterMatch rows are selectors. These counts have different
meanings and must not all be described as numbers of unique matches. The
current-source InterMat selector is not applicable because the CALM ledger
does not contain native JARVIS traversal ranks; a separate paper-text proxy is
reported explicitly. InterMatch selection is not applicable unless an
`entry_id,elastic_energy` CSV is supplied.

When that CSV is supplied, its semantics must be explicit:

```bash
python examples/lif_li2o_low_index_dedup_comparison.py \
  --intermatch-elastic-energies path/to/energies.csv \
  --intermatch-energy-units "eV" \
  --intermatch-energy-normalization "per source supercell" \
  --intermatch-strained-side A \
  --intermatch-thickness-convention "3.45 angstrom effective thickness"
```

The script does not convert these values. It records the declarations, file
SHA256, size, and row count in the run metadata and each InterMatch method-run
record. `method-run-diagnostics.jsonl` contains one record per method and
search, including all adapter parameters and outcomes; for the InterOptimus
analogue this includes the complete class membership and representative maps.

The adapters operationalize selected paper- and source-described rules on
CALM's fixed-surface two-dimensional ledger. They do not execute or claim
bitwise parity with the external packages. The output metadata records this
fidelity limitation and the exact CALM search settings, surface identities,
and surface-symmetry groups used for every comparison. In particular, the
InterOptimus analogue uses a documented deterministic CALM-ledger order for
greedy representative selection and omits the external code's atomistic
structure-matching fallback.
