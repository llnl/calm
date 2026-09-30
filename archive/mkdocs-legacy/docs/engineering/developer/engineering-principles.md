# Engineering principles

These principles guide CALM patch work.

## Preserve the green state

Each forward patch should apply cleanly and leave the repository testable. If a patch fails locally, the next patch should repair that failure before expanding scope.

## Prefer explicit public contracts

Basic-facing workflows should be expressed through the public facade and validated with focused tests. If a workflow is not implemented, examples and documentation should say so clearly rather than implying support.

## Remove obsolete compatibility layers

CALM is under active development and has no broad external user base. Breaking changes are acceptable when they simplify the codebase and leave the modern implementation available and tested. Do not preserve thin facades or legacy adapters unless a current test, example, or public contract requires them.

## Keep ownership boundaries clear

- Slab generation belongs to the modern oriented-slab pipeline.
- Public basic workflows belong in `calm.public` and top-level curated exports.
- Advanced/core APIs may remain importable, but they should not be advertised as basic public API unless they are part of the numbered-example contract.
- MLIP integration should be backend-specific and should not force incompatible frameworks into one environment.

## Make process corrections durable

When the collaboration process fails, update `docs/engineering/` rather than relying on memory from a prior chat. Patch format, validation rules, and handoff conventions are repository documentation.
