# Patch generation checklist

Use this checklist before every patch-producing response.

## Artifact checklist

- [ ] Patch filename follows `NNNN-short-description.patch`.
- [ ] Corrective patch uses the original number plus a suffix, such as `0016a-...`.
- [ ] Patch applies with `git apply --check` against the current baseline.
- [ ] Instructions assume the patch was downloaded to `~/Downloads`.
- [ ] No zip overlay or complete-file bundle is provided unless explicitly requested.
- [ ] The patch is scoped to one milestone or subtask.
- [ ] Validation limitations are stated honestly.

## Response checklist

Every patch-producing response must include:

- active milestone;
- roadmap checklist;
- what changed;
- architecture notes;
- patch artifact link;
- patch application commands;
- installation commands;
- test commands;
- expected results;
- validation performed;
- user feedback checklist;
- next planned work.

## Scope checklist

- [ ] No unrelated cleanup is mixed into the patch.
- [ ] Public API changes update the public API contract or inventory when needed.
- [ ] Example changes update tests or documentation when needed.
- [ ] Engineering-process changes update `docs/engineering/`.
