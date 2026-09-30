import sys


def test_importing_calm_project_does_not_mutate_sys_meta_path():
    before = list(sys.meta_path)
    import calm.project  # noqa: F401
    after = list(sys.meta_path)

    # Importing calm.project should not install meta_path hooks.
    assert after == before
