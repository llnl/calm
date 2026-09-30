# Roadmap

This roadmap is a living document. It is intentionally high-level and may change as the API stabilizes.

## Near term

- **Documentation**
  - Publish a rendered **Public API** reference in the docs site (generated from `public_api.md`).
  - Expand the **Quickstart** and add task-focused guides (prototype search, interface build, interface energy).
  - Add an "API stability" policy page (SemVer-like intent; deprecations with clear replacements).

- **Examples and smoke tests**
  - Keep the example scripts in lock-step with the public API via CI smoke tests.
  - Add a small "common pitfalls" section to each example.

## Medium term

- **API reference pages**
  - Add lightweight reference pages for core objects (`Workspace`, records, config dataclasses).
  - Document optional dependencies and extras (calculators, plotting).

- **Compatibility policy**
  - Keep compatibility aliases small and explicit.
  - Prefer clear breakpoints over long-lived shims when the codebase is single-maintainer.

## Long term

- **Workflow ergonomics**
  - Improve orchestration helpers for multi-stage workflows (prototype search → strain scan → registry search).
  - Standardize result objects and printed summaries.

- **Data model and persistence**
  - Document the DB schema at a conceptual level.
