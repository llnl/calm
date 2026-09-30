"""MkDocs reference-page generator.

This repository uses the `mkdocs-gen-files` plugin to generate a small set of
reference pages at build time.

Design goals
------------
- Keep the docs build deterministic and lightweight (stdlib + mkdocs-gen-files).
- Avoid importing `calm` (or heavy optional deps) during docs generation.
- Treat the repo-root `public_api.md` as the canonical API contract and mirror it
  into the MkDocs `reference/` section so the docs stay in sync.

This script is invoked by MkDocs via the `gen-files` plugin.

 NOTE: This is the canonical public-API generator for this repository.
 docs/gen_public_api_reference.py was a legacy duplicate and has been
 removed; keep this file as the single source of truth for generating
 docs/reference/public_api.md from the repository-root public_api.md.
"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files


def _repo_root() -> Path:
    # docs/gen_ref_pages.py -> docs/ -> repo root
    return Path(__file__).resolve().parents[1]


def _write_public_api_reference(*, repo_root: Path) -> None:
    """Generate `docs/reference/public_api.md` from the root inventory."""

    inventory = repo_root / "public_api.md"
    out_path = Path("reference") / "public_api.md"

    if not inventory.exists():
        # Keep MkDocs build resilient even if the inventory file is missing.
        with mkdocs_gen_files.open(out_path, "w") as f:
            f.write("# Public API\n\n")
            f.write("`public_api.md` was not found at the repository root.\n")
        return

    text = inventory.read_text(encoding="utf-8")

    # Mirror the inventory verbatim so the docs are guaranteed to match.
    with mkdocs_gen_files.open(out_path, "w") as f:
        f.write(text)

    # In addition to mirroring the canonical public_api.md, emit explicit
    # HTML anchors for each import path so cross-page links like
    # `reference/public_api.md#calm.calculators.spec.CalculatorSpec` resolve.
    #
    # We intentionally keep this generation import-light and deterministic: we
    # only parse the inventory table present in public_api.md and write a
    # stable <a id=...></a> for every import path found.
    anchors = []
    begin_marker = "<!-- public-api-table:begin -->"
    end_marker = "<!-- public-api-table:end -->"
    if begin_marker in text and end_marker in text:
        tbl = text.split(begin_marker, 1)[1].split(end_marker, 1)[0]
        for ln in tbl.splitlines():
            ln = ln.strip()
            # rows look like: | calm.calculators.spec.CalculatorSpec | class | ... |
            if not ln.startswith("|") or ln.startswith("|---"):
                continue
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) < 2:
                continue
            import_path = parts[1]
            # Skip header rows
            if import_path.lower().startswith("import path"):
                continue
            if import_path:
                # anchor ids must be unique; use the import path verbatim
                anchors.append(import_path)

    if anchors:
        # Append explicit Markdown headings with attribute IDs so MkDocs will
        # generate stable anchors. The `attr_list` markdown extension is
        # enabled in mkdocs.yml which allows the `{#id}` syntax.
        with mkdocs_gen_files.open(out_path, "a") as f:
            f.write("\n\n<!-- generated-api-anchors:begin -->\n")
            for a in anchors:
                # Write a compact heading which will create an anchor with the
                # exact id required by doc links (e.g., #calm.calculators.spec.CalculatorSpec)
                f.write(f"### {a} {{#{a}}}\n\n")
            f.write("<!-- generated-api-anchors:end -->\n")

    # Point the "edit" link at the canonical source-of-truth file.
    # (Path is relative to the repo root.)
    mkdocs_gen_files.set_edit_path(out_path, "public_api.md")


def main() -> None:
    repo_root = _repo_root()
    _write_public_api_reference(repo_root=repo_root)


if __name__ == "__main__":
    main()
