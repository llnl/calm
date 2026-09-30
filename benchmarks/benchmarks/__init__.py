"""Benchmark harness for CALM and external lattice-matching tools.

Use :mod:`benchmarks.run_full_suite` for the complete repository benchmark and
qualification workflow. Synthetic cross-tool comparison uses
:mod:`benchmarks.run_calm`; exact-key and audit qualification use
:mod:`benchmarks.run_coupled_qualification`; and the current project-centered
public workflow is exercised by
:mod:`benchmarks.run_public_api_qualification`. External tools such as pymatgen
ZSL and the historical SlabGen distribution remain explicitly named and are
never presented as CALM results. Claim-oriented schemas and provenance are
initialized separately through :mod:`benchmarks.run_claim_suite`; that scaffold
does not yet execute scientific qualification. Raw pymatgen ZSL source evidence
is captured through :mod:`benchmarks.run_zsl_source_capture` and classified
later through the explicitly separate :mod:`benchmarks.run_zsl_projection`
stage.
"""
