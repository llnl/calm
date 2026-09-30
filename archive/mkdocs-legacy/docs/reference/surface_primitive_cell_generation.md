# Surface motif-compatible primitive cell generation

This document describes the **surface motif-compatible primitive cell reduction** algorithm implemented in CALM.

The implementation lives in the modern surface-primitive pipeline:

- `calm.slab.surface_primitive_cell.compute_surface_primitive_cell` (public helper)
- `calm.slab.surface_primitive_cell.surface_primitive_slab` (slab-level reducer; wraps the backend)
- `calm.symmetry.surface_primitive._surface_primitive_slab_impl` (backend implementation; returns `(slab_reduced, info)`)

Supporting helpers used by the backend include:

- `calm.symmetry.surface_primitive.primitive_surface_vectors_from_slab` (bulk→surface lattice extraction)
- `calm.symmetry.surface_primitive.primitive_generators_from_C_snf` (lattice saturation helpers)
- `calm.symmetry.reduction.niggli_reduce_2d_columns` and related integer/unimodular utilities

For a user-facing overview (when to call this, expected outputs, and fallback policy), see
[Primitive surface cells](../primitive_surface_cells.md).

The goal is to take a slab supercell and produce a **reduced slab** with the smallest in-plane cell that still reproduces the observed **decorated surface motif** under periodic repetition.

“Motif-compatible” is essential: pure lattice reduction can generate an in-plane lattice cell that is *geometrically* primitive but too small to represent the *atomic motif* (e.g., centered lattices, multi-site motifs).

## Inputs and output

**Input (conceptual):**

- A slab supercell with lattice vectors $\mathbf{a}_S,\mathbf{b}_S,\mathbf{c}_S$ and atomic positions $\{\mathbf{r}_i\}$.
- The bulk primitive lattice basis $\mathbf{P}$ expressed in the **same Cartesian frame** as the slab.

**Output:**

- A reduced slab with in-plane vectors $\mathbf{a}_P,\mathbf{b}_P$ and the *same* surface motif.
- Integer matrices and metadata sufficient to reproduce the reduction deterministically.

## Conventions

### Column-vector lattice convention

In the equations below, we use a **column convention** for lattice matrices:

$$
\mathbf{A}_S = [\,\mathbf{a}_S\ \mathbf{b}_S\ \mathbf{c}_S\,] \in \mathbb{R}^{3\times 3}
$$

Atomic Cartesian coordinates and fractional coordinates are related by:

$$
\mathbf{r} = \mathbf{A}_S\,\mathbf{f},\qquad \mathbf{f} = \mathbf{A}_S^{-1}\,\mathbf{r}.
$$

Define the slab in-plane basis:

$$
\mathbf{S} = [\,\mathbf{a}_S\ \mathbf{b}_S\,] \in \mathbb{R}^{3\times 2}.
$$

The bulk primitive lattice basis is:

$$
\mathbf{P} = [\,\mathbf{p}_1\ \mathbf{p}_2\ \mathbf{p}_3\,] \in \mathbb{R}^{3\times 3}.
$$

## Algorithm

### Step 1 — Express the slab in-plane lattice in the bulk primitive basis

Compute the real-valued coefficient matrix:

$$
\tilde{\mathbf{C}} = \mathbf{P}^{-1}\,\mathbf{S} \in \mathbb{R}^{3\times 2}.
$$

Because the slab is (by construction) commensurate with the bulk primitive lattice, $\tilde{\mathbf{C}}$ should be close to integers. Round within tolerance:

$$
\mathbf{C} = \operatorname{round}(\tilde{\mathbf{C}}) \in \mathbb{Z}^{3\times 2},
$$

so that:

$$
\mathbf{S} = \mathbf{P}\,\mathbf{C}.
$$

**What this achieves:** $\mathbf{C}$ encodes how the slab’s surface lattice vectors $\mathbf{a}_S,\mathbf{b}_S$ are built as integer combinations of bulk primitive vectors.

### Step 2 — Compute the *bulk-induced* primitive surface lattice (SNF saturation)

The integer columns of $\mathbf{C}$ generate a rank‑2 sublattice of $\mathbb{Z}^3$:

$$
\mathcal{L} = \{\,\mathbf{C}\,\mathbf{n}\;|\;\mathbf{n}\in\mathbb{Z}^2\,\} \subset \mathbb{Z}^3.
$$

This sublattice may not be **saturated**; i.e., it may miss smaller integer generators compatible with the same plane. CALM computes a saturated generator $\mathbf{K}\in\mathbb{Z}^{3\times 2}$ using the Smith normal form (SNF) of $\mathbf{C}$.

Conceptually, SNF gives unimodular matrices $\mathbf{U}\in GL(3,\mathbb{Z})$, $\mathbf{V}\in GL(2,\mathbb{Z})$ and invariants $d_1\mid d_2$ such that:

$$
\mathbf{U}\,\mathbf{C}\,\mathbf{V} =
\begin{bmatrix}
 d_1 & 0 \\
 0 & d_2 \\
 0 & 0
\end{bmatrix}.
$$

From this, CALM constructs $\mathbf{K}$ whose columns generate the **saturated** rank‑2 lattice associated with the surface intersection.

Define the candidate surface primitive basis in Cartesian space:

$$
\mathbf{P}_{\parallel} = \mathbf{P}\,\mathbf{K} \in \mathbb{R}^{3\times 2}.
$$

**What this achieves:** $\mathbf{P}_{\parallel}$ is the smallest-area lattice cell implied by the bulk primitive lattice and slab orientation (a geometric/lattice primitive cell).

