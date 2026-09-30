# Monte Carlo registry alignment

## Purpose

CALM's registry-search algorithm explores relative in-plane translations of two already constructed interface slabs, with an optional out-of-plane gap variable. The algorithm is used after an interface candidate or prototype has fixed the crystallographic match, strain state, and stacking order. Registry search therefore does not create a new lattice match. It searches the residual configurational degree of freedom inside a fixed interface cell and returns the lowest-scoring registry encountered under a user-provided objective.

The implemented kernel is intentionally lightweight. It is a stochastic optimizer over a two-dimensional torus, optionally augmented by one bounded scalar coordinate. The caller supplies the score or energy function, so the mathematical contract is independent of a particular interatomic potential, calculator backend, or relaxation protocol.

## Ontology mapping

| Layer | Object or representation | Role |
| --- | --- | --- |
| Scientific object | Built Interface Structure | Object whose relative slab registry is varied |
| Scientific morphism | Evaluate / registry search follow-up | Evaluates candidate registries under a scalar objective |
| Representation space | Fractional in-plane registry coordinates | Translation state \(t=(t_1,t_2)\in [0,1)^2\) |
| Optional representation coordinate | Gap or z-padding coordinate | Scalar separation variable \(z\) |
| Output representation | RegistrySearchResult | Best translation, score, optional z-padding, acceptance count, trace, metadata |
| Persistence projection | Follow-up result payloads | Stores best registry shifts and trace summaries for downstream derived interfaces |

The core Monte Carlo kernel is a representation-level optimizer. It does not itself decide scientific admissibility. A workflow may later use the returned registry as the input to a scientific construction or evaluation morphism.

## Mathematical problem

Let \(B=(b_1,b_2)\) be the in-plane basis of the fixed interface cell. A registry is a fractional translation

\[
t=(t_1,t_2) \in \mathbb{T}^2 = \mathbb{R}^2 / \mathbb{Z}^2,
\]

with Cartesian displacement

\[
\Delta r(t)=t_1 b_1+t_2 b_2.
\]

If z-padding is enabled, the search space becomes

\[
\Omega = \mathbb{T}^2 \times [z_{\min},z_{\max}],
\]

or \(\mathbb{T}^2 \times [0,\infty)\) when no finite upper bound is provided. The objective is a scalar function

\[
E: \Omega \rightarrow \mathbb{R}\cup\{+\infty\},
\]

where lower values are preferred. In practice \(E\) may be an interatomic energy, a surrogate score, or a workflow-specific penalty. The algorithm seeks

\[
(t^*,z^*) \approx \operatorname*{argmin}_{(t,z)\in\Omega} E(t,z).
\]

Because the objective is supplied externally and may be nonconvex, discontinuous, noisy, calculator-dependent, or only partially defined, the implemented method provides a heuristic stochastic search rather than a global optimality guarantee.

## State conventions

### In-plane translation

The in-plane state is always stored in reduced fractional coordinates. After each translation proposal, CALM wraps the state into the unit square:

\[
\operatorname{wrap}(x)=x-\lfloor x\rfloor.
\]

This implements the quotient topology of the translation torus and ensures that registries differing by an integer lattice translation are represented by the same fractional state.

### Optional z-padding

When enabled, the scalar coordinate is clamped to the configured interval:

\[
\operatorname{clamp}(z)=\min(\max(z,z_{\min}),z_{\max}),
\]

with only the lower bound applied when no upper bound is provided. If `z_bounds` is supplied and `z_step_scale` is zero, the implementation chooses an effective proposal width equal to ten percent of the bounds width. This is an implementation convention: finite bounds are interpreted as a request to explore the gap coordinate rather than merely clamp it.

## Monte Carlo algorithm

Inputs:

- scalar objective `energy_fn`;
- number of proposals \(N\);
- translation proposal scale \(\sigma_t\);
- scalar or callable temperature \(T_k\);
- optional random seed;
- optional initial state \((t_0,z_0)\);
- optional z proposal scale \(\sigma_z\), bounds, and move probability;
- trace flag.

Workflow:

