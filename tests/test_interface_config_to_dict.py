import json

import pytest


def test_prototype_search_config_to_dict_is_json_serializable() -> None:
    """PrototypeSearchConfig should provide a stable JSON-friendly dict."""

    from calm.interface.config import PrototypeSearchConfig

    cfg = PrototypeSearchConfig(k_max=2, max_results=10)
    d = cfg.to_dict()

    assert isinstance(d, dict)
    assert d["k_max"] == 2
    assert d["max_results"] == 10

    # Must be JSON serializable (for provenance + example outputs).
    json.dumps(d)


def test_prototype_search_result_to_dict_uses_config_to_dict() -> None:
    """PrototypeSearchResult.to_dict should surface the *serialized* config."""

    from calm.interface.config import PrototypeSearchConfig
    from calm.interface.results import PrototypeSearchResult

    cfg = PrototypeSearchConfig(k_max=2, max_results=10)
    res = PrototypeSearchResult(slab_a_uid="slab:A", slab_b_uid="slab:B", config=cfg, prototypes=[])

    d = res.to_dict(include_fingerprints=False)
    assert d["config"] == cfg.to_dict()
    json.dumps(d)


def test_other_interface_configs_to_dict_are_json_serializable() -> None:
    """Keep config serialization consistent across the UX wrapper surface."""

    from calm.interface.config import EnergyConfig, InterfaceBuildConfig, StrainModel

    json.dumps(StrainModel().to_dict())
    json.dumps(InterfaceBuildConfig().to_dict())
    json.dumps(EnergyConfig().to_dict())


def test_prototype_search_config_correspondence_limit_is_optional_and_validated() -> None:
    import pytest

    from calm.interface.config import PrototypeSearchConfig

    assert PrototypeSearchConfig().correspondence_entry_limit is None
    assert PrototypeSearchConfig(correspondence_entry_limit=256).correspondence_entry_limit == 256
    with pytest.raises(ValueError, match="correspondence_entry_limit"):
        PrototypeSearchConfig(correspondence_entry_limit=0)
    with pytest.raises(TypeError, match="correspondence_entry_limit"):
        PrototypeSearchConfig(correspondence_entry_limit=True)


def test_public_search_settings_use_fixed_complete_coupled_policy() -> None:
    from calm.public.inputs.settings import SearchSettings

    config = SearchSettings().to_internal_config()
    assert config.pair_symmetry_policy == "full"
    assert config.correspondence_orientation == "proper"
    assert config.identify_material_exchange is False
    assert config.correspondence_entry_limit is None


def test_prototype_search_config_pair_identity_policy_is_explicit_and_validated() -> None:
    import pytest

    from calm.interface.config import PrototypeSearchConfig

    default = PrototypeSearchConfig()
    assert default.pair_symmetry_policy == "full"
    assert default.correspondence_orientation == "proper"
    assert default.identify_material_exchange is False

    configured = PrototypeSearchConfig(
        pair_symmetry_policy="proper",
        correspondence_orientation="all",
        identify_material_exchange=True,
    )
    serialized = configured.to_dict()
    assert serialized["pair_symmetry_policy"] == "proper"
    assert serialized["correspondence_orientation"] == "all"
    assert serialized["identify_material_exchange"] is True

    with pytest.raises(ValueError, match="pair_symmetry_policy"):
        PrototypeSearchConfig(pair_symmetry_policy="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="correspondence_orientation"):
        PrototypeSearchConfig(
            correspondence_orientation="invalid"  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="identify_material_exchange"):
        PrototypeSearchConfig(identify_material_exchange=1)  # type: ignore[arg-type]


def test_exact_pair_deduplication_controls_are_not_active_config_fields() -> None:
    from dataclasses import fields

    import pytest

    from calm.interface.config import PrototypeSearchConfig
    from calm.public.inputs.settings import SearchSettings

    assert "deduplicate" not in {field.name for field in fields(SearchSettings)}
    assert "dedupe_by_key" not in {
        field.name for field in fields(PrototypeSearchConfig)
    }
    assert "deduplicate" not in SearchSettings().to_dict()
    assert "dedupe_by_key" not in PrototypeSearchConfig().to_dict()

    with pytest.raises(TypeError, match="deduplicate"):
        SearchSettings(deduplicate=False)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="dedupe_by_key"):
        PrototypeSearchConfig(dedupe_by_key=False)  # type: ignore[call-arg]


def test_retired_search_deduplication_value_is_rejected() -> None:
    from calm.public.inputs.settings import SearchSettings

    serialized = {
        **SearchSettings(max_candidates=7).to_dict(),
        "deduplicate": False,
    }
    with pytest.raises(TypeError, match="deduplicate"):
        SearchSettings.from_dict(serialized)
