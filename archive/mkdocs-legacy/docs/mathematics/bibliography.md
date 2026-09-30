# Bibliography

This page will collect literature and technical references used by the mathematical and algorithmic specification.

Initial reference categories:

- crystallographic lattices and cell reduction;
- surface and slab construction;
- lattice matching and interface construction;
- strain theory and deformation metrics;
- structure equivalence and deduplication;
- stochastic/Monte Carlo registry optimization.

## Surface primitive cell generation

The first algorithm specification relies on standard results from crystallographic reciprocal-lattice theory, integer lattice kernels, Smith normal form, Hermite normal form, and two-dimensional lattice reduction. Bibliographic entries should be expanded as the reference manual matures; for now this page records the reference categories used by the motif-compatible primitive surface-cell specification.

## Deduplication and equivalence

- Cohen, H. *A Course in Computational Algebraic Number Theory*. Springer, 1993. Background on Hermite normal forms and integer-lattice canonical representatives.
- Pymatgen and ASE documentation are useful implementation-context references for structure matching, periodic distances, and crystallographic representation conventions, but CALM's normative behavior is defined by the specifications in this directory and by its tests.

## Monte Carlo and registry optimization

- Metropolis, N.; Rosenbluth, A. W.; Rosenbluth, M. N.; Teller, A. H.; Teller, E. Equation of State Calculations by Fast Computing Machines. *J. Chem. Phys.* **1953**, 21, 1087-1092.
- CALM implementation reference: `calm.interface.registry_search`, `calm.interface.registry_search_geometry`, and `calm.interface.ops.registry_search_runner`.

## Interface construction and atomistic assembly

- CALM implementation references: `calm.interface.pipeline.build_interface`, `calm.interface._build_kernel.build_interface_atoms`, and `calm.ase_adapter.make_supercell_col`.
- ASE supercell construction conventions are relevant for understanding the row/column representation adapter used by CALM.

## Persistence, projection, and reporting

- CALM implementation references: `calm.project.infrastructure.db.tables`, `calm.public.sidecar`, `calm.public.datasets`, `calm.public.dataset_collections`, and `calm.reporting`.
- Database normalization and schema-versioning references should be expanded if the persistence specification becomes a formal migration design document.
