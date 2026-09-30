"""Import-light invariants for the single public API registry."""

from __future__ import annotations


def test_public_exports_are_mapped_unique_and_ordered() -> None:
    import calm.api as api

    assert len(api.PUBLIC_EXPORTS) == len(set(api.PUBLIC_EXPORTS))
    assert list(api.PUBLIC_EXPORTS) == list(api._EXPORT_MAP)
    assert list(api.__all__) == [
        name for name in api.PUBLIC_EXPORTS if name != "__version__"
    ]


def test_optional_dependency_error_has_actionable_public_context() -> None:
    from calm.exceptions import OptionalDependencyError, optional_dependency_error

    error = optional_dependency_error(
        missing="matplotlib",
        symbol="calm.Project.plot_strain_partition_scan",
    )
    assert isinstance(error, OptionalDependencyError)
    assert isinstance(error, ImportError)
    assert "matplotlib" in str(error)
    assert "calm.Project.plot_strain_partition_scan" in str(error)
    assert "pip install matplotlib" in str(error)


def test_science_extra_reports_complete_required_stack() -> None:
    from calm.exceptions import optional_dependency_error

    error = optional_dependency_error(
        missing="ase",
        extra="science",
        symbol="calm.open_project",
    )
    message = str(error)
    assert "pip install calm[science]" in message
    assert "`ase`" in message
    assert "`spglib`" in message
