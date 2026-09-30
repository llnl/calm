# Compare interface candidates

<p class="calm-lede">
Inspect the complete LiF/Li₂O candidate population, identify the strain–size Pareto front, and create a shortlist for an explicit modeling objective.
</p>

<div class="calm-page-facts" markdown>
- **Outcome:** a Pareto-filtered candidate shortlist
- **Calculator:** not required
- **Inputs:** package-owned LiF and Li₂O tutorial structures
- **Canonical program:** `examples/tutorials/compare_candidates.py`
</div>

## Outcome

The first tutorial selected one candidate to demonstrate construction. This tutorial slows down at the scientifically important decision: **which coherent candidate should be modeled?**

You will:

1. run a broader search;
2. export the complete candidate table;
3. retain candidates on the saved strain–size Pareto front;
4. apply a principal-strain threshold;
5. rank the remaining candidates by the search score; and
6. record the selected candidate identifier.

The tutorial creates its own project and does not depend on the first tutorial.

<figure class="calm-figure calm-figure--wide" markdown>

[![Illustrative candidate scatter plot with estimated atom count on the horizontal axis and cell mismatch on the vertical axis. Dominated candidates are filtered to four Pareto candidates, three of which satisfy the tutorial strain threshold and form a shortlist.](../assets/figures/tutorials/candidate-selection.svg)](../assets/figures/tutorials/candidate-selection.svg)
  <figcaption>Pareto filtering removes candidates that are no better in either cell size or mismatch. The remaining front is a set of tradeoffs, not a unique scientific answer.</figcaption>
</figure>

## Prerequisites

Use the same geometry-capable CALM environment required by the first tutorial:

```bash
python -c "import calm, ase, spglib"
```

Run the canonical program:

```bash
python examples/tutorials/compare_candidates.py \
  --work-dir examples/work/compare-candidates \
  --reset
```

Add `--plot` to write a PNG Pareto plot when CALM's plotting dependencies are installed:

```bash
python examples/tutorials/compare_candidates.py \
  --work-dir examples/work/compare-candidates \
  --reset \
  --plot
```

## Workflow

### 1. Search a larger candidate space

The program recreates the two materials and selected (100) surfaces, then uses broader supercell and atom-count limits than the first tutorial:

```python
--8<-- "examples/tutorials/compare_candidates.py:compare-candidates-search"
```

The search result is a saved object whose candidate collection supports filtering, tabulation, plotting, and selection without rerunning the matching calculation.

### 2. Separate Pareto filtering from model selection

```python
--8<-- "examples/tutorials/compare_candidates.py:compare-candidates-select"
```

This sequence contains three distinct decisions:

1. `select(pareto=True)` keeps candidates on the full search population's saved strain–size Pareto front.
2. `where(max_principal_strain=(None, 0.08))` applies the tutorial's additional 8% principal-strain limit.
3. `select_top(5, by="score")` orders the eligible set using the search score and keeps at most five candidates.

If the 8% threshold removes every Pareto candidate, the tutorial falls back to the top five Pareto candidates rather than silently returning an empty shortlist.

The saved Pareto front uses two objectives:

- interface atom count, represented in tables by `n_atoms_estimate`; and
- the dimensionless cell mismatch measure `d_cell`.

A candidate is dominated when another candidate is no larger and no more mismatched, with a strict improvement in at least one objective. Pareto filtering removes clearly inferior size–mismatch choices. It does not determine the correct termination, registry, energy, or experimental structure.

### 3. Export views for different questions

```python
--8<-- "examples/tutorials/compare_candidates.py:compare-candidates-export"
```

The tutorial writes three CSV files:

| File | Contents | Use |
|---|---|---|
| `candidates-all.csv` | Every admitted candidate | Audit the full search population. |
| `candidates-pareto.csv` | Saved Pareto candidates | Inspect nondominated size–mismatch tradeoffs. |
| `candidates-shortlist.csv` | Pareto candidates after the tutorial's strain and score rules | Choose models to build or compare. |

The default candidate table contains the most useful comparison fields:

| Field | Interpretation |
|---|---|
| `candidate_id` | Short identifier used to select or trace a candidate. |
| `n_atoms_estimate` | Estimated atom count of the constructed interface. |
| `d_cell` | Dimensionless cell mismatch measure; smaller is a closer cell match. |
| `d_area` | Area-change contribution to `d_cell`. |
| `d_shape` | Shape-change contribution to `d_cell`. |
| `max_principal_strain` | Largest absolute principal strain required by the coherent mapping. |
| `score` | Search ranking that combines configured objectives; it is not an energy. |
| `is_pareto` | Whether the candidate belongs to the saved full-population front. |

## Inspect the result

The program creates:

```text
examples/work/compare-candidates/
├── compare-candidates.calm/
└── outputs/
    ├── candidates-all.csv
    ├── candidates-pareto.csv
    ├── candidates-shortlist.csv
    ├── run-summary.json
    └── candidate-pareto.png       # only with --plot
```

Inspect the shortlist directly:

```bash
python - <<'PY'
import csv
from pathlib import Path

path = Path("examples/work/compare-candidates/outputs/candidates-shortlist.csv")
with path.open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        print(
            row["candidate_id"],
            row["n_atoms_estimate"],
            row["d_cell"],
            row["max_principal_strain"],
        )
PY
```

## Expected output

A verified run with the current tutorial resources produced:

```text
[tutorial] outcome: a Pareto-filtered LiF/Li2O candidate shortlist
[tutorial] candidates: 429
[tutorial] Pareto candidates: 4
[tutorial] shortlist: 3
```

These counts describe one verified run, not a fixed expected outcome. The stable expectations are:

- at least one candidate is found;
- at least one Pareto candidate exists;
- the shortlist is nonempty;
- all three CSV views and `run-summary.json` are written.

## Interpretation

Different modeling objectives can justify different choices on the same Pareto front:

- choose a smaller interface when downstream calculations are expensive;
- choose a lower-mismatch interface when coherent strain is the dominant concern;
- retain several candidates when registry, relaxation, or energy may reverse the geometric ranking;
- reject the complete front when every candidate violates a scientific limit not represented by the two Pareto objectives.

The tutorial records one `selected_candidate` in `run-summary.json`, but it does not claim that this candidate is universally best.

## Limitations

!!! note "The search score is not a thermodynamic quantity"
    `score` is a configured geometric ranking. It cannot replace structural relaxation, energy evaluation, comparison with experiment, or system-specific scientific judgment.

The atom count is an estimate at search time. Construction settings and later workflow stages determine the realized atomistic model.

## Next step

Continue with [Refine, relax, and evaluate](refine-relax-evaluate.md) to see how strain allocation, registry, calculator-backed relaxation, and explicit energy references add information that is absent from geometric candidate ranking.
