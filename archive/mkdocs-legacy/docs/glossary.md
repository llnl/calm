# Glossary

Comprehensive glossary of terms used throughout CALM documentation and API.

---

## Core Concepts

### Affine-Invariant
Property of a metric or measurement that remains unchanged under affine transformations (rotation, scaling, shearing). CALM's strain metrics are affine-invariant, meaning they don't depend on arbitrary coordinate basis choices.

### Bulk
A 3D periodic crystal structure representing an infinite material with no surfaces. In CALM, bulks are the starting point for slab generation. Can be "reference" (unoptimized) or "optimized" (relaxed with calculator).

### Calculator
A computational engine for evaluating energies and forces. CALM supports machine learning potentials via first-class calculator backends (currently GRACE and MACE), plus reference calculators through ASE (e.g., EMT) and external engines such as LAMMPS (via ASE).

### Canonical Gauge
A standard, deterministic orientation for a lattice basis. CALM uses canonical gauges (Niggli reduction, Cholesky factorization) to eliminate arbitrary rotational degrees of freedom.

### Derived Interface
An interface structure generated from a prototype with specific strain partition (α) and registry shift parameters. Stored in workspace with provenance links to parent prototype.

### Interface
An atomistic structure representing two slabs joined together with defined separation along the interface normal. Includes both materials, their atomic positions, and interface geometry.

### Miller Index
Three integers (h k l) specifying a crystallographic plane. Common surfaces: (100), (110), (111). Higher indices like (210) indicate stepped or high-index surfaces.

### Prototype
A candidate commensurate interface geometry from a pair of slabs and an in-plane supercell match. Represents a geometrically compatible configuration before strain partition optimization.

### Registry
The in-plane translation (a, b) between two slabs at the interface. Different registry shifts result in different atomic alignments. Often optimized via Monte Carlo search.

### Slab
A finite-thickness cut of a bulk crystal exposing a surface. Has periodic boundary conditions in-plane (x, y) and vacuum spacing in perpendicular direction (z). Specified by Miller index, thickness (layers), and vacuum spacing.

### Strain Partition
The distribution of lattice mismatch strain between two materials. Parameterized by α ∈ [0,1]: α=0 (all strain on B), α=0.5 (symmetric), α=1 (all strain on A). CALM uses geodesic interpolation on SPD(2).

### Strain State
A parameterization of how two slabs are deformed to become commensurate. Includes deformation gradients (F_A, F_B), strain tensors, and target cell basis.

### UID (Unique Identifier)
A deterministic, content-derived identifier for persisted entities. Format: `tag_hash` (e.g., `b_a1b2c3d4` for bulk). Enables reproducible, content-addressable storage.

### Workspace
A persistent project directory containing SQLite database (records) and artifact directory (plots, logs, structures). Created via `open_workspace(root)`.

---

## Mathematical & Geometric Terms

### Cholesky Factorization
Decomposition of SPD matrix $G$ into $G = X^T \cdot X$ where $X$ is upper-triangular with positive diagonal. CALM uses Cholesky to extract canonical cell basis from Gram matrix.

### Conditioning (Matrix)
Ratio $\kappa = \sigma_{\max} / \sigma_{\min}$ of largest to smallest singular values. Well-conditioned ($\kappa \approx 1$) matrices are numerically stable. CALM gates on $\kappa < \kappa_{\max}$ to reject ill-conditioned supercells.

### Deformation Gradient
2×2 matrix $F$ mapping reference configuration to deformed configuration. For interfaces: $F_A$ maps slab A to target cell, $F_B$ maps slab B to target cell.

### Frobenius Norm
Matrix norm $\|A\|_F = \sqrt{\Sigma a_{ij}^2}$. Used for measuring strain magnitudes. For strain tensor $E$: $\|E\|_F = \sqrt{\epsilon_1^2 + \epsilon_2^2}$.

### Geodesic
Shortest path between two points on a curved space (manifold). CALM uses geodesics on SPD(2) manifold for strain partitioning, ensuring affine-invariant interpolation.

### Gram Matrix
$G = S^T \cdot S$ where $S$ is a basis matrix (columns are lattice vectors). Encodes all geometric information (lengths, angles) in coordinate-independent form.

### Hencky Strain
Logarithmic strain tensor $H = \log(M)$ where $M$ is relative metric. Factor 1/2 convention: $E = (1/2)H$. Hencky strain is natural for large deformations.

### HNF (Hermite Normal Form)
Canonical form for integer matrices: $H = \begin{bmatrix} a & b \\ 0 & c \end{bmatrix}$ with $a>0$, $c>0$, $0 \leq b < a$. Used for supercell enumeration. Each HNF with $\det(H)=k$ corresponds to a $k$-fold supercell.

