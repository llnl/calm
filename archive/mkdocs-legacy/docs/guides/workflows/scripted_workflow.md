# Scripted Workflow (Workspace)

Automate complete CALM workflows from bulk structures to optimized interfaces using Python scripts.

## Overview

This guide shows how to build **end-to-end automated workflows** with the workspace API, suitable for:

- **Batch processing** - Multiple material systems
- **HPC deployment** - SLURM/PBS job arrays
- **Reproducible pipelines** - Version-controlled scripts
- **Production campaigns** - Large-scale interface generation

**Key principles:**
- All operations through workspace API
- Explicit run queue management
- Artifact organization automatic
- Full provenance tracking

## Minimal End-to-End Script

Complete workflow from bulk POSCAR files to Pareto candidates:

```python
#!/usr/bin/env python3
"""minimal_workflow.py - Basic CALM workflow"""

from pathlib import Path
from calm.project import open_workspace
from calm.project.runner import run_until_empty

def main():
    # 1. Create/open workspace
    ws = open_workspace(Path("workspace"))

    # 2. Add bulks
    bulk_a = ws.add_bulk_from_poscar(
        Path("structures/LiF.poscar"),
        label="LiF",
    )
    bulk_b = ws.add_bulk_from_poscar(
        Path("structures/Li2O.poscar"),
        label="Li2O",
    )

    # 3. Build slabs
    slabs_a = ws.build_slabs(
        bulk_a.id_short,
        millers=[(1, 0, 0), (1, 1, 0)],
        params={"vacuum": 15.0, "layers": 5},
    )
    slabs_b = ws.build_slabs(
        bulk_b.id_short,
        millers=[(1, 0, 0), (1, 1, 0)],
        params={"vacuum": 15.0, "layers": 5},
    )

    # 4. Start prototype searches
    runs = []
    for slab_a in slabs_a:
        for slab_b in slabs_b:
            run = ws.start_prototype_search(
                slab_a.id_short,
                slab_b.id_short,
                n_candidates=50,
                label=f"{slab_a.miller}_{slab_b.miller}",
            )
            runs.append(run)

    # 5. Execute all queued runs
    run_until_empty(ws)

    # 6. Generate Pareto plots
    for run in runs:
        ws.enrichment.pareto_plot(
            run.id_short,
            filename="pareto.png",
        )

    print(f"Completed {len(runs)} searches")

if __name__ == "__main__":
    main()
```

**Run:**
```bash
$ python minimal_workflow.py
Added bulk: b_a1b2c3d4 (LiF)
Added bulk: b_e5f6g7h8 (Li2O)
Built 2 slabs for LiF
Built 2 slabs for Li2O
Started 4 prototype searches
Executing runs...
Completed 4 searches
```

## Structured Workflow Template

Production-ready template with configuration, logging, and error handling:

