"""Typed public contracts, comparisons, and summaries for CALM campaigns."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from itertools import product
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from calm.project.domain.contracts.campaign import canonical_campaign_stages
from calm.public.inputs.settings import (
    BuildSettings,
    DatasetSettings,
    EnergyConvention,
    EnergySettings,
    ReferenceEnergySettings,
    RegistrySettings,
    RelaxSettings,
    SearchSettings,
    StrainPartitionSettings,
)
from calm.public.records.campaign_views import (
    CAMPAIGN_COMPARISON_VIEW_SPECS,
    CAMPAIGN_RESULT_VIEW_SPECS,
)
from calm.public.records.tabular import (
    TabularResultMixin,
    projection_dataframe,
    projection_table,
    resolve_named_projection,
    write_projection_csv,
)


@dataclass(frozen=True)
class _CampaignCaseVariant:
    """One typed variant used by ``CampaignCase.grid()``."""

    label: str
    search_settings: SearchSettings | None = None
    build_top: int | None = None
    build_settings: BuildSettings | None = None
    strain_settings: StrainPartitionSettings | None = None
    registry_settings: RegistrySettings | None = None
    relax_settings: RelaxSettings | None = None
    relax_backend: str | None = None
    energy_settings: EnergySettings | None = None
    energy_backend: str | None = None
    energy_convention: EnergyConvention | None = None
    energy_references: ReferenceEnergySettings | None = None
    dataset_settings: DatasetSettings | None = None
    dataset_name: str | None = None

    def validate(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Campaign case variant labels must be non-empty strings.")
        if self.label != self.label.strip():
            raise ValueError(
                "Campaign case variant labels must not have surrounding whitespace."
            )
        if self.search_settings is not None and not isinstance(
            self.search_settings, SearchSettings
        ):
            raise TypeError("Campaign case search_settings must be SearchSettings.")
        if self.search_settings is not None:
            self.search_settings.validate()
        _validate_case_overrides(self)


@dataclass(frozen=True)
class CampaignCase:
    """One named system/search case in a synchronous campaign.

    Existing persisted searches may be referenced by ``search_name`` alone. When
    the search does not exist, both surface identifiers are required. Optional
    workflow fields override campaign-wide settings for this case.

    Attributes:
        name: Unique case label within the campaign specification.
        search_name: Exact persisted search name to reuse or create.
        surface_a: Exact persisted surface-A selector used when creating a search.
            Default: ``None``.
        surface_b: Exact persisted surface-B selector used when creating a search.
            Default: ``None``.
        search_settings: Search controls for this case. Default:
            ``SearchSettings()``.
        build_top: Optional case-specific number of ranked candidates to build.
            Default: ``None``.
        build_settings: Optional case-specific construction settings.
            Default: ``None``.
        strain_settings: Optional case-specific strain-partition settings.
            Default: ``None``.
        registry_settings: Optional case-specific registry settings.
            Default: ``None``.
        relax_settings: Optional case-specific relaxation settings.
            Default: ``None``.
        relax_backend: Optional case-specific relaxation backend identifier.
            Default: ``None``.
        energy_settings: Optional case-specific energy settings.
            Default: ``None``.
        energy_backend: Optional case-specific energy backend identifier.
            Default: ``None``.
        energy_convention: Optional case-specific thermodynamic convention.
            Default: ``None``.
        energy_references: Optional case-specific manual reference values.
            Default: ``None``.
        dataset_settings: Optional case-specific dataset contract.
            Default: ``None``.
        dataset_name: Optional exact output dataset name. Default: ``None``.
        dimensions: Stable string labels exposed in grouping and comparison
            columns. Default: an empty mapping.
    """

    name: str
    search_name: str
    surface_a: str | None = None
    surface_b: str | None = None
    search_settings: SearchSettings = field(default_factory=SearchSettings)
    build_top: int | None = None
    build_settings: BuildSettings | None = None
    strain_settings: StrainPartitionSettings | None = None
    registry_settings: RegistrySettings | None = None
    relax_settings: RelaxSettings | None = None
    relax_backend: str | None = None
    energy_settings: EnergySettings | None = None
    energy_backend: str | None = None
    energy_convention: EnergyConvention | None = None
    energy_references: ReferenceEnergySettings | None = None
    dataset_settings: DatasetSettings | None = None
    dataset_name: str | None = None
    dimensions: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("CampaignCase.name must be non-empty.")
        if not isinstance(self.search_name, str) or not self.search_name.strip():
            raise ValueError("CampaignCase.search_name must be non-empty.")
        if (
            self.name != self.name.strip()
            or self.search_name != self.search_name.strip()
        ):
            raise ValueError(
                "CampaignCase names and search names must not have surrounding "
                "whitespace."
            )
        if (self.surface_a is None) != (self.surface_b is None):
            raise ValueError(
                "CampaignCase.surface_a and surface_b must either both be set "
                "or both be omitted."
            )
        for field_name in ("surface_a", "surface_b"):
            item = getattr(self, field_name)
            if item is not None and (not isinstance(item, str) or not item.strip()):
                raise ValueError(
                    f"CampaignCase.{field_name} must be a non-empty string when set."
                )
        if not isinstance(self.search_settings, SearchSettings):
            raise TypeError("CampaignCase.search_settings must be SearchSettings.")
        self.search_settings.validate()
        _validate_case_overrides(self)
        if not isinstance(self.dimensions, Mapping):
            raise TypeError("CampaignCase.dimensions must be a mapping.")
        for key, value in self.dimensions.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError(
                    "CampaignCase dimension names and values must be strings."
                )
            if not key.strip() or not value.strip():
                raise ValueError(
                    "CampaignCase dimension names and values must be non-empty."
                )

    def resolved_settings(self, settings: "CampaignSettings") -> "CampaignSettings":
        """Return validated campaign settings after applying this case's overrides."""
        values = {
            "build_top": self.build_top,
            "build_settings": self.build_settings,
            "strain_settings": self.strain_settings,
            "registry_settings": self.registry_settings,
            "relax_settings": self.relax_settings,
            "relax_backend": self.relax_backend,
            "energy_settings": self.energy_settings,
            "energy_backend": self.energy_backend,
            "energy_convention": self.energy_convention,
            "energy_references": self.energy_references,
            "dataset_settings": self.dataset_settings,
        }
        updates = {key: value for key, value in values.items() if value is not None}
        if self.energy_convention is not None:
            # A convention override without scalar references requests the
            # authoritative first-class reference workflow for this case.
            updates["energy_references"] = self.energy_references
        resolved = replace(settings, **updates)
        resolved.validate()
        return resolved

    @staticmethod
    def variant(
        label: str,
        *,
        search_settings: SearchSettings | None = None,
        build_top: int | None = None,
        build_settings: BuildSettings | None = None,
        strain_settings: StrainPartitionSettings | None = None,
        registry_settings: RegistrySettings | None = None,
        relax_settings: RelaxSettings | None = None,
        relax_backend: str | None = None,
        energy_settings: EnergySettings | None = None,
        energy_backend: str | None = None,
        energy_convention: EnergyConvention | None = None,
        energy_references: ReferenceEnergySettings | None = None,
        dataset_settings: DatasetSettings | None = None,
        dataset_name: str | None = None,
    ) -> _CampaignCaseVariant:
        """Create one typed grid variant without raw settings dictionaries."""
        variant = _CampaignCaseVariant(
            label=label,
            search_settings=search_settings,
            build_top=build_top,
            build_settings=build_settings,
            strain_settings=strain_settings,
            registry_settings=registry_settings,
            relax_settings=relax_settings,
            relax_backend=relax_backend,
            energy_settings=energy_settings,
            energy_backend=energy_backend,
            energy_convention=energy_convention,
            energy_references=energy_references,
            dataset_settings=dataset_settings,
            dataset_name=dataset_name,
        )
        variant.validate()
        return variant

    @classmethod
    def grid(
        cls,
        base: "CampaignCase | Sequence[CampaignCase]",
        *,
        axes: Mapping[str, Sequence[_CampaignCaseVariant]],
        separator: str = "__",
        unique_searches: bool | None = None,
    ) -> tuple["CampaignCase", ...]:
        """Expand typed Cartesian case variants into deterministic campaign cases.

        Each axis is a mapping entry whose values were created with
        ``CampaignCase.variant()``. Variants on separate axes may override
        different workflow settings. Conflicting overrides of the same field are
        rejected rather than resolved by axis order. By default, downstream-only
        grids share the base persisted search, while any search-settings axis
        receives deterministic unique search names.
        """
        bases = (base,) if isinstance(base, CampaignCase) else tuple(base)
        if not bases:
            raise ValueError("CampaignCase.grid requires at least one base case.")
        if not axes:
            raise ValueError("CampaignCase.grid requires at least one axis.")
        if not separator:
            raise ValueError("CampaignCase.grid separator must be non-empty.")
        for item in bases:
            if not isinstance(item, CampaignCase):
                raise TypeError(
                    "CampaignCase.grid base values must be CampaignCase instances."
                )
            item.validate()

        axis_rows: list[tuple[str, tuple[_CampaignCaseVariant, ...]]] = []
        axis_names: set[str] = set()
        for axis_name, raw_variants in axes.items():
            name = str(axis_name).strip()
            if not name:
                raise ValueError("Campaign grid axis names must be non-empty.")
            if name in axis_names:
                raise ValueError(
                    f"Campaign grid contains duplicate normalized axis name {name!r}."
                )
            axis_names.add(name)
            variants = tuple(raw_variants)
            if not variants:
                raise ValueError(f"Campaign grid axis {name!r} has no variants.")
            if not all(isinstance(item, _CampaignCaseVariant) for item in variants):
                raise TypeError(
                    "Campaign grid axes must contain values returned by "
                    "CampaignCase.variant()."
                )
            for item in variants:
                item.validate()
            labels = [item.label for item in variants]
            if len(labels) != len(set(labels)):
                raise ValueError(f"Campaign grid axis {name!r} has duplicate labels.")
            axis_rows.append((name, variants))

        expanded: list[CampaignCase] = []
        override_fields = (
            "build_top",
            "build_settings",
            "strain_settings",
            "registry_settings",
            "relax_settings",
            "relax_backend",
            "energy_settings",
            "energy_backend",
            "energy_convention",
            "energy_references",
            "dataset_settings",
            "dataset_name",
        )
        for base_case in bases:
            for combination in product(*(variants for _name, variants in axis_rows)):
                labels: list[str] = []
                search_labels: list[str] = []
                dimensions = {str(k): str(v) for k, v in base_case.dimensions.items()}
                selected: dict[str, Any] = {}
                search_override: SearchSettings | None = None
                for (axis_name, _variants), variant in zip(axis_rows, combination):
                    if axis_name in dimensions:
                        raise ValueError(
                            f"Campaign grid axis {axis_name!r} duplicates a base "
                            "dimension."
                        )
                    dimensions[axis_name] = str(variant.label)
                    labels.append(f"{axis_name}-{variant.label}")
                    if variant.search_settings is not None:
                        if (
                            search_override is not None
                            and search_override != variant.search_settings
                        ):
                            raise ValueError(
                                "Multiple campaign grid axes override search_settings. "
                                "Combine those search controls into one typed axis."
                            )
                        search_override = variant.search_settings
                        search_labels.append(f"{axis_name}-{variant.label}")
                    for field_name in override_fields:
                        value = getattr(variant, field_name)
                        if value is None:
                            continue
                        previous = selected.get(field_name)
                        if previous is not None and previous != value:
                            raise ValueError(
                                f"Campaign grid variants conflict on {field_name!r}."
                            )
                        selected[field_name] = value
                suffix = separator.join(labels)
                make_unique_search = (
                    search_override is not None
                    if unique_searches is None
                    else bool(unique_searches)
                )
                if search_override is not None and not make_unique_search:
                    raise ValueError(
                        "Campaign grids that vary search_settings require unique "
                        "search names."
                    )
                if make_unique_search and (
                    base_case.surface_a is None or base_case.surface_b is None
                ):
                    raise ValueError(
                        "Campaign grids that create unique searches require exact "
                        "surface_a and surface_b identifiers on every base case."
                    )
                search_suffix = (
                    suffix if unique_searches is True else separator.join(search_labels)
                )
                case = replace(
                    base_case,
                    name=f"{base_case.name}{separator}{suffix}",
                    search_name=(
                        f"{base_case.search_name}{separator}{search_suffix}"
                        if make_unique_search
                        else base_case.search_name
                    ),
                    search_settings=search_override or base_case.search_settings,
                    dimensions=dimensions,
                    **selected,
                )
                case.validate()
                expanded.append(case)

        names = [case.name for case in expanded]
        if len(names) != len(set(names)):
            raise ValueError("CampaignCase.grid generated duplicate case names.")
        return tuple(expanded)

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "name": str(self.name),
            "search_name": str(self.search_name),
            "surface_a": str(self.surface_a) if self.surface_a is not None else None,
            "surface_b": str(self.surface_b) if self.surface_b is not None else None,
            "search_settings": self.search_settings.to_dict(),
            "build_top": int(self.build_top) if self.build_top is not None else None,
            "build_settings": (
                self.build_settings.to_dict() if self.build_settings else None
            ),
            "strain_settings": (
                self.strain_settings.to_dict() if self.strain_settings else None
            ),
            "registry_settings": (
                self.registry_settings.to_dict() if self.registry_settings else None
            ),
            "relax_settings": (
                self.relax_settings.to_dict() if self.relax_settings else None
            ),
            "relax_backend": self.relax_backend,
            "energy_settings": (
                self.energy_settings.to_dict() if self.energy_settings else None
            ),
            "energy_backend": self.energy_backend,
            "energy_convention": (
                self.energy_convention.to_dict() if self.energy_convention else None
            ),
            "energy_references": (
                self.energy_references.to_dict() if self.energy_references else None
            ),
            "dataset_settings": (
                self.dataset_settings.to_dict() if self.dataset_settings else None
            ),
            "dataset_name": self.dataset_name,
            "dimensions": {str(k): str(v) for k, v in sorted(self.dimensions.items())},
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CampaignCase":
        build = value.get("build_settings")
        strain = value.get("strain_settings")
        registry = value.get("registry_settings")
        relax = value.get("relax_settings")
        energy = value.get("energy_settings")
        convention = value.get("energy_convention")
        references = value.get("energy_references")
        dataset = value.get("dataset_settings")
        return cls(
            name=str(value["name"]),
            search_name=str(value["search_name"]),
            surface_a=(str(value["surface_a"]) if value.get("surface_a") else None),
            surface_b=(str(value["surface_b"]) if value.get("surface_b") else None),
            search_settings=SearchSettings.from_dict(
                dict(value.get("search_settings") or {})
            ),
            build_top=(
                int(value["build_top"]) if value.get("build_top") is not None else None
            ),
            build_settings=(
                BuildSettings(**dict(build)) if isinstance(build, Mapping) else None
            ),
            strain_settings=(
                StrainPartitionSettings(
                    target_metric=str(strain.get("target_metric")),
                    alphas=(
                        tuple(strain["alphas"])
                        if strain.get("alphas") is not None
                        else None
                    ),
                )
                if isinstance(strain, Mapping)
                else None
            ),
            registry_settings=(
                RegistrySettings(**dict(registry))
                if isinstance(registry, Mapping)
                else None
            ),
            relax_settings=(
                RelaxSettings(**dict(relax)) if isinstance(relax, Mapping) else None
            ),
            relax_backend=(
                str(value["relax_backend"])
                if value.get("relax_backend") is not None
                else None
            ),
            energy_settings=(
                EnergySettings(**dict(energy)) if isinstance(energy, Mapping) else None
            ),
            energy_backend=(
                str(value["energy_backend"])
                if value.get("energy_backend") is not None
                else None
            ),
            energy_convention=(
                EnergyConvention(
                    formula=str(convention.get("formula")),
                    n_interfaces=int(convention.get("n_interfaces")),
                    area_source=str(
                        convention.get(
                            "area_source",
                            "authoritative_interface_area",
                        )
                    ),
                )
                if isinstance(convention, Mapping)
                else None
            ),
            energy_references=(
                ReferenceEnergySettings(**dict(references))
                if isinstance(references, Mapping)
                else None
            ),
            dataset_settings=(
                DatasetSettings(**dict(dataset))
                if isinstance(dataset, Mapping)
                else None
            ),
            dataset_name=(
                str(value["dataset_name"])
                if value.get("dataset_name") is not None
                else None
            ),
            dimensions={
                str(key): str(item)
                for key, item in dict(value.get("dimensions") or {}).items()
            },
        )


