# Release checklist

This checklist is intended to be followed when cutting a tagged release of **CALM**.

The repository is configured so that CI performs:

- Unit tests (`pytest`)
- Docs build (`mkdocs build --strict`)
- Wheel + sdist build (`python -m build`)
- Install smoke test of the built wheel in a fresh virtual environment
- (Optional) publication to the **GitLab PyPI Package Registry** (manual job on tags)

## 1) Pre-flight (local)

1. Ensure your working tree is clean.
2. Ensure the public API inventory is up to date:
   - `public_api.md` reflects the stable user-facing import paths.
3. Update the changelog:
   - Add a dated section for the release in `CHANGELOG.md`.
   - Move relevant entries from `[Unreleased]` into the release section.
4. Bump the package version in `pyproject.toml`:

```bash
# Edit the version field under [project]
$ sed -n '1,120p' pyproject.toml
```

5. Run the full test suite and docs build locally:

```bash
$ python -m pip install -U pip
$ python -m pip install -e '.[viz]'
$ pytest -q
$ python -m pip install -r docs/requirements.txt
$ mkdocs build --strict
```

## 2) Cut the release commit

1. Commit the version bump + changelog updates.

```bash
$ git add pyproject.toml CHANGELOG.md
$ git commit -m "Release X.Y.Z"
```

2. Push the commit to the default branch (or a protected release branch, if you use one).

```bash
$ git push
```

## 3) Tag the release

Tag naming is a team choice; two common conventions:

- `vX.Y.Z` (recommended, human-friendly)
- `X.Y.Z`

The *package version* still comes from `pyproject.toml` unless/until we adopt tag-derived versioning
(e.g. `setuptools-scm`) as a future improvement.

```bash
$ git tag -a vX.Y.Z -m "CALM vX.Y.Z"
$ git push --tags
```

## 4) Confirm the tag pipeline is green

On a tag pipeline, CI should:

- Run the test matrix (py310/py311/py312)
- Build the distributions (`dist/*.whl`, `dist/*.tar.gz`)
- Verify:
  - The wheel installs and imports cleanly in a fresh venv
  - `twine check dist/*` passes (metadata / long description)

## 5) Publish to the GitLab PyPI Package Registry (optional)

If you want the package to be pip-installable via your GitLab instance's PyPI registry, use the
manual publish job in the tag pipeline.

- Job name: $publish:gitlab_pypi$
- Credentials: uses the built-in `CI_JOB_TOKEN`
- Target repository URL:
  - `${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/pypi`

Notes:

- The GitLab project must have the Package Registry enabled and allow CI job tokens to write.
- For locked-down GitLab installations, you may prefer a **Deploy Token** or personal access token.
  If you switch away from `CI_JOB_TOKEN`, update the CI job accordingly.

## 6) Publish documentation (GitLab Pages)

Documentation is built and deployed from the default branch via the `pages` job.

- Merge the release commit to the default branch (if not already).
- Confirm the `pages` job succeeds.
- Confirm the Pages site is updated.

## 7) Create the GitLab Release entry

Create a GitLab Release entry for the tag (UI or API), and link:

- The changelog section for the release
- Documentation site
- Optional: attach wheel/sdist artifacts produced by CI

## 8) Post-release

- Open a follow-up PR updating `[Unreleased]` in `CHANGELOG.md` with placeholders for the next cycle.
- If the release included deprecations, ensure the deprecation window and replacement paths are clearly documented.