### Niggli Reduction
Algorithm to find shortest, most orthogonal basis for a lattice. Conditions: $\|a\| \leq \|b\|$, $|a \cdot b| \leq (1/2)\|a\|^2$. CALM uses 2D Niggli reduction for surface lattices.

### Pareto Front
Set of non-dominated solutions in multi-objective optimization. For interfaces: minimize both cell strain (d_cell) and interface size (n_atoms). No solution is better in all objectives.

### Point Group
Symmetry operations (rotations, reflections) leaving a crystal unchanged. CALM uses point groups to identify equivalent supercell variants and eliminate duplicates.

### Principal Strains
Eigenvalues $\epsilon_1$, $\epsilon_2$ of strain tensor $E$. Represent maximum/minimum stretching along principal directions. CALM computes from Hencky strain: $\epsilon_i = (1/2) \ln(\lambda_i)$.

### SNF (Smith Normal Form)
Canonical form for integer matrices: $D = \begin{bmatrix} d_1 & 0 \\ 0 & d_2 \end{bmatrix}$ with $d_1 | d_2$. Invariants $d_1$, $d_2$ used for refinement pruning. True 2D refinement requires $d_1>1$ AND $d_2>1$.

### SPD(2) Manifold
Space of 2×2 symmetric positive-definite matrices, forming a Riemannian manifold. Gram matrices live on SPD(2). CALM uses SPD(2) geometry for affine-invariant strain metrics.

### Unimodular Matrix
Integer matrix with determinant ±1. Represents a basis change that preserves lattice. Used in HNF enumeration and canonical transformations.

---

## Interface Matching Terms

### Area Band
Range of acceptable supercell area ratios for matching. Filter: $|\ln(A_A/A_B)| \leq \tau$. Reduces search space by eliminating gross area mismatches.

### Conditioning Gate
Filter rejecting ill-conditioned supercells: $\kappa(S) > \kappa_{\max}$. Prevents numerical instability in downstream strain calculations.

### d_cell
Affine-invariant strain metric: $d_{\text{cell}} = 2\|\log(G_A^{-1/2} \cdot G_B \cdot G_A^{-1/2})\|_F$. Coordinate-independent measure of lattice mismatch.

### d_size
Interface size penalty based on total atom count $N_{\text{tot}}$: $d_{\text{size}} = (N_{\text{tot}} - N_{\text{target}})^2$. Used in match scoring to prefer smaller interfaces.

### Key (Point Group)
Canonical HNF under point group symmetry: key_pg = min_{P ∈ PG} HNF(P @ N). Used to identify and eliminate symmetry-equivalent supercell variants.

### Match Score
Weighted combination: $J = w \cdot (d_{\text{cell}}/d_{\text{cell,max}}) + (1-w) \cdot (d_{\text{size}}/d_{\text{size,max}})$. Lower is better. Default $w=0.7$ emphasizes strain over size.

### Refinement
Candidate B refines candidate A if B's supercells are integer multiples of A's supercells on both sides. CALM prunes refinements using SNF invariants.

### Supercell
$k$-fold enlargement of primitive cell: $S' = S \cdot H$ where $\det(H) = k$. CALM enumerates all HNF matrices up to $k_{\max}$ for each surface.

---

## Workspace & Database Terms

### Artifact
File-based output (plot, log, structure, JSON) stored in workspace artifact directory. Each artifact has URI, category, and provenance links.

### Edge
Provenance relationship between entities. Types: "derived_from", "computed_with", "optimized_from". Stored in edges table, queryable via workspace API.

### Enrichment
Computation of derived properties (area, volume, atom counts) from database records. Enriched queries return records with additional computed fields.

### Facade
Organizational pattern grouping related methods. CALM workspace uses facades: query, mutations, enrichment, artifacts, visualization, export.

### Followup
Analysis performed on existing prototype (strain partition scan, registry search). Stored as run with results table linking back to parent prototype.

### ID (Short)
Abbreviated identifier for display: `b_a1b2c3d4`. First tag letter indicates type (b=bulk, s=slab, p=prototype, i=interface, r=run).

### Payload
JSON blob storing flexible metadata. Used for calculator specs, match diagnostics, analysis parameters, etc. Schemaless for extensibility.

### Provenance
Chain of relationships tracking how results were generated. Every entity links to inputs, enabling reproducibility and debugging.

### Record
Database row representing an entity (bulk, slab, prototype, etc.). Contains UID, timestamps, foreign keys, and payload.

### Run
Computational task with status tracking. Types: prototype_search, strain_partition_scan, registry_search. Has status: queued, running, done, failed.