```text
#!/usr/bin/env python3
"""production_workflow.py - Production CALM workflow with config"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
import json

from calm.project import open_workspace
from calm.project.runner import run_until_empty

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('workflow.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Workflow configuration"""
    workspace_root: Path
    structure_dir: Path

    # Material pairs to evaluate
    material_pairs: List[Tuple[str, str]]

    # Slab parameters
    millers: List[Tuple[int, int, int]]
    slab_vacuum: float = 15.0
    slab_layers: int = 5

    # Search parameters
    k_max: int = 12
    n_candidates: int = 100
    eps_principal_max: float = 0.15
    w_match: float = 0.5

    # Follow-up parameters
    strain_scan_alphas: List[float] = None
    registry_n_steps: int = 400
    registry_n_seeds: int = 5

    # Calculator
    calculator_family: str = "grace"
    calculator_model: str = "GRACE-2L-OMAT"

    def __post_init__(self):
        if self.strain_scan_alphas is None:
            self.strain_scan_alphas = [0.0, 0.25, 0.5, 0.75, 1.0]

    @classmethod
    def from_json(cls, path: Path) -> "WorkflowConfig":
        """Load config from JSON file"""
        with open(path) as f:
            data = json.load(f)

        # Convert paths
        data['workspace_root'] = Path(data['workspace_root'])
        data['structure_dir'] = Path(data['structure_dir'])

        # Convert tuples
        data['material_pairs'] = [tuple(p) for p in data['material_pairs']]
        data['millers'] = [tuple(m) for m in data['millers']]

        return cls(**data)


class CALMWorkflow:
    """Automated CALM workflow runner"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.ws = open_workspace(config.workspace_root)
        self.bulk_ids = {}
        self.slab_ids = {}
        self.search_runs = []
        self.scan_runs = []
        self.registry_runs = []

    def run_complete_workflow(self):
        """Run all workflow stages"""
        logger.info("Starting CALM workflow")

        try:
            self.stage_1_add_bulks()
            self.stage_2_build_slabs()
            self.stage_3_prototype_searches()
            self.stage_4_analyze_results()
            self.stage_5_follow_up_scans()
            self.stage_6_export_results()

            logger.info("Workflow completed successfully")

        except Exception as e:
            logger.error(f"Workflow failed: {e}", exc_info=True)
            raise

    def stage_1_add_bulks(self):
        """Add bulk structures to workspace"""
        logger.info("Stage 1: Adding bulk structures")

        # Collect unique materials
        materials = set()
        for mat_a, mat_b in self.config.material_pairs:
            materials.add(mat_a)
            materials.add(mat_b)

        for material in materials:
            poscar_path = self.config.structure_dir / f"{material}.poscar"

            if not poscar_path.exists():
                raise FileNotFoundError(f"POSCAR not found: {poscar_path}")

            bulk = self.ws.add_bulk_from_poscar(
                poscar_path,
                label=material,
                metadata={"source": str(poscar_path)},
            )

            self.bulk_ids[material] = bulk.id_short
            logger.info(f"  Added {material}: {bulk.id_short}")

    def stage_2_build_slabs(self):
        """Build slabs for all bulks"""
        logger.info("Stage 2: Building slabs")

        for material, bulk_id in self.bulk_ids.items():
            slabs = self.ws.build_slabs(
                bulk_id,
                millers=self.config.millers,
                params={
                    "vacuum": self.config.slab_vacuum,
                    "layers": self.config.slab_layers,
                },
            )

            self.slab_ids[material] = {
                slab.miller: slab.id_short for slab in slabs
            }

            logger.info(f"  Built {len(slabs)} slabs for {material}")

    def stage_3_prototype_searches(self):
        """Run prototype searches for all material pairs"""
        logger.info("Stage 3: Prototype searches")

        for mat_a, mat_b in self.config.material_pairs:
            slabs_a = self.slab_ids[mat_a]
            slabs_b = self.slab_ids[mat_b]

            for miller_a in self.config.millers:
                for miller_b in self.config.millers:
                    slab_a_id = slabs_a[miller_a]
                    slab_b_id = slabs_b[miller_b]

    run = self.ws.start_prototype_search(
        slab_a_id,
        slab_b_id,
        n_candidates=self.config.n_candidates,
        k_max=self.config.k_max,
        eps_principal_max=self.config.eps_principal_max,
        w_match=self.config.w_match,
        label=f"{mat_a}{miller_a}_{mat_b}{miller_b}",
    )

                    self.search_runs.append(run)
                    logger.info(f"  Started search: {run.label}")

        # Execute all searches
        logger.info("  Executing prototype searches...")
        run_until_empty(self.ws)
        logger.info(f"  Completed {len(self.search_runs)} searches")

    def stage_4_analyze_results(self):
        """Analyze search results and generate plots"""
        logger.info("Stage 4: Analyzing results")

        summary = []

        for run in self.search_runs:
            # Get prototypes
            prototypes = self.ws.list_prototypes(run=run.id_short)
            pareto = self.ws.list_prototypes(
                run=run.id_short,
                pareto=True,
            )

            # Generate plot
            self.ws.enrichment.pareto_plot(
                run.id_short,
                filename="pareto.png",
            )

            summary.append({
                'run_id': run.id_short,
                'label': run.label,
                'total_prototypes': len(prototypes),
                'pareto_count': len(pareto),
                'best_match_score': min(p.match_score for p in prototypes) if prototypes else None,
            })

            logger.info(f"  {run.label}: {len(prototypes)} total, {len(pareto)} Pareto")

        # Save summary
        summary_path = self.config.workspace_root / "search_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"  Saved summary: {summary_path}")

    def stage_5_follow_up_scans(self):
        """Run follow-up scans on best candidates"""
        logger.info("Stage 5: Follow-up scans")

        calc_spec = {
            "family": self.config.calculator_family,
            "model": self.config.calculator_model,
        }

        for run in self.search_runs:
            # Get top 3 Pareto candidates
            pareto = self.ws.list_prototypes(
                run=run.id_short,
                pareto=True,
            )

            if not pareto:
                logger.warning(f"  No Pareto candidates for {run.label}, skipping")
                continue

            pareto.sort(key=lambda p: p.match_score)
            top_protos = pareto[:3]
            proto_ids = [p.id_short for p in top_protos]

            # Strain partition scan
            scan_run = self.ws.start_strain_partition_scan(
                proto_ids,
                alphas=self.config.strain_scan_alphas,
                calculator_spec=calc_spec,
                relax=True,
                fmax=0.05,
                label=f"strain_scan_{run.label}",
            )

            self.scan_runs.append(scan_run)
            logger.info(f"  Started strain scan: {scan_run.label}")

        # Execute scans
        if self.scan_runs:
            logger.info("  Executing strain scans...")
            run_until_empty(self.ws)
            logger.info(f"  Completed {len(self.scan_runs)} scans")

    def stage_6_export_results(self):
        """Export optimized structures"""
        logger.info("Stage 6: Exporting results")

        export_dir = self.config.workspace_root / "exports"
        export_dir.mkdir(exist_ok=True)

        from ase.io import write

        export_count = 0

        for scan_run in self.scan_runs:
            # Get derived interfaces
            interfaces = self.ws.list_derived_interfaces(
                run=scan_run.id_short,
            )

            if not interfaces:
                continue

            # Find best
            best = min(interfaces, key=lambda i: i.energy_total)

            # Get full structure
            interface = self.ws.get_derived_interface(best.id_short)

            # Export
            filename = f"{scan_run.label}_{best.id_short}.vasp"
            export_path = export_dir / filename
            write(export_path, interface.atoms, format="vasp")

            export_count += 1
            logger.info(f"  Exported: {filename}")

        logger.info(f"  Total exported: {export_count} structures")


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python production_workflow.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])

    # Load configuration
    logger.info(f"Loading config: {config_path}")
    config = WorkflowConfig.from_json(config_path)

    # Run workflow
    workflow = CALMWorkflow(config)
    workflow.run_complete_workflow()


if __name__ == "__main__":
    main()
```