def _validate_case_overrides(value: Any) -> None:
    build_top = getattr(value, "build_top", None)
    if build_top is not None:
        if isinstance(build_top, bool) or not isinstance(build_top, int):
            raise TypeError("Campaign case build_top must be an integer.")
        if build_top < 1:
            raise ValueError("Campaign case build_top must be >= 1.")

    typed_fields = (
        ("build_settings", BuildSettings, "validate"),
        ("strain_settings", StrainPartitionSettings, "validate"),
        (
            "registry_settings",
            RegistrySettings,
            "validate_for_persisted_refinement",
        ),
        ("relax_settings", RelaxSettings, "validate"),
        ("energy_settings", EnergySettings, "validate"),
        ("energy_convention", EnergyConvention, "validate"),
        ("dataset_settings", DatasetSettings, "validate"),
    )
    for field_name, expected_type, validator_name in typed_fields:
        item = getattr(value, field_name, None)
        if item is None:
            continue
        if not isinstance(item, expected_type):
            raise TypeError(
                f"Campaign case {field_name} must be {expected_type.__name__}."
            )
        getattr(item, validator_name)()

    references = getattr(value, "energy_references", None)
    if references is not None and not isinstance(references, ReferenceEnergySettings):
        raise TypeError(
            "Campaign case energy_references must be ReferenceEnergySettings."
        )

    for field_name in ("relax_backend", "energy_backend", "dataset_name"):
        item = getattr(value, field_name, None)
        if item is None:
            continue
        if not isinstance(item, str):
            raise TypeError(f"Campaign case {field_name} must be a string.")
        if not item.strip():
            raise ValueError(
                f"Campaign case {field_name} must be non-empty when provided."
            )

    convention = getattr(value, "energy_convention", None)
    if convention is not None and references is not None:
        references.validate_for(convention)


