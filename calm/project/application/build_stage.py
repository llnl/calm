"""Authoritative persisted build-stage orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ..ports.uow import UnitOfWork
from .buildability import check_prototypes_buildability
from .derived_interfaces import DerivedInterfaceService
from .interface_building import build_interface_model_from_prototype
from .runs import RunsService


@dataclass(frozen=True)
class BuildStageResult:
    """One requested prototype's build-stage outcome."""

    prototype_uid: str
    status: str  # built | skipped | failed
    reason: str | None = None
    run_uid: str | None = None
    derived_interface_uid: str | None = None


class BuildStageOrchestrator:
    """Build and persist derived-interface specs from authoritative prototypes.

    The Unit-of-Work factory must return a fresh, non-entered UnitOfWork for
    each transaction. Run-state failures and repository failures are hard
    errors; per-prototype scientific build failures are recorded as failed
    results and produce a failed terminal run state.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        if not callable(uow_factory):
            raise TypeError("BuildStageOrchestrator requires a UnitOfWork factory.")
        self._uow_factory = uow_factory

    def _fresh_uow(self) -> UnitOfWork:
        uow = self._uow_factory()
        if uow is None:
            raise RuntimeError("Build-stage UnitOfWork factory returned None.")
        if int(getattr(uow, "_depth", 0) or 0) != 0:
            raise ValueError(
                "BuildStageOrchestrator requires a fresh non-entered UnitOfWork."
            )
        return uow

    def _runs(self) -> RunsService:
        return RunsService(self._fresh_uow())

    @staticmethod
    def _run_spec(
        prototypes: Sequence[str],
        *,
        run_name: str | None,
        alpha: float,
        translation_frac: tuple[float, float],
        z_padding: float,
    ) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "prototypes": list(prototypes),
            "alpha": float(alpha),
            "translation_frac": [
                float(translation_frac[0]),
                float(translation_frac[1]),
            ],
            "z_padding": float(z_padding),
        }
        if run_name is not None:
            name = str(run_name).strip()
            if not name:
                raise ValueError("run_name must be non-empty when provided.")
            spec["name"] = name
        return spec

    def build_from_prototypes(
        self,
        prototype_uids: Sequence[str],
        *,
        run_name: str | None = None,
        alpha: float = 0.5,
        translation_frac: tuple[float, float] = (0.0, 0.0),
        z_padding: float = 1.5,
        resume: bool = True,
    ) -> list[BuildStageResult]:
        requested = [str(identifier).strip() for identifier in prototype_uids]
        if any(not identifier for identifier in requested):
            raise ValueError("Prototype identifiers must be non-empty strings.")
        if not requested:
            return []

        run = self._runs().create(
            run_type="build_stage",
            spec=self._run_spec(
                requested,
                run_name=run_name,
                alpha=alpha,
                translation_frac=translation_frac,
                z_padding=z_padding,
            ),
        )
        run_uid = run.uid_full
        if resume and run.status == "done":
            return [
                BuildStageResult(
                    prototype_uid=identifier,
                    status="skipped",
                    reason="run_already_done",
                    run_uid=run_uid,
                )
                for identifier in requested
            ]

        try:
            self._runs().mark_running(
                run_uid,
                progress={"stage": "building", "n_requested": len(requested)},
            )

            with self._fresh_uow() as uow:
                buildability = check_prototypes_buildability(uow, requested)

            results: list[BuildStageResult] = []
            n_built = 0
            n_failed = 0
            n_skipped = 0

            for identifier in requested:
                readiness = buildability[identifier]
                if not readiness.buildable:
                    reason = ",".join(readiness.reasons) or "not_buildable"
                    results.append(
                        BuildStageResult(
                            prototype_uid=identifier,
                            status="skipped",
                            reason=reason,
                            run_uid=run_uid,
                        )
                    )
                    n_skipped += 1
                    continue

                prototype_uid = readiness.prototype_uid_full
                if prototype_uid is None:
                    raise RuntimeError(
                        "A buildable prototype must have a canonical UID."
                    )

                try:
                    with self._fresh_uow() as uow:
                        built = build_interface_model_from_prototype(
                            uow,
                            prototype_uid,
                            alpha=alpha,
                            translation_frac=translation_frac,
                            z_padding=z_padding,
                        )

                    interface = DerivedInterfaceService(
                        uow_factory=self._uow_factory
                    ).create(
                        prototype=built.prototype_uid_full,
                        strain_alpha=alpha,
                        registry_shift_frac_a=translation_frac,
                        z_padding=z_padding,
                    )
                except Exception as exc:
                    results.append(
                        BuildStageResult(
                            prototype_uid=identifier,
                            status="failed",
                            reason=str(exc),
                            run_uid=run_uid,
                        )
                    )
                    n_failed += 1
                    continue

                results.append(
                    BuildStageResult(
                        prototype_uid=identifier,
                        status="built",
                        run_uid=run_uid,
                        derived_interface_uid=interface.uid_full,
                    )
                )
                n_built += 1

            if n_failed:
                self._runs().mark_failed(
                    run_uid,
                    error={
                        "n_requested": len(requested),
                        "n_failed": n_failed,
                        "n_built": n_built,
                        "n_skipped": n_skipped,
                    },
                )
            else:
                self._runs().mark_done(
                    run_uid,
                    progress={
                        "n_requested": len(requested),
                        "n_built": n_built,
                        "n_skipped": n_skipped,
                    },
                )
            return results
        except Exception as exc:
            self._runs().mark_failed(
                run_uid,
                error={"type": type(exc).__name__, "message": str(exc)},
            )
            raise