**Configuration file (workflow_config.json):**

```json
{
  "workspace_root": "my_workspace",
  "structure_dir": "structures",
  "material_pairs": [
    ["LiF", "Li2O"],
    ["MgO", "Al2O3"]
  ],
  "millers": [
    [1, 0, 0],
    [1, 1, 0],
    [1, 1, 1]
  ],
  "slab_vacuum": 15.0,
  "slab_layers": 5,
  "k_max": 12,
  "n_candidates": 100,
  "eps_principal_max": 0.15,
  "w_match": 0.5,
  "strain_scan_alphas": [0.0, 0.25, 0.5, 0.75, 1.0],
  "registry_n_steps": 400,
  "registry_n_seeds": 5,
  "calculator_family": "grace",
  "calculator_model": "GRACE-2L-OMAT"
}
```

**Run:**
```bash
$ python production_workflow.py workflow_config.json
2026-02-26 10:00:00 - __main__ - INFO - Loading config: workflow_config.json
2026-02-26 10:00:01 - __main__ - INFO - Starting CALM workflow
2026-02-26 10:00:01 - __main__ - INFO - Stage 1: Adding bulk structures
2026-02-26 10:00:02 - __main__ - INFO -   Added LiF: b_a1b2c3d4
2026-02-26 10:00:03 - __main__ - INFO -   Added Li2O: b_e5f6g7h8
...
```

## HPC Integration

### SLURM Job Script

