"""Dependency-light tests for explicit environment validation profiles."""

from __future__ import annotations

from importlib import util
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _module() -> ModuleType:
    path = ROOT / "environments" / "validate_environment.py"
    spec = util.spec_from_file_location("calm_environment_validator", path)
    assert spec is not None and spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_checks(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        module,
        "_check_python",
        lambda checks, validation: calls.append("python"),
    )
    monkeypatch.setattr(
        module,
        "_check_distribution_imports",
        lambda checks, imports: calls.append(
            "distributions:" + ",".join(sorted(imports))
        ),
    )
    monkeypatch.setattr(
        module,
        "_check_required_imports",
        lambda checks, imports: calls.append(
            "required:" + ",".join(sorted(imports))
        ),
    )
    monkeypatch.setattr(
        module,
        "_check_any_import",
        lambda checks, imports: calls.append("any:" + ",".join(sorted(imports))),
    )
    monkeypatch.setattr(
        module,
        "_check_calm_installation",
        lambda checks, project_smoke: calls.append(f"calm:{project_smoke}"),
    )
    monkeypatch.setattr(
        module,
        "_check_provider_registry",
        lambda checks, family: calls.append(f"provider:{family}"),
    )
    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
    return calls


def test_validator_defaults_to_the_import_light_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    calls = _stub_checks(module, monkeypatch)

    report = module.validate_environment()

    assert report["schema"] == "calm.source_environment_validation.v1"
    assert report["profile"] == "base"
    assert report["provider"] is None
    assert report["passed"] is True
    assert calls == ["python", "distributions:numpy,sqlalchemy", "calm:True"]


def test_validator_science_profile_adds_only_the_science_layer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    calls = _stub_checks(module, monkeypatch)

    report = module.validate_environment(profile="science")

    assert report["profile"] == "science"
    assert calls == [
        "python",
        "distributions:numpy,sqlalchemy",
        "distributions:ase,scipy,spglib",
        "calm:True",
    ]


def test_validator_provider_profile_adds_one_registered_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    calls = _stub_checks(module, monkeypatch)

    report = module.validate_environment(provider="grace")

    assert report["profile"] == "provider"
    assert report["provider"] == "grace"
    assert calls == [
        "python",
        "distributions:numpy,sqlalchemy",
        "distributions:ase,scipy,spglib",
        "distributions:tensorpotential",
        "required:",
        "any:",
        "calm:True",
        "provider:grace",
    ]


def test_validator_records_external_runtime_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    _stub_checks(module, monkeypatch)

    report = module.validate_environment(provider="lammps")

    assert len(report["notes"]) == 1
    assert "external runtime or files" in report["notes"][0]


def test_validator_rejects_ambiguous_or_unknown_selection() -> None:
    module = _module()

    with pytest.raises(ValueError, match="mutually exclusive"):
        module.validate_environment(profile="base", provider="ase")
    with pytest.raises(ValueError, match="unknown provider"):
        module.validate_environment(provider="orb")
    with pytest.raises(ValueError, match="unknown profile"):
        module.validate_environment(profile="full")