@dataclass(frozen=True)
class CampaignSettings:
    """Operational settings for a first-class synchronous campaign.

    Campaign execution is intentionally in-process. Every scientific control
    participates in the persisted specification and deterministic campaign-run
    identity. Export destinations are runtime presentation choices and do not
    affect scientific identity.

    Attributes:
        stages: Ordered canonical subsequence of ``search``, ``build``, ``refine``,
            ``relax``, ``energy``, and ``dataset``. Default: all six stages.
        build_top: Number of ranked candidates built per case. Default: ``1``.
        build_settings: Campaign-wide interface-construction settings. Default:
            ``BuildSettings()``.
        strain_settings: Campaign-wide strain-partition settings. Default: the
            canonical potential-energy-density objective.
        registry_settings: Campaign-wide registry settings. Default:
            ``RegistrySettings()``.
        relax_settings: Campaign-wide relaxation settings. Default:
            ``RelaxSettings()``.
        relax_backend: Exact relaxation backend identifier. Default: ``"real"``.
        energy_settings: Campaign-wide raw-energy settings. Default:
            ``EnergySettings()``.
        energy_backend: Exact energy backend identifier. Default: ``"real"``.
        energy_convention: Optional derived thermodynamic convention.
            Default: ``None``.
        energy_references: Optional manual reference values paired with
            ``energy_convention``. Default: ``None``.
        dataset_settings: Optional explicit dataset contract. When omitted, CALM
            selects the raw-energy or thermodynamic schema from the campaign.
            Default: ``None``.
        dataset_name_template: Format string accepting ``{campaign}`` and ``{case}``.
            Default: ``"{campaign}_{case}_dataset"``.
        on_error: Case-failure policy: ``"raise"``, ``"record"``, or ``"skip"``.
            Default: ``"record"``.
    """

    stages: tuple[str, ...] = (
        "search",
        "build",
        "refine",
        "relax",
        "energy",
        "dataset",
    )
    build_top: int = 1
    build_settings: BuildSettings = field(default_factory=BuildSettings)
    strain_settings: StrainPartitionSettings = field(
        default_factory=lambda: StrainPartitionSettings(
            target_metric="potential_energy_density_eV_per_A2"
        )
    )
    registry_settings: RegistrySettings = field(default_factory=RegistrySettings)
    relax_settings: RelaxSettings = field(default_factory=RelaxSettings)
    relax_backend: str = "real"
    energy_settings: EnergySettings = field(default_factory=EnergySettings)
    energy_backend: str = "real"
    energy_convention: EnergyConvention | None = None
    energy_references: ReferenceEnergySettings | None = None
    dataset_settings: DatasetSettings | None = None
    dataset_name_template: str = "{campaign}_{case}_dataset"
    on_error: str = "record"

    @property
    def canonical_stages(self) -> tuple[str, ...]:
        return canonical_campaign_stages(self.stages)

    @property
    def resolved_dataset_settings(self) -> DatasetSettings:
        if self.dataset_settings is not None:
            return self.dataset_settings
        schema = (
            "calm.thermodynamic.v1"
            if self.energy_convention is not None
            else "calm.raw_energy.v1"
        )
        return DatasetSettings(
            schema_version=schema,
            duplicate_policy="skip",
            failure_policy="error",
            require_complete_provenance=True,
        )

    def validate(self) -> None:
        stages = self.canonical_stages
        if int(self.build_top) < 1:
            raise ValueError("CampaignSettings.build_top must be >= 1.")
        self.build_settings.validate()
        self.strain_settings.validate()
        self.registry_settings.validate_for_persisted_refinement()
        self.relax_settings.validate()
        self.energy_settings.validate()
        if not isinstance(self.relax_backend, str) or not self.relax_backend.strip():
            raise ValueError(
                "CampaignSettings.relax_backend must be a non-empty string."
            )
        if not isinstance(self.energy_backend, str) or not self.energy_backend.strip():
            raise ValueError(
                "CampaignSettings.energy_backend must be a non-empty string."
            )
        if self.energy_convention is None and self.energy_references is not None:
            raise ValueError(
                "CampaignSettings.energy_references requires energy_convention."
            )
        if self.energy_convention is not None:
            self.energy_convention.validate()
            if self.energy_references is not None:
                self.energy_references.validate_for(self.energy_convention)
        if "dataset" in stages:
            self.resolved_dataset_settings.validate()
            try:
                self.dataset_name_template.format(campaign="campaign", case="case")
            except Exception as exc:
                raise ValueError(
                    "CampaignSettings.dataset_name_template must accept "
                    "{campaign} and {case}."
                ) from exc
        if self.on_error not in {"raise", "record", "skip"}:
            raise ValueError(
                "CampaignSettings.on_error must be 'raise', 'record', or 'skip'."
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "stages": list(self.canonical_stages),
            "build_top": int(self.build_top),
            "build_settings": self.build_settings.to_dict(),
            "strain_settings": self.strain_settings.to_dict(),
            "registry_settings": self.registry_settings.to_dict(),
            "relax_settings": self.relax_settings.to_dict(),
            "relax_backend": self.relax_backend,
            "energy_settings": self.energy_settings.to_dict(),
            "energy_backend": self.energy_backend,
            "energy_convention": (
                self.energy_convention.to_dict()
                if self.energy_convention is not None
                else None
            ),
            "energy_references": (
                self.energy_references.to_dict()
                if self.energy_references is not None
                else None
            ),
            "dataset_settings": (
                self.dataset_settings.to_dict()
                if self.dataset_settings is not None
                else None
            ),
            "dataset_name_template": self.dataset_name_template,
            "on_error": self.on_error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CampaignSettings":
        strain = dict(value.get("strain_settings") or {})
        registry = dict(value.get("registry_settings") or {})
        relax = dict(value.get("relax_settings") or {})
        energy = dict(value.get("energy_settings") or {})
        convention = value.get("energy_convention")
        references = value.get("energy_references")
        dataset = value.get("dataset_settings")
        return cls(
            stages=tuple(value.get("stages") or ()),
            build_top=int(value.get("build_top", 1)),
            build_settings=BuildSettings(**dict(value.get("build_settings") or {})),
            strain_settings=StrainPartitionSettings(
                target_metric=str(strain.get("target_metric")),
                alphas=(
                    tuple(strain["alphas"])
                    if strain.get("alphas") is not None
                    else None
                ),
            ),
            registry_settings=RegistrySettings(**registry),
            relax_settings=RelaxSettings(**relax),
            relax_backend=str(value.get("relax_backend", "real")),
            energy_settings=EnergySettings(**energy),
            energy_backend=str(value.get("energy_backend", "real")),
            energy_convention=(
                EnergyConvention(
                    formula=str(convention.get("formula")),
                    n_interfaces=int(convention.get("n_interfaces")),
                    area_source=str(
                        convention.get("area_source", "authoritative_interface_area")
                    ),
                )
                if isinstance(convention, Mapping)
                else None
            ),
            energy_references=(
                ReferenceEnergySettings(**dict(references))
                if isinstance(references, Mapping)
                else None
            ),
            dataset_settings=(
                DatasetSettings(**dict(dataset))
                if isinstance(dataset, Mapping)
                else None
            ),
            dataset_name_template=str(
                value.get("dataset_name_template", "{campaign}_{case}_dataset")
            ),
            on_error=str(value.get("on_error", "record")),
        )


@dataclass(frozen=True)
class CampaignCaseResult:
    """Summarize execution of one typed campaign case.

    The immutable result combines the case declaration, aggregate status,
    per-stage summaries, optional dataset and export path, and structured failure
    information. It can be serialized into the reopen-safe persisted edge payload.
    """

    case: CampaignCase
    status: str
    stages: Mapping[str, Any] = field(default_factory=dict)
    dataset: Any | None = None
    export_path: Path | None = None
    failure: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case.to_dict(),
            "status": self.status,
            "stages": dict(self.stages),
            "dataset": self.dataset.to_dict() if self.dataset is not None else None,
            "export_path": str(self.export_path) if self.export_path else None,
            "failure": dict(self.failure) if self.failure else None,
        }

    def to_persisted_payload(self) -> dict[str, Any]:
        """Return the reopen-safe campaign-case result edge payload."""
        return {
            "contract": "calm.campaign_case_result.v1",
            "case": self.case.to_dict(),
            "status": self.status,
            "stages": dict(self.stages),
            "dataset_uid_full": getattr(self.dataset, "uid_full", None),
            "export_path": str(self.export_path) if self.export_path else None,
            "failure": dict(self.failure) if self.failure else None,
        }