```bash
#!/bin/bash
#SBATCH --job-name=calm_workflow
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --partition=standard
#SBATCH --output=calm_%j.out
#SBATCH --error=calm_%j.err

# Load modules
module load python/3.10
module load cuda/11.8  # If using GPU calculators

# Activate environment
source ~/.venv/calm/bin/activate

# Set environment variables
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
export CALM_WORKSPACE=/path/to/workspace

# Run workflow
python production_workflow.py workflow_config.json

# Check status
if [ $? -eq 0 ]; then
    echo "Workflow completed successfully"
else
    echo "Workflow failed with exit code $?"
    exit 1
fi
```

**Submit:**
```bash
$ sbatch calm_workflow.slurm
Submitted batch job 123456
```

### Array Jobs for Parallel Searches

```bash
#!/bin/bash
#SBATCH --job-name=calm_array
#SBATCH --array=0-11
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --output=calm_array_%A_%a.out

# Define material pairs and Miller indices
MATERIALS=(LiF:Li2O MgO:Al2O3)
MILLERS=(100:100 110:110 111:111)

# Calculate indices
N_MILLERS=${#MILLERS[@]}
MAT_IDX=$((SLURM_ARRAY_TASK_ID / N_MILLERS))
MILLER_IDX=$((SLURM_ARRAY_TASK_ID % N_MILLERS))

MAT_PAIR=${MATERIALS[$MAT_IDX]}
MILLER_PAIR=${MILLERS[$MILLER_IDX]}

IFS=':' read -ra MAT_ARR <<< "$MAT_PAIR"
IFS=':' read -ra MILLER_ARR <<< "$MILLER_PAIR"

MAT_A=${MAT_ARR[0]}
MAT_B=${MAT_ARR[1]}
MILLER_A=${MILLER_ARR[0]}
MILLER_B=${MILLER_ARR[1]}

echo "Processing: ${MAT_A}(${MILLER_A}) / ${MAT_B}(${MILLER_B})"

# Run single search
python run_single_search.py \
    --workspace $CALM_WORKSPACE \
    --mat-a $MAT_A \
    --mat-b $MAT_B \
    --miller-a $MILLER_A \
    --miller-b $MILLER_B \
    --k-max 12 \
    --n-candidates 100
```

**Supporting script (run_single_search.py):**

```python
#!/usr/bin/env python3
import argparse
from calm.project import open_workspace
from calm.project.runner import run_until_empty

def parse_miller(s):
    """Parse '111' -> (1, 1, 1)"""
    return tuple(int(c) for c in s)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--mat-a', required=True)
    parser.add_argument('--mat-b', required=True)
    parser.add_argument('--miller-a', required=True)
    parser.add_argument('--miller-b', required=True)
    parser.add_argument('--k-max', type=int, default=12)
    parser.add_argument('--n-candidates', type=int, default=100)
    args = parser.parse_args()

    ws = open_workspace(args.workspace)

    # Helper: find slab by material and Miller index
    def find_slab_by_material_and_miller(ws, material: str, miller: tuple[int, int, int]):
        bulk = ws.find_bulk_by_material(material)
        if bulk is None:
            raise KeyError(f"No bulk found for material {material!r}")

        for slab in ws.list_slabs(bulk=bulk.id_short):
            if tuple(slab.miller) == tuple(miller):
                return slab

        raise KeyError(f"No slab found for material {material!r} with Miller index {miller!r}")

    slab_a = find_slab_by_material_and_miller(ws, args.mat_a, parse_miller(args.miller_a))
    slab_b = find_slab_by_material_and_miller(ws, args.mat_b, parse_miller(args.miller_b))

    # Start search
    run = ws.start_prototype_search(
        slab_a.id_short,
        slab_b.id_short,
        k_max=args.k_max,
        n_candidates=args.n_candidates,
        label=f"{args.mat_a}{args.miller_a}_{args.mat_b}{args.miller_b}",
    )

    # Execute
    run_until_empty(ws, run_ids=[run.id_short])

    print(f"Completed: {run.id_short}")

if __name__ == "__main__":
    main()
```

## Advanced Patterns

### Conditional Workflow

Execute stages based on results from previous stages:

