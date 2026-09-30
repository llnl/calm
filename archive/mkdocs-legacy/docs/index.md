# CALM

**Canonicalized Affine-invariant Lattice Matching for interface Models**

CALM is a Python library for deterministic enumeration and optimization of crystalline interfaces using affine-invariant geometric methods.

## Key Features

- 🎯 **Deterministic** - Same inputs always give same outputs (no random seeds)
- 📐 **Affine-invariant** - Strain metrics independent of coordinate choice
- ⚡ **Fast** - Optimized 2×2 matrix operations, parallel-ready architecture
- 🔬 **ML-ready** - Integrated calculator backends for GRACE and MACE (additional MLIP frameworks are being added)
- 💾 **Persistent** - Workspace-based storage with SQLite database
- 🔍 **Searchable** - Query and filter results efficiently

## Quick Links

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Getting Started__

    ---

    Install CALM and run your first prototype search in 5 minutes

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-package-variant:{ .lg .middle } __Conda environments__

    ---

    Reproducible installs for different MLIP frameworks (separate envs for incompatible dependencies)

    [:octicons-arrow-right-24: Environments](getting-started/conda_environments.md)

-   :material-school:{ .lg .middle } __Tutorials__

    ---

    Step-by-step guides from workspace basics to advanced strain analysis

    [:octicons-arrow-right-24: Tutorials](tutorials/index.md)

-   :material-algorithm:{ .lg .middle } __Algorithms__

    ---

    Mathematical foundations and implementation details

    [:octicons-arrow-right-24: Algorithms](mathematics/algorithms/README.md)

-   :material-api:{ .lg .middle } __API Reference__

    ---

    Complete documentation of public methods and classes

    [:octicons-arrow-right-24: API](reference/public_api.md)

</div>

## What is CALM?

CALM solves the **interface matching problem**: given two crystal structures, find all geometrically compatible ways to stack them into an interface.

### The Challenge

Traditional approaches suffer from:
- **Coordinate dependence** - Results depend on arbitrary basis choices
- **Incomplete enumeration** - Miss valid configurations
- **Duplicates** - Same configuration appears multiple times
- **Arbitrary strain assignment** - No principled way to distribute mismatch

### CALM's Solution

CALM uses **canonicalized affine-invariant methods**:

1. **Surface preprocessing** - Reduce to canonical primitive lattice
2. **Supercell enumeration** - Enumerate all HNF matrices up to k_max
3. **Lattice matching** - Compute affine-invariant strain metrics
4. **Geodesic strain partition** - Distribute strain via SPD(2) geometry
5. **SNF pruning** - Remove redundant refinements
6. **Registry optimization** - Optimize atomic alignment

Result: **Complete, duplicate-free enumeration** with **coordinate-independent strain metrics**.

## Example Workflow

```python
from calm import Surface, SearchSettings, search_interfaces

surface_a = Surface("MaterialA.poscar", miller=(1, 1, 1), thickness=10.0, material="A")
surface_b = Surface("MaterialB.poscar", miller=(0, 0, 1), thickness=10.0, material="B")

result = search_interfaces(
    surface_a,
    surface_b,
    settings=SearchSettings(
        max_principal_strain=0.10,
        max_atoms=300,
        max_supercell_index=12,
        max_candidates=25,
    ),
)

print(result.to_dataframe())
result.plot_pareto(save="pareto.png")

interface = result.best.build(strain_partition="both", alpha=0.5, gap=1.5, vacuum=15.0)
interface.write("interface.POSCAR")
```

For persistent campaigns, use `open_project(...)` and query generated structures through scientific collections such as `project.structures()`, `project.candidates()`, and `project.interfaces()`.

## Key Concepts

### Projects and generated-structure inventories

A **project** is the public recovery layer for persistent CALM work. Users query
scientific collections such as `project.structures()`, `project.candidates()`,
`project.interfaces()`, and `project.energies()` instead of inspecting SQLite
tables or artifact-store paths directly. The underlying workspace/database
implementation is an advanced detail.

### Affine-Invariant Strain

Traditional strain metrics depend on coordinate basis. CALM uses **geodesic distances on the SPD(2) manifold**:

$$
d_{\text{cell}}(S_A, S_B) = \left\| \log\left(G_A^{-1/2} G_B G_A^{-1/2}\right) \right\|_F
$$

where $G = S^T S$ is the Gram matrix. This distance is:
- **Coordinate-independent** (affine-invariant)
- **Physically meaningful** (geodesic on Riemannian manifold)
- **Additive under composition**

### Geodesic Strain Partitioning

To distribute mismatch strain, CALM interpolates Gram matrices along geodesics:

$$
G(\alpha) = G_A^{1/2} \left(G_A^{-1/2} G_B G_A^{-1/2}\right)^\alpha G_A^{1/2}
$$

- $\alpha = 0$: All strain on B (A unstrained)
- $\alpha = 0.5$: Symmetric distribution
- $\alpha = 1$: All strain on A (B unstrained)

## Documentation Structure

### [Tutorials](tutorials/index.md)
Step-by-step learning path from basics to advanced topics. Start here if you're new to CALM.

### [Guides](guides/index.md)
Task-focused recipes for specific workflows. Use when you know what you want to do.

### [Algorithms](mathematics/algorithms/README.md)
Mathematical foundations and implementation details. For understanding the "why" and "how".

### [Concepts](concepts/overview.md)
Background explanations of key ideas (UIDs, workspaces, calculators, etc.).

### [API Reference](reference/public_api.md)
Complete documentation of all public methods, classes, and functions.

## Installation

The recommended workflow is to install CALM from source into a backend-specific conda environment.

```bash
# From the CALM repository root
conda env create -f environments/calm-base.yml
conda activate calm-base
pip install -e . --no-deps
```

If you plan to use an MLIP backend, choose the corresponding environment file in `environments/` (for example `calm-mace.yml`, `calm-sevennet.yml`, `calm-nequip.yml`, `calm-mattersim.yml`, or `calm-grace.yml`).

See [Installation](getting-started/installation.md) for detailed instructions.

## Citation

If you use CALM in your research, please cite:

> Weitzner, S., et al. (2024). "CALM: Canonicalized Affine-invariant Lattice Matching for interface Models." *In preparation*.

## License

CALM is released under the MIT License. See `LICENSE` for details.

## Getting Help

- **Documentation**: You're reading it!
- **Examples**: Check `examples/` directory in the repository
- **Issues**: Report bugs on [GitLab Issues](https://gitlab.com/sweitzner/CALM/-/issues)
- **Discussions**: Ask questions on [GitLab Discussions](https://gitlab.com/sweitzner/CALM/-/issues)

## Next Steps

<div class="grid" markdown>

:material-clock-fast:{ .lg .middle } **Quick Start**

Get up and running in 5 minutes with our [Quickstart Guide](getting-started/quickstart.md)

---

:material-school:{ .lg .middle } **Learn the Basics**

Follow our [Tutorial Series](tutorials/index.md) to master CALM

---

:material-code-braces:{ .lg .middle } **Explore Examples**

Check out real-world examples in `examples/` directory

---

:material-file-document:{ .lg .middle } **Deep Dive**

Understand the algorithms in [Algorithm Documentation](mathematics/algorithms/README.md)

</div>
