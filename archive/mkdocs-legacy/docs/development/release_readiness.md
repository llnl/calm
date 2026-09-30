# Development workflow

This page summarizes the recommended development workflow for **calm**, with a focus on practices that keep the codebase testable and releases repeatable.

## Daily development loop

1. Create a topic branch for each logical change set.
2. Keep changes small and reviewable.
3. Run the local quality gates before pushing:

```bash
   pytest -q
   mkdocs build --strict
```

4. Prefer additive, backwards-compatible changes to the public API. If a breaking change is unavoidable, introduce a deprecation window and update ``public_api.md``.

## Release readiness

For release-specific guidance, refer to:

- **Release checklist**: [development/release_checklist.md](release_checklist.md)
- **Architecture guardrails** (import boundaries, layering): [development/architecture.md](architecture.md)

## Documentation updates

When adding new user-facing features:

- Prefer documenting them as a **How-To** (task oriented) and/or **Concept** page.
- Ensure documentation examples import only the **public API**.
- Keep API reference generation deterministic (see ``docs/gen_ref_pages.py``).