```text
def conditional_workflow(ws, bulk_ids, quality_threshold=0.3):
    """Only run follow-ups if search quality is good"""

    # Stage 1: Prototype search
    search_run = ws.start_prototype_search(...)
    run_until_empty(ws)

    # Check quality
    pareto = ws.list_prototypes(run=search_run.id_short, pareto=True)

    if not pareto:
        logger.warning("No Pareto candidates, skipping follow-ups")
        return

    best_score = min(p.match_score for p in pareto)

    if best_score > quality_threshold:
        logger.warning(f"Best score {best_score:.3f} exceeds threshold {quality_threshold}, skipping")
        return

    # Stage 2: Follow-ups (only if quality good)
    logger.info("Quality good, running follow-ups")
    scan_run = ws.start_strain_partition_scan(...)
    run_until_empty(ws)
```

### Incremental Processing

Process large batches incrementally:

```text
def incremental_workflow(ws, material_list, batch_size=10):
    """Process materials in batches to manage memory"""

    for i in range(0, len(material_list), batch_size):
        batch = material_list[i:i+batch_size]

        logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} materials")

        # Add bulks for this batch
        bulk_ids = []
        for material in batch:
            bulk = ws.add_bulk_from_poscar(...)
            bulk_ids.append(bulk.id_short)

        # Build slabs
        for bulk_id in bulk_ids:
            slabs = ws.build_slabs(bulk_id, ...)

        # Run searches
        runs = []
        # ... start searches ...

        run_until_empty(ws)

        # Save checkpoint
        checkpoint = {
            'completed_batches': i//batch_size + 1,
            'total_batches': (len(material_list) + batch_size - 1) // batch_size,
        }
        with open('checkpoint.json', 'w') as f:
            json.dump(checkpoint, f)

        logger.info(f"Completed batch {i//batch_size + 1}")
```

### Error Recovery

Handle failures gracefully:

```text
def robust_workflow(ws, config):
    """Workflow with error recovery and retry logic"""

    max_retries = 3
    failed_runs = []

    for attempt in range(max_retries):
        logger.info(f"Attempt {attempt + 1}/{max_retries}")

        try:
            # Get pending runs
            pending = ws.list_runs(status='pending')

            if not pending:
                logger.info("No pending runs")
                break

            # Execute
            run_until_empty(ws)

            # Check for failures
            for run in pending:
                run_updated = ws.get_run(run.id_short)
                if run_updated.status == 'failed':
                    failed_runs.append(run)
                    logger.error(f"Run failed: {run.id_short} - {run_updated.error_message}")

        except Exception as e:
            logger.error(f"Workflow error on attempt {attempt + 1}: {e}", exc_info=True)

            if attempt < max_retries - 1:
                logger.info(f"Retrying in 60 seconds...")
                import time
                time.sleep(60)
            else:
                logger.error("Max retries exceeded")
                raise

    if failed_runs:
        logger.warning(f"Workflow completed with {len(failed_runs)} failed runs")
        for run in failed_runs:
            logger.warning(f"  {run.id_short}: {run.label}")
    else:
        logger.info("Workflow completed successfully with no failures")
```

## Testing and Validation

### Dry Run Mode

Test workflow without executing expensive operations:

```text
class DryRunWorkspace:
    """Wrapper for dry-run testing"""

    def __init__(self, ws):
        self.ws = ws
        self.dry_run = True

    def mutations(self):
        if self.dry_run:
            return DryRunMutations(self.ws)
        return self.ws.mutations

    # ... wrap other methods ...

class DryRunMutations:
    def start_prototype_search(self, *args, **kwargs):
        logger.info(f"[DRY RUN] Would start prototype search with: {kwargs}")
        return MockRun(id_short="r_dryrun123", status="pending")

# Use
ws = DryRunWorkspace(open_workspace(...))
workflow = CALMWorkflow(config, ws=ws)
workflow.run_complete_workflow()  # Logs actions without executing
```

### Unit Testing

Test workflow components:

```text
import unittest
from unittest.mock import Mock, patch

class TestWorkflow(unittest.TestCase):

    def setUp(self):
        self.config = WorkflowConfig(...)
        self.workflow = CALMWorkflow(self.config)

    @patch('calm.project.open_workspace')
    def test_stage_1_add_bulks(self, mock_open):
        mock_ws = Mock()
        mock_ws.mutations.add_bulk_from_poscar.return_value = Mock(id_short="b_test123")
        self.workflow.ws = mock_ws

        self.workflow.stage_1_add_bulks()

        self.assertIn("LiF", self.workflow.bulk_ids)
        self.assertEqual(mock_ws.mutations.add_bulk_from_poscar.call_count, len(self.config.materials))

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            WorkflowConfig(
                workspace_root="/tmp",
                structure_dir="/tmp",
                material_pairs=[],  # Empty
                millers=[(1, 0, 0)],
            )
```