### Step 3 — Compute the slab→primitive integer relation

Because $\mathbf{P}_{\parallel}$ and $\mathbf{S}$ describe commensurate in-plane lattices, there exists $\mathbf{H}\in\mathbb{Z}^{2\times 2}$ such that:

$$
\mathbf{S} = \mathbf{P}_{\parallel}\,\mathbf{H}.
$$

Define the multiplicity:

$$
 m = |\det\mathbf{H}|.
$$

Interpretation: the slab in-plane cell contains $m$ copies of the candidate primitive surface lattice cell.

**What this achieves:** the reduction problem is now discrete: $\mathbf{H}$ specifies how many primitive cells tile the slab supercell.

### Step 4 — Motif compatibility test (decorated lattice check)

Even if $\mathbf{P}_{\parallel}$ is a primitive **lattice**, it can be too small for the **motif** (atomic basis). CALM checks motif compatibility by folding atoms into the candidate cell and verifying multiplicities.

1. Form a slab copy with in-plane cell $\mathbf{P}_{\parallel}$ and unchanged $\mathbf{c}_S$.
2. Compute fractional coordinates $\mathbf{f}_i$ in that cell.
3. **Wrap only x/y** into $[0,1)$:

   $$
   f_{ix} \leftarrow f_{ix} - \lfloor f_{ix} \rfloor,\qquad
   f_{iy} \leftarrow f_{iy} - \lfloor f_{iy} \rfloor.
   $$

   (z is not wrapped).

4. Assign a “motif key” using discretization tolerances $\delta_{xy}$ and $\delta_z$:

   $$
   k_i = \Big(
   Z_i,\
   \operatorname{round}(f_{ix}/\delta_{xy}),\
   \operatorname{round}(f_{iy}/\delta_{xy}),\
   \operatorname{round}(f_{iz}/\delta_z)
   \Big).
   $$

5. Motif compatibility requires:

   - the number of unique keys is $N/m$, and
   - each unique key occurs exactly $m$ times.

**What this achieves:** this prevents “over-reduction” that would collapse distinct motif sites.

### Step 5 — If needed, promote to the smallest motif-compatible superlattice

If the motif test fails, CALM promotes $\mathbf{P}_{\parallel}$ to a minimal-area superlattice that still fits the slab’s in-plane cell and passes the motif test.

Search over 2×2 integer matrices $\mathbf{M}$ in **Hermite normal form (HNF)** with determinant $d$, where $d$ divides $m$:

$$
\mathbf{P}'_{\parallel} = \mathbf{P}_{\parallel}\,\mathbf{M},\qquad |\det\mathbf{M}| = d.
$$

For each candidate $\mathbf{P}'_{\parallel}$, compute the corresponding $\mathbf{H}'$ satisfying:

$$
\mathbf{S} = \mathbf{P}'_{\parallel}\,\mathbf{H}'.
$$

The search is ordered by increasing $d$, so the first passing candidate yields the smallest-area motif-compatible cell.

**What this achieves:** the final cell is minimal with respect to *both* lattice commensurability and motif reproduction.

### Step 6 — Canonicalize the in-plane basis (2D reduction)

To avoid arbitrary basis choices, CALM applies a unimodular change of basis $\mathbf{V}\in GL(2,\mathbb{Z})$:

$$
\mathbf{P}^{\mathrm{red}}_{\parallel} = \mathbf{P}'_{\parallel}\,\mathbf{V},\qquad |\det\mathbf{V}| = 1.
$$

This is a deterministic Gauss/Niggli-style reduction that produces shorter/less-skewed basis vectors.

**What this achieves:** a canonical-ish representation of the same in-plane lattice.

### Step 7 — Fold atoms into the reduced cell and deduplicate

Construct the reduced slab cell:

$$
\mathbf{A}_P = [\,\mathbf{P}^{\mathrm{red}}_{\parallel}\ \mathbf{c}_S\,].
$$

Compute fractional coordinates in $\mathbf{A}_P$, wrap x/y into $[0,1)$, then **deduplicate** atoms using the motif keys $k_i$ above.

Finally, verify the atom count:

$$
N_P = \frac{N}{m}.
$$

**What this achieves:** an actual primitive motif cell (unique basis) rather than merely a smaller lattice.

### Step 8 — Optional in-plane rotation to a canonical orientation

CALM may rotate the reduced cell about $\mathbf{c}_S$ so that $\mathbf{a}_P$ aligns with the +x axis. If $\mathbf{a}_P = (a_x,a_y,a_z)$:

$$
\theta = \operatorname{atan2}(a_y,a_x).
$$

**What this achieves:** deterministic orientation (useful for hashing and canonical IDs).

## Implementation invariants (what to verify)

If you are validating correctness of an implementation, the following checks should hold:

1. **Near-integer commensurability:** $\mathbf{P}^{-1}\mathbf{S}$ rounds cleanly to $\mathbf{C}$ within tolerance.
2. **Exact integer relation:** $\mathbf{S} = \mathbf{P}_{\parallel}\mathbf{H}$ with $\mathbf{H}\in\mathbb{Z}^{2\times2}$.
3. **Multiplicity consistency:** $m = |\det\mathbf{H}|$ equals the expected in-plane area ratio.
4. **Motif multiplicity:** folding into the primitive candidate cell yields exactly $m$ repeats of every motif site.
5. **Atom count reduction:** final reduced slab contains $N/m$ atoms.
6. **Lattice equivalence under reduction:** applying $\mathbf{V}\in GL(2,\mathbb{Z})$ changes only the basis, not the lattice.
