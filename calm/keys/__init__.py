"""Canonical identity and lattice-key implementation modules.

Current callers import the owning module directly:

- :mod:`calm.keys.uid` for deterministic scientific and workflow identifiers;
- :mod:`calm.keys.hnf` for exact one-sided HNF orbit witnesses;
- :mod:`calm.keys._canonical_v2` for type-tagged persisted identity bytes.

The package root intentionally provides no duplicate function re-exports.
"""