## Best Practices

### 1. Configuration Management

```text
# Store configs in version control
configs/
├── production.json      # Production parameters
├── development.json     # Fast testing parameters
└── hpc_large.json      # Large-scale HPC run

# Use environment-specific configs
import os
env = os.getenv('CALM_ENV', 'development')
config_path = Path(f"configs/{env}.json")
```

### 2. Logging and Monitoring

```python
# Structured logging
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'workflow.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file', 'console'],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### 3. Resource Estimation

```python
def estimate_resources(config):
    """Estimate computational requirements"""

    n_materials = len(set(sum(config.material_pairs, ())))
    n_slabs = n_materials * len(config.millers)
    n_searches = len(config.material_pairs) * len(config.millers) ** 2

    # Prototype search cost
    avg_supercells_per_slab = config.k_max ** 1.5  # Rough estimate
    avg_candidates = config.n_candidates

    # Follow-up cost
    n_alphas = len(config.strain_scan_alphas)
    top_candidates_per_search = 3

    total_energy_evals = (
        n_searches * avg_candidates +  # Initial prototypes
        n_searches * top_candidates_per_search * n_alphas +  # Strain scans
        n_searches * top_candidates_per_search * config.registry_n_steps * config.registry_n_seeds  # Registry
    )

    # Time estimate (assuming 0.1s per eval with GRACE)
    time_estimate = total_energy_evals * 0.1 / 3600  # hours

    print(f"Resource estimates:")
    print(f"  Materials: {n_materials}")
    print(f"  Slabs: {n_slabs}")
    print(f"  Searches: {n_searches}")
    print(f"  Energy evaluations: {total_energy_evals:,}")
    print(f"  Estimated time: {time_estimate:.1f} hours")

    return {
        'n_searches': n_searches,
        'n_energy_evals': total_energy_evals,
        'estimated_hours': time_estimate,
    }
```

## Troubleshooting

### Workspace Locked

**Symptom:** `database is locked` error

**Solution:**
```python
# Open workspace when needed and rely on the framework's resource management.
# Do not rely on a non-existent `ws.close` method in public examples.
ws = open_workspace("workspace")
# Do work with ws. The underlying implementation manages DB sessions per operation.
```

### Out of Memory

**Symptom:** Python process killed on HPC

**Solution:**
```python
# Process in smaller batches
# Request more memory in SLURM:
#SBATCH --mem=32GB  # Instead of default

# Or use generator patterns
def process_in_chunks(items, chunk_size=100):
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i+chunk_size]
        process_chunk(chunk)
        # Memory freed between chunks
```

### Incomplete Runs

**Symptom:** Some runs stuck in "pending"

**Solution:**
```python
# Check run status
pending = ws.list_runs(status='pending')
for run in pending:
    print(f"{run.id_short}: {run.label}")

# Force re-execute specific run
run_until_empty(ws, run_ids=["r_specific123"])

# Or inspect failed runs and decide the appropriate recovery action
failed = ws.list_runs(status='failed')
for run in failed:
    print(f"{run.id_short}: {run.label} - {run.error_message}")
# Depending on the failure mode, create a new corrected run or queue a follow-up job
# rather than mutating historical run records in place.
```

## Related Documentation

- [Tutorial 01: Workspace Basics](../../tutorials/01_workspace_basics.md) - Workspace fundamentals
- [Tutorial 03: Prototype Search](../../tutorials/03_prototype_search.md) - Search workflow
- [Workspace Prototype Search](project_prototype_search.md) - Interactive workflow
- [Workspace Interface Optimization](project_interface_optimization.md) - Follow-up workflows
- [Concepts: Workspace Layout](../../concepts/project_layout.md) - File organization
-- [Development: Runner](../../development/runner.md) - Run queue details

## See Also

- `examples/03_match_interfaces.py` - Example script
- `examples/04_compare_interface_searches.py` - Follow-up script
- [Public API Reference](../../reference/public_api.md) - Complete API
