# Persistence, public projection, and reporting

## Purpose

This specification documents CALM's persistence and reporting projections as representation morphisms from scientific workflow objects into durable database rows, JSON sidecar records, tabular dataset manifests, and human-facing report tables. These operations do not create new scientific objects by changing geometry or energetics. They preserve selected identity and provenance information while intentionally discarding implementation details that are not part of the public projection contract.

## Ontology mapping

| Role | Object or representation |
| --- | --- |
| Input scientific objects | crystals, slabs, interface candidates/prototypes, built interface structures, evaluation results, datasets |
| Output representations | workspace database rows, artifact records, public sidecar rows, dataset manifests, query collections, report tables |
| Ontology morphism | Persist / Project |
| Representation spaces | persistence space, JSON projection space, CSV/table space, report space |
| Primary owners | `calm.project.application.*`, `calm.project.infrastructure.db.*`, `calm.public.*`, `calm.reporting` |

The projection is many-to-one in general: a public row is not required to contain enough information to reconstruct the full scientific object. Reconstructability belongs to the durable workspace database and artifact stores, while public rows and reports are query and communication projections.

## Mathematical formulation

Let `O` be a scientific object with identity `id(O)`, provenance `prov(O)`, and representation payload `repr(O)`. A persistence projection is a map

```text
P: O -> (uid, payload, metadata)
```

where `uid` is stable under representation-preserving conversions, `payload` stores the reconstruction or summary data required by the owning persistence layer, and `metadata` stores queryable or human-facing fields. A public projection is a lossy map

```text
Q: O -> row(O)
```

whose correctness criterion is not invertibility, but preservation of declared public identity fields and semantic columns. A report projection is another lossy map

```text
R: collection(O_i) -> table(rows_i)
```

that orders, formats, and selects fields for user interpretation.

## Identity and provenance contracts

CALM separates multiple identity layers:

- durable full UIDs, such as workspace `uid_full` values;
- short IDs for interactive display;
- candidate display identifiers such as `candidate_id`;
- scientific/provenance identifiers such as `candidate_uid`, `prototype_uid`, `build_uid`, and run/artifact UIDs;
- public dataset row indices and generated structure names.

A projection is valid only if it does not silently conflate these layers. A display ID may be useful for tables, but it is not a substitute for provenance identity. Conversely, public rows should not expose private helper objects or internal prototypes unless the public contract explicitly includes them.

## Durable workspace projection

The workspace database uses explicit tables for schema versioning, bulks, calculators, slabs, runs, artifacts, prototypes, derived interfaces, and follow-up results. These tables are not mathematical transformations of structure geometry; they are typed persistence coordinates for workflow state.

The durable projection should satisfy:

1. stable UID uniqueness for persisted entities;
2. explicit foreign-key provenance for relationships such as run-to-artifact, prototype-to-slab, and derived-interface-to-prototype;
3. JSON payload fields for reconstruction or detailed metadata;
4. additive schema evolution through versioned database infrastructure.

## Public sidecar projection

The public project facade maintains `calm-public-records.json` as a lightweight reporting index. Its schema version and tables are defined by `calm.public.sidecar`. The current table families are searches, candidates, interfaces, datasets, dataset items, and energies.

The sidecar projection is intentionally separate from the durable workspace database. It supports basic-facing query methods and resilient reopening of public project views, but it is not the authoritative scientific store.

Correctness properties include:

- table values normalize to lists of row mappings;
- unsupported future schema versions are not interpreted as if they were current;
- invalid rows may be dropped or warned about in non-strict recovery mode;
- strict validation rejects invalid public records;
- atomic write semantics prevent partially written public sidecars from becoming the normal outcome.

## Dataset and manifest projection

`InterfaceDataset.to_rows` projects built interface structures into manifest rows. The projection preserves dataset name/index, generated structure name, atom count when available, public candidate identifiers, provenance UIDs, material/surface labels, area, and build settings such as gap and vacuum.

The manifest is a CSV table derived from row dictionaries. It is a communication and export object, not a replacement for the built interface structure or durable provenance record.

## Report projection

`calm.reporting` provides deterministic table helpers for prototype and energy summaries. Reporting helpers extract features from dictionaries, dataclasses, and object attributes while tolerating missing values. Their mathematical role is ordering, selection, and formatting of scalar diagnostics, not recomputation of the scientific quantities themselves.

For prototype summaries, report rows may include match scores, atom counts, affine-invariant strain metrics, ZM-style strain metrics, and derived scalar diagnostics such as a displayed Hencky norm. These fields must be interpreted as projections of already computed candidate/prototype properties.

## Algorithmic workflow

1. A scientific or workflow object is produced by a scientific morphism or application service.
2. The owning service assigns or carries a stable UID and provenance links.
3. Durable persistence writes typed database rows and JSON payloads.
4. Public projection records selected fields in sidecar tables or public collection rows.
5. Dataset projection emits manifest rows and optional structure files.
6. Report projection formats selected scalar fields for display or export.

## Complexity

Persistence and projection are linear in the number of projected rows, aside from database indexing and artifact I/O. Manifest field-name construction is linear in the total number of row keys. Report table formatting is linear in the number of displayed rows times the number of displayed columns.

## Correctness properties

A valid persistence/projection implementation should satisfy:

- identity preservation for declared UID and provenance fields;
- no unintended promotion of private implementation helpers into public APIs;
- schema-version validation for sidecar records;
- stable public row keys unless a compatibility migration is explicitly planned;
- deterministic report rows for the same input collection and requested view;
- graceful optional-dependency behavior for dataframe/plotting/export conveniences.

## Limitations

Public rows and reports are lossy. They should not be used as the sole source for reconstructing scientific objects unless the relevant projection explicitly documents reconstructability. Sidecar records are a public-query convenience and can lag behind durable database expressiveness. CSV manifests also lose type information compared with JSON/database payloads.

## Implementation mapping

| Concept | Implementation owner |
| --- | --- |
| Public sidecar schema and migration | `calm.public.sidecar` |
| Public project facade and queries | `calm.public.project`, `calm.public.project_queries` |
| Dataset row and manifest projection | `calm.public.datasets`, `calm.public.dataset_collections` |
| Energy/dataset/candidate collections | `calm.public.*_collections` |
| Durable database tables | `calm.project.infrastructure.db.tables` |
| Application persistence services | `calm.project.application.*` |
| Report table helpers | `calm.reporting` |

## Verification mapping

Relevant verification includes public API boundary tests, persistence/projection guardrails, candidate identity/projection tests, dataset manifest tests, public sidecar validation tests, and reporting/table tests. Future verification should add an end-to-end canonical workflow assertion that traces a candidate UID/prototype UID/build UID/evaluation UID through persistence, public sidecar projection, dataset manifest projection, and report projection without conflating the identity layers.