@dataclass(frozen=True)
class CampaignComparisonGroup:
    """One typed group produced by ``CampaignComparison.group_by()``."""

    fields: tuple[str, ...]
    key: tuple[Any, ...]
    comparison: "CampaignComparison"

    @property
    def values(self) -> Mapping[str, Any]:
        return dict(zip(self.fields, self.key))


@dataclass(frozen=True)
class CampaignComparison:
    """Flat, typed campaign-case comparison with grouping and ranking helpers."""

    _rows: tuple[Mapping[str, Any], ...]
    rank_metric: str | None = None
    rank_ascending: bool = True
    rank_groups: tuple[str, ...] = ()

    def _projection(self):
        return resolve_named_projection(
            CAMPAIGN_COMPARISON_VIEW_SPECS,
            self._rows,
            view="comparison",
        )

    def to_rows(self) -> list[dict[str, Any]]:
        """Return homogeneous comparison rows with deterministic columns."""

        return self._projection().to_rows()

    def to_table(
        self,
        *,
        title: str = "Campaign comparison",
        max_rows: int = 50,
        max_width: int = 120,
        max_col_width: int = 40,
        sort_by: str | None = None,
        descending: bool = False,
        file: TextIO | None = None,
    ):
        """Return a deferred campaign-comparison table."""

        return projection_table(
            self._projection(),
            title=title,
            max_rows=max_rows,
            max_width=max_width,
            max_col_width=max_col_width,
            sort_by=sort_by,
            descending=descending,
            file=file,
        )

    def to_dataframe(self):
        """Return a dataframe using the resolved comparison schema."""

        return projection_dataframe(self._projection())

    def write_table(self, path: str | Path) -> None:
        """Write comparison rows through the shared CSV projection path."""

        write_projection_csv(path, self._projection())

    def group_by(self, *fields: str) -> tuple[CampaignComparisonGroup, ...]:
        """Partition rows by stable comparison fields or grid dimensions."""
        names = tuple(str(field) for field in fields)
        if not names:
            raise ValueError("CampaignComparison.group_by requires at least one field.")
        _require_fields(self._rows, names)
        grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
        for row in self._rows:
            key = tuple(row.get(field) for field in names)
            grouped.setdefault(key, []).append(row)
        return tuple(
            CampaignComparisonGroup(
                fields=names,
                key=key,
                comparison=CampaignComparison(
                    tuple(rows),
                    rank_metric=self.rank_metric,
                    rank_ascending=self.rank_ascending,
                    rank_groups=self.rank_groups,
                ),
            )
            for key, rows in grouped.items()
        )

    def rank_by(
        self,
        metric: str,
        *,
        ascending: bool = True,
        group_by: Sequence[str] = (),
    ) -> "CampaignComparison":
        """Dense-rank cases by one numeric metric, optionally within groups.

        Missing metric values sort after numeric values and receive no rank.
        Equal values receive the same dense rank.
        """
        metric_name = str(metric)
        groups = tuple(str(field) for field in group_by)
        _require_fields(self._rows, groups)
        numeric = [
            row.get(metric_name)
            for row in self._rows
            if _is_number(row.get(metric_name))
        ]
        if not numeric:
            raise KeyError(
                f"Campaign comparison metric {metric_name!r} has no numeric values."
            )

        grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
        for row in self._rows:
            key = tuple(row.get(field) for field in groups)
            grouped.setdefault(key, []).append(row)

        ranked_rows: list[dict[str, Any]] = []
        for key, rows in grouped.items():
            available = [row for row in rows if _is_number(row.get(metric_name))]
            missing = [row for row in rows if not _is_number(row.get(metric_name))]
            available.sort(
                key=lambda row: float(row[metric_name]),
                reverse=not ascending,
            )
            previous: float | None = None
            dense_rank = 0
            for row in available:
                value = float(row[metric_name])
                if previous is None or value != previous:
                    dense_rank += 1
                    previous = value
                item = dict(row)
                item["rank"] = dense_rank
                item["rank_metric"] = metric_name
                item["rank_value"] = row[metric_name]
                for group_field, group_value in zip(groups, key):
                    item.setdefault(group_field, group_value)
                ranked_rows.append(item)
            for row in missing:
                item = dict(row)
                item["rank"] = None
                item["rank_metric"] = metric_name
                item["rank_value"] = None
                ranked_rows.append(item)

        return CampaignComparison(
            tuple(ranked_rows),
            rank_metric=metric_name,
            rank_ascending=bool(ascending),
            rank_groups=groups,
        )

    def best(
        self,
        metric: str,
        *,
        ascending: bool = True,
        group_by: Sequence[str] = (),
    ) -> "CampaignComparison":
        """Return the best-ranked case or tied cases in each requested group."""
        ranked = self.rank_by(metric, ascending=ascending, group_by=group_by)
        return CampaignComparison(
            tuple(row for row in ranked._rows if row.get("rank") == 1),
            rank_metric=ranked.rank_metric,
            rank_ascending=ranked.rank_ascending,
            rank_groups=ranked.rank_groups,
        )

    def summary(self) -> str:
        status_counts: dict[str, int] = {}
        for row in self._rows:
            status = str(row.get("status") or "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        lines = [f"Campaign comparison: {len(self._rows)} case(s)"]
        for status, count in sorted(status_counts.items()):
            lines.append(f"  {status}: {count}")
        if self.rank_metric is not None:
            direction = "ascending" if self.rank_ascending else "descending"
            lines.append(f"  ranking: {self.rank_metric} ({direction})")
            if self.rank_groups:
                lines.append(f"  rank groups: {', '.join(self.rank_groups)}")
        return "\n".join(lines)


@dataclass(frozen=True)
class CampaignWorkflowResult(TabularResultMixin):
    """Summarize one synchronous campaign execution.

    The result links the persisted campaign and run records to all case results,
    reports whether an existing compatible run was reused, and provides dataset,
    failure, comparison, table, and summary projections.
    """

    _default_view = "summary"
    _view_specs = CAMPAIGN_RESULT_VIEW_SPECS

    campaign: Any
    run: Any
    cases: tuple[CampaignCaseResult, ...]
    status: str
    reused: bool = False

    @property
    def datasets(self) -> tuple[Any, ...]:
        return tuple(
            result.dataset for result in self.cases if result.dataset is not None
        )

    @property
    def failures(self) -> tuple[CampaignCaseResult, ...]:
        return tuple(result for result in self.cases if result.failure is not None)

    def comparison(self) -> CampaignComparison:
        """Return flat case metrics suitable for grouping and ranking."""
        return CampaignComparison(tuple(self.to_rows(view="comparison")))

    def _rows_for_view(self, view: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for result in self.cases:
            if view == "all":
                row = result.to_dict()
                row["campaign_uid_full"] = getattr(
                    self.campaign, "uid_full", None
                )
                row["campaign_run_uid_full"] = getattr(
                    self.run, "uid_full", None
                )
                rows.append(row)
                continue

            dataset = result.dataset
            failure = dict(result.failure or {})
            row = {
                "campaign_uid_full": getattr(self.campaign, "uid_full", None),
                "campaign_id_short": getattr(self.campaign, "id_short", None),
                "campaign_name": getattr(self.campaign, "name", None),
                "campaign_run_uid_full": getattr(self.run, "uid_full", None),
                "campaign_run_id_short": getattr(self.run, "id_short", None),
                "case_name": result.case.name,
                "search_name": result.case.search_name,
                "status": result.status,
                "dataset_uid_full": getattr(dataset, "uid_full", None),
                "dataset_id_short": getattr(dataset, "id_short", None),
                "dataset_name": getattr(dataset, "name", None),
                "export_path": (
                    str(result.export_path) if result.export_path else None
                ),
                "failure_type": (
                    failure.get("type") or failure.get("exception_type")
                ),
                "failure_message": failure.get("message"),
            }
            if view == "comparison":
                for name, value in sorted(result.case.dimensions.items()):
                    row[f"dimension_{name}"] = value
                for stage, values in result.stages.items():
                    if isinstance(values, Mapping):
                        _flatten_scalars(row, prefix=str(stage), value=values)
                    elif _is_scalar(values):
                        row[str(stage)] = values
            rows.append(row)
        return rows

    def summary(self) -> str:
        """Return a concise campaign-level execution summary."""
        campaign_id = getattr(self.campaign, "id_short", None) or getattr(
            self.campaign, "uid_full", None
        )
        run_id = getattr(self.run, "id_short", None) or getattr(
            self.run, "uid_full", None
        )
        return "\n".join(
            [
                f"Campaign: {campaign_id}",
                f"  run: {run_id}",
                f"  status: {self.status}",
                f"  cases: {len(self.cases)}",
                f"  failures: {len(self.failures)}",
                f"  datasets: {len(self.datasets)}",
                f"  reused: {self.reused}",
            ]
        )


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _flatten_scalars(
    row: dict[str, Any],
    *,
    prefix: str,
    value: Mapping[str, Any],
) -> None:
    for key, item in value.items():
        name = f"{prefix}_{key}"
        if _is_scalar(item):
            row[name] = item
        elif isinstance(item, Mapping):
            _flatten_scalars(row, prefix=name, value=item)


def _require_fields(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    if not fields:
        return
    available = {key for row in rows for key in row}
    missing = [field for field in fields if field not in available]
    if missing:
        raise KeyError("Unknown campaign comparison field(s): " + ", ".join(missing))
