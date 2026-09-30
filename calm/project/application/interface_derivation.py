"""Exact derivation of interface variants from persisted follow-up results."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from calm.project.domain.contracts.refinement_result import (
    registry_result_state,
    strain_partition_selection,
)

from ..domain.models import DerivedInterface, FollowupResult, Run
from ._uow import fresh_uow, require_uow_factory
from .derived_interfaces import DerivedInterfaceService


def _merged_params(
    seed_params: Mapping[str, Any] | None,
    user_params: Mapping[str, Any] | None,
    *,
    followup: FollowupResult,
    run_spec: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(seed_params or {})
    merged.update(dict(user_params or {}))
    merged.update(
        {
            "source_followup_uid": followup.uid_full,
            "source_run_uid": followup.run_uid_full,
        }
    )
    payload = run_spec.get("payload")
    if isinstance(payload, Mapping):
        search_name = payload.get("search_name")
        if search_name:
            merged["search_name"] = search_name
        registry_settings = payload.get("registry_settings")
        if registry_settings is not None:
            merged["registry_settings"] = registry_settings
    return merged


class InterfaceDerivationService:
    """Own follow-up-to-interface derivation and mandatory lineage."""

    def __init__(
        self,
        *,
        uow_factory: Callable[[], Any],
        artifacts: Any | None = None,
    ) -> None:
        self._uow_factory = require_uow_factory(
            uow_factory,
            owner="InterfaceDerivationService",
        )
        self._interfaces = DerivedInterfaceService(
            uow_factory=uow_factory,
            artifacts=artifacts,
        )

    def derive_from_strain_scan(
        self,
        scan_run: str,
        *,
        label: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[DerivedInterface]:
        """Persist one derived interface for each completed strain result."""

        with fresh_uow(
            self._uow_factory,
            owner="InterfaceDerivationService",
        ) as uow:
            run = self._resolve_completed_run(
                uow,
                scan_run,
                expected_type="strain_partition_scan",
            )
            results = uow.followups.list(
                run_uid_full=run.uid_full,
                kind="strain_partition_scan",
            )
            seed_specs = self._seed_specs(uow, run)
            created: list[DerivedInterface] = []
            for result in results:
                target_metric, target_alpha, _target_value = strain_partition_selection(
                    result.payload or {}
                )
                seed_spec = self._seed_spec(result, seed_specs)
                seed_params = self._seed_params(seed_spec)
                lineage = _merged_params(
                    seed_params,
                    params,
                    followup=result,
                    run_spec=run.spec,
                )
                lineage["strain_target_metric"] = target_metric
                interface = self._interfaces.create_in(
                    uow,
                    prototype=self._seed_or_prototype(result, seed_specs),
                    label=label,
                    stage="strain_partitioned",
                    strain_alpha=target_alpha,
                    registry_shift_frac_a=(
                        seed_spec["registry_shift_frac_a"] if seed_spec else None
                    ),
                    z_padding=seed_spec["z_padding"] if seed_spec else None,
                    vacuum=seed_spec["vacuum"] if seed_spec else None,
                    params=lineage,
                )
                self._followup_edge(uow, result, interface)
                created.append(interface)
            return created

    def derive_from_registry_search(
        self,
        reg_run: str,
        *,
        label: str | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> list[DerivedInterface]:
        """Persist one derived interface for each completed registry result."""

        with fresh_uow(
            self._uow_factory,
            owner="InterfaceDerivationService",
        ) as uow:
            run = self._resolve_completed_run(
                uow,
                reg_run,
                expected_type="registry_search",
            )
            results = uow.followups.list(
                run_uid_full=run.uid_full,
                kind="registry_search",
            )
            seed_specs = self._seed_specs(uow, run)
            created: list[DerivedInterface] = []
            for result in results:
                payload = dict(result.payload or {})
                shift, z_padding, vacuum = registry_result_state(payload)
                seed_spec = self._seed_spec(result, seed_specs)
                seed_params = self._seed_params(seed_spec)
                lineage = _merged_params(
                    seed_params,
                    params,
                    followup=result,
                    run_spec=run.spec,
                )
                interface = self._interfaces.create_in(
                    uow,
                    prototype=self._seed_or_prototype(result, seed_specs),
                    label=label,
                    stage="registry_refined",
                    strain_alpha=(seed_spec["strain_alpha"] if seed_spec else None),
                    registry_shift_frac_a=shift,
                    z_padding=z_padding,
                    vacuum=vacuum,
                    inherit_seed_vacuum=False,
                    params=lineage,
                )
                self._followup_edge(uow, result, interface)
                created.append(interface)
            return created

    @staticmethod
    def _resolve_completed_run(
        uow: Any,
        identifier: str,
        *,
        expected_type: str,
    ) -> Run:
        run_uid = uow.ids.resolve_run(identifier)
        run = uow.runs.get_by_uid_full(run_uid)
        if run is None:
            raise KeyError(f"Run not found: {identifier!r}")
        if run.run_type != expected_type:
            raise ValueError(
                f"Run {identifier!r} has type {run.run_type!r}; "
                f"expected {expected_type!r}."
            )
        if run.status != "done":
            raise ValueError(
                f"Run {identifier!r} must be done before interface derivation."
            )
        return run

    @staticmethod
    def _target_specs(run: Run) -> list[Mapping[str, Any]]:
        targets = run.spec.get("targets")
        if targets is None:
            return []
        if isinstance(targets, (str, bytes)) or not isinstance(targets, Sequence):
            raise TypeError("Follow-up run targets must be a sequence of mappings.")
        values: list[Mapping[str, Any]] = []
        for target in targets:
            if not isinstance(target, Mapping):
                raise TypeError("Every follow-up run target must be a mapping.")
            values.append(target)
        return values

    @classmethod
    def _seed_specs(
        cls,
        uow: Any,
        run: Run,
    ) -> dict[str, Mapping[str, Any]]:
        specs: dict[str, Mapping[str, Any]] = {}
        for target in cls._target_specs(run):
            if target.get("target_kind") != "interface":
                continue
            uid = target.get("target_uid_full")
            if not isinstance(uid, str) or not uid:
                raise ValueError("An interface target must provide target_uid_full.")
            interface = uow.derived_interfaces.get_by_uid_full(uid)
            if interface is None:
                raise KeyError(f"Seed derived interface not found: {uid!r}")
            if not isinstance(interface.spec, Mapping):
                raise TypeError("Seed derived-interface spec must be a mapping.")
            specs[uid] = dict(interface.spec)
        return specs

    @staticmethod
    def _seed_uid(result: FollowupResult) -> str | None:
        if result.target_kind == "interface":
            if not result.target_uid_full:
                raise ValueError(
                    "An interface-targeted follow-up result must persist "
                    "target_uid_full."
                )
            return str(result.target_uid_full)
        return None

    @classmethod
    def _seed_spec(
        cls,
        result: FollowupResult,
        seed_specs: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        seed_uid = cls._seed_uid(result)
        if seed_uid is None:
            return {}
        if seed_uid not in seed_specs:
            raise KeyError(
                f"Follow-up seed interface is not declared by its run: {seed_uid}"
            )
        return seed_specs[seed_uid]

    @classmethod
    def _seed_or_prototype(
        cls,
        result: FollowupResult,
        seed_specs: Mapping[str, Mapping[str, Any]],
    ) -> str:
        seed_uid = cls._seed_uid(result)
        if seed_uid is not None:
            if seed_uid not in seed_specs:
                raise KeyError(
                    f"Follow-up seed interface is not declared by its run: {seed_uid}"
                )
            return seed_uid
        if not result.prototype_uid_full:
            raise ValueError("A follow-up result must persist prototype_uid_full.")
        return str(result.prototype_uid_full)

    @staticmethod
    def _seed_params(spec: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if not spec:
            return None
        if "params" not in spec:
            raise ValueError("Seed derived-interface spec must contain current params.")
        value = spec["params"]
        if not isinstance(value, Mapping):
            raise TypeError("Seed derived-interface params must be a mapping.")
        return value

    @staticmethod
    def _followup_edge(
        uow: Any,
        result: FollowupResult,
        interface: DerivedInterface,
    ) -> None:
        uow.edges.add(
            src_uid_full=result.uid_full,
            dst_uid_full=interface.uid_full,
            kind="followup_to_interface",
            payload={"source_kind": result.kind},
        )