1. Initialize a NumPy random generator from the seed.
2. Initialize the fractional translation from `x0` or uniformly from \([0,1)^2\).
3. Enable z-padding if `z0`, `z_bounds`, or a positive z proposal scale is supplied.
4. Evaluate the initial score.
5. For each proposal step \(k=1,\ldots,N\):
   1. Select either a z move or an in-plane translation move.
   2. For a translation move, draw \(\eta_t\sim\mathcal{N}(0,\sigma_t^2I_2)\) and set
      \[
      t'=\operatorname{wrap}(t+\eta_t).
      \]
   3. For a z move, draw \(\eta_z\sim\mathcal{N}(0,
      \sigma_z^2)\) and set
      \[
      z'=\operatorname{clamp}(z+
      \eta_z).
      \]
   4. Evaluate \(E'=E(t',z')\).
   5. Reject non-finite scores.
   6. Otherwise accept downhill moves and accept uphill moves with Metropolis probability
      \[
      p=\exp\left(-\frac{E'-E}{T_k}\right)
      \]
      when \(T_k>0\).
   7. Update the incumbent state if the proposal is accepted.
   8. Update the best-seen state if the accepted score is strictly lower.
   9. Optionally append `(step, current_score, best_score)` to the trace.
6. Return the best-seen translation, best score, accepted count, optional z-padding, trace, and metadata.

## Geometry update used by project workflows

The pure Monte Carlo kernel only sees a state and an objective. Project-level workflows must convert a proposed state into an interface geometry before evaluating the objective. CALM factors this geometry update into a dependency-light helper.

Given reference positions \(R_0\), upper-slab atom indices \(U\), in-plane vectors \(v_1,v_2\), a normal direction \(u_3\), reference cell length \(L_3\), reference gap \(g_0\), candidate translation \(t\), reference translation \(t_0\), and candidate gap \(z\), the geometry proposal computes the minimum-image fractional displacement

\[
\delta t = (t-t_0+1/2) \bmod 1 - 1/2.
\]

The Cartesian in-plane displacement is

\[
d = \delta t_1 v_1 + \delta t_2 v_2,
\]

then projected perpendicular to the normalized interface normal to avoid numerical drift:

\[
d_\perp = d - (d\cdot \hat u_3)\hat u_3.
\]

The z move is

\[
\delta z = z-g_0.
\]

Upper-slab atom positions are updated by

\[
R_i'=R_i+d_\perp+\delta z\hat u_3, \qquad i\in U,
\]

and the third cell vector is updated to

\[
c'=(L_3+2\delta z)\hat u_3.
\]

The proposed geometry is rejected if the resulting cell length is not positive.

## Correctness properties

The implemented algorithm has the following correctness properties relative to its stochastic contract:

- **Torus invariance:** in-plane states are always wrapped into \([0,1)^2\), so integer translation offsets do not change the represented registry.
- **Seed reproducibility:** for deterministic objectives and fixed inputs, a fixed seed determines the proposal sequence and result.
- **Finite-score admissibility:** non-finite proposal scores are never accepted.
- **Best-seen monotonicity:** the reported best score is non-increasing along the accepted trajectory.
- **Temperature semantics:** at zero temperature, uphill finite moves are rejected; at positive temperature, uphill moves are accepted with the implemented Metropolis probability.
- **z-bound preservation:** when finite z bounds are configured, all evaluated z states remain inside the configured interval.
- **Geometry nonmutation:** the dependency-light geometry proposal returns copies and does not mutate reference positions.

These are algorithmic guarantees, not guarantees of global optimization.

## Limitations and assumptions

Registry search assumes that the interface lattice, slab identities, atom labeling, and strain state have already been fixed. The search does not enumerate alternative crystallographic matches, alternative surfaces, atom permutations, reconstructions, or chemical substitutions.

The objective function is treated as a black box. CALM therefore cannot prove smoothness, convexity, stationarity, or convergence to a global optimum. The Monte Carlo trajectory should be interpreted as a heuristic search whose reliability depends on the objective landscape, proposal scales, temperature schedule, number of steps, and initialization.

The z-padding coordinate is a simplified scalar geometry control. It changes the upper-slab position and the third cell vector according to the implemented project-layer convention; it does not replace full structural relaxation.

## Complexity

For \(N\) Monte Carlo proposals and objective cost \(C_E\), the core complexity is

\[
O(N C_E),
\]

with \(O(N)\) memory only when trace retention is enabled and \(O(1)\) memory otherwise. Geometry-proposal overhead is linear in the number of atoms moved, but in realistic workflows the objective evaluation usually dominates.

## Implementation mapping

| Concept | Implementation owner |
| --- | --- |
| Monte Carlo kernel | `calm.interface.registry_search.monte_carlo_registry_search` |
| Result object | `calm.interface.registry_search.RegistrySearchResult` |
| Translation wrapping | `calm.interface.registry_search._wrap_unit` |
| z clamping | `calm.interface.registry_search._clamp` |
| flexible objective dispatch | `calm.interface.registry_search._call_energy_fn` |
| registry geometry proposal | `calm.interface.registry_search_geometry.propose_registry_search_geometry` |
| workflow runner | `calm.interface.ops.registry_search_runner.run_registry_search_monte_carlo_on_interface` |
| user configuration | `calm.interface.config.RegistrySearchConfig` |
| project orchestration | `calm.project.application.followups.registry_search.RegistrySearchOrchestrator` |
| workspace facade | `calm.project.ux.workspace.Workspace.start_registry_search` |

## Verification mapping

Current verification should cover at least:

- deterministic reproducibility for fixed seed and objective;
- translation wrapping into the unit torus;
- zero-temperature and finite-temperature acceptance behavior;
- non-finite proposal rejection;
- optional z-padding enablement, clamping, and automatic effective step scale under finite bounds;
- geometry-proposal minimum-image translation and nonmutation behavior;
- workflow extraction of best translation and z-padding into derived-interface specifications.

The traceability audit should record any missing tests explicitly. In particular, convergence-style tests should avoid asserting global optimality for stochastic search. The robust contract is reproducibility and preservation of state-space invariants.

## References

The stochastic acceptance rule follows the Metropolis Monte Carlo convention. Registry alignment is formulated here as torus optimization over fractional interface-cell translations rather than as a separate crystallographic matching problem.