### Tag
Type prefix in UID: b_ (bulk), s_ (slab), p_ (prototype), i_ (interface), r_ (run), a_ (artifact). Enables type identification from ID alone.

---

## Crystallography Terms

### Conventional Cell
Standard unit cell choice for a space group. May contain multiple primitive cells. Used for consistent structure descriptions.

### FCC (Face-Centered Cubic)
Lattice with atoms at cube corners and face centers. Examples: Al, Cu, Au. Space group Fm-3m.

### Motif-Compatible Lattice
Surface lattice enlarged to tile evenly with slab's atomic motif. Prevents fractional atoms in supercells. CALM automatically promotes to motif-compatible lattice.

### Non-Polar Surface
Surface with symmetric stacking sequence (no net dipole). Example: FCC(111). Single termination.

### Polar Surface
Surface with asymmetric ionic stacking (net dipole perpendicular). Example: LiF(100). Multiple terminations possible.

### Primitive Cell
Smallest repeating unit. Contains one lattice point. CALM extracts primitive cells before surface analysis.

### Rock Salt Structure
NaCl-type structure. Two interpenetrating FCC lattices. Space group Fm-3m. Examples: LiF, MgO, NaCl.

### Space Group
Complete set of symmetry operations (including translations). Determines crystal structure classification. CALM uses spglib for space group detection.

### Superlattice
Larger periodic structure from multiple unit cells. In CALM: surface supercells for interface matching.

### Surface Pointgroup
2D point group of surface (rotations/reflections in plane). Subset of bulk point group. Used for orbit canonicalization.

### Termination
Choice of which atomic layer appears at surface. Matters for polar surfaces (cation-terminated vs anion-terminated).

---

## Algorithm Terms

### Best-by-Key
Deduplication strategy: group by canonical key, keep best-conditioned representative per key. Eliminates symmetry-equivalent variants.

### Enumerate
Systematically generate all possibilities meeting constraints. CALM enumerates: HNF matrices (supercells), terminations (polar surfaces), matches (strain-filtered pairs).

### Geodesic Interpolation
Interpolation along shortest path on manifold. For SPD(2): $G(\alpha) = G_A^{1/2} \cdot (G_A^{-1/2} \cdot G_B \cdot G_A^{-1/2})^\alpha \cdot G_A^{1/2}$. Affine-invariant.

### Monte Carlo Search
Randomized optimization sampling state space. CALM uses for registry optimization: sample translations, evaluate energies, accept/reject via Metropolis criterion.

### Orbit
Set of equivalent configurations under symmetry group. Example: supercells related by point group rotations. CALM canonicalizes to min HNF per orbit.

### Pareto Filtering
Elimination of dominated solutions. Keep only non-dominated points. For 2D: scan sorted list, drop points above/right of frontier.

### Pruning
Elimination of redundant candidates. CALM prunes: (1) metric duplicates (optional), (2) simultaneous refinements (SNF-based).

### Strict Simultaneous Refinement
Candidate where both supercells are strict integer refinements with same ratio and SNF indicates true 2D refinement ($d_1>1$, $d_2>1$).

---

## File & IO Terms

### POSCAR
VASP structure file format. Contains lattice vectors, atomic positions, species. CALM exports to POSCAR for DFT/visualization compatibility.

### SQLite
Embedded SQL database. CALM uses SQLite for workspace persistence. Single file (`calm.sqlite`), no server required.

### URI (Uniform Resource Identifier)
Path to artifact relative to workspace root. Format: `out/runs/{run_id}/{category}/{filename}`. Resolvable via workspace API.

---

## Performance & Numerical Terms

### Caching
Storing computed results for reuse. CALM caches: inverse square roots (strain computation), point group orbits (canonicalization), divisors (SNF pruning).

### Determinism
Property that same inputs always produce same outputs. CALM is deterministic: uses exact integer arithmetic, canonical orderings, no floating-point comparisons in critical paths.

### Fast 2×2 Kernels
Specialized functions for 2×2 matrix operations. CALM uses fast kernels (det2, inv2, sym2, geodesic_spd) for 26× speedup over generic NumPy.

### Numerical Stability
Resistance to round-off errors. CALM ensures stability via: Cholesky (SPD square roots), symmetric eigensolvers (strain computation), conditioning gates.

### Tolerance (eps)
Numerical threshold for equality checks. CALM uses configurable tolerances: niggli_eps (reduction), metric_scale (deduplication).

---

## Related Concepts

**See Also:**
- [Concepts: UIDs and Records](concepts/uids_and_records.md)
- [Concepts: Workspace Layout](concepts/project_layout.md)
- [Algorithms: Strain Partitioning](mathematics/algorithms/geodesic-strain-partitioning.md)
- [Algorithms: Overview](mathematics/algorithms/README.md)
