"""Calculator provider implementations and helpers.

This module contains concrete provider implementations for external
calculator backends (MACE, CHGNet, GRACE, LAMMPS) as well as small helper functions
used when adapting user options to third-party constructors.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any

from .exceptions import (
    CalculatorBuildError,
    CalculatorSpecError,
    OptionalDependencyError,
)
from .registry import CalculatorProvider
from .spec import CalculatorSpec


class MACEProvider(CalculatorProvider):
    """Provider for MACE foundation models via `mace.calculators.mace_mp`."""

    DEFAULT_MODEL = "medium-mpa-0"

    VALID_MODELS = {
        "small",
        "medium",
        "large",
        "medium-mpa-0",
        "medium-omat-0",
        "matpes-pbe",
        "matpes-r2scan",
        "small-off",
        "medium-off",
        "large-off",
    }

    @property
    def family(self) -> str:
        return "mace"

    def describe(self) -> str:
        return "MACE foundation model calculators via mace.calculators.mace_mp"

    def required_extras(self) -> tuple[str, ...]:
        return ("mace",)

    def is_available(self) -> bool:
        return importlib.util.find_spec("mace") is not None

    def list_models(self) -> tuple[str, ...]:
        return tuple(sorted(self.VALID_MODELS))

    def create(self, spec: CalculatorSpec) -> Any:
        if not self.is_available():
            raise OptionalDependencyError(
                "MACE is not installed. Install it (e.g. `pip install mace-torch`) to use MACE calculators."
            )

        try:
            from mace.calculators import mace_mp
        except ImportError as exc:
            raise OptionalDependencyError(
                "MACE is installed but CALM could not import "
                "mace.calculators.mace_mp. Install or upgrade `mace-torch`."
            ) from exc

        device = spec.device or "cpu"
        options = spec.options_dict()

        # Guard against ambiguous double-specification.
        if "model" in options:
            raise CalculatorSpecError(
                "MACEProvider does not allow 'model' inside options; use spec.model."
            )
        if "device" in options:
            raise CalculatorSpecError(
                "MACEProvider does not allow 'device' inside options; use spec.device."
            )

        # CALM requests stress by default for MACE-MP calculations.
        options.setdefault("stress", True)

        try:
            return mace_mp(model=spec.model, device=device, **options)
        except TypeError as e:
            raise CalculatorBuildError(
                f"Failed to construct MACE calculator via mace_mp(model={spec.model!r}, device={device!r}). "
                f"Unsupported option keys: {sorted(options)}"
            ) from e


class CHGNetProvider(CalculatorProvider):
    """Provider for CHGNet pretrained models via ``CHGNetCalculator``.

    The provider keeps import-time behavior lightweight: importing CALM only
    registers this provider, while importing CHGNet and loading the requested
    model happens only inside :meth:`create`.
    """

    DEFAULT_MODEL = "0.3.0"

    VALID_MODELS = (
        "0.3.0",
        "0.2.0",
        "r2scan",
    )

    @property
    def family(self) -> str:
        return "chgnet"

    def describe(self) -> str:
        return "CHGNet pretrained models via chgnet.model.dynamics.CHGNetCalculator"

    def required_extras(self) -> tuple[str, ...]:
        return ("chgnet",)

    def is_available(self) -> bool:
        return importlib.util.find_spec("chgnet") is not None

    def list_models(self) -> tuple[str, ...]:
        return self.VALID_MODELS

    def normalize_spec(self, spec: CalculatorSpec) -> CalculatorSpec:
        if spec.model == "default":
            raise CalculatorSpecError(
                f"CHGNet model 'default' is retired; use {self.DEFAULT_MODEL!r}."
            )
        if spec.model not in self.VALID_MODELS:
            raise CalculatorSpecError(
                f"Unsupported CHGNet model {spec.model!r}. "
                f"Supported models are: {', '.join(self.VALID_MODELS)}."
            )
        return spec

    def create(self, spec: CalculatorSpec) -> Any:
        spec = self.normalize_spec(spec)
        if not self.is_available():
            raise OptionalDependencyError(
                "CHGNet is not installed. Install it (e.g. `pip install chgnet`) to use CHGNet calculators."
            )

        try:
            from chgnet.model import CHGNet
            from chgnet.model.dynamics import CHGNetCalculator
        except ImportError as exc:
            raise OptionalDependencyError(
                "CHGNet is installed but CALM could not import CHGNet/CHGNetCalculator. "
                "Install or upgrade the `chgnet` package."
            ) from exc

        options = spec.options_dict()
        for forbidden in ("model", "model_name", "device", "use_device"):
            if forbidden in options:
                raise CalculatorSpecError(
                    f"CHGNetProvider does not allow {forbidden!r} inside options; "
                    "use CalculatorSpec fields instead."
                )

        load_kwargs: dict[str, Any] = {}
        if spec.model:
            load_kwargs["model_name"] = spec.model

        try:
            model = CHGNet.load(**load_kwargs)
        except TypeError as exc:
            raise CalculatorBuildError(
                f"Failed to load CHGNet model {spec.model!r}. "
                "The installed CHGNet version may not support this model name."
            ) from exc

        calc_kwargs = dict(options)
        if spec.device:
            calc_kwargs["use_device"] = spec.device

        try:
            return CHGNetCalculator(model=model, **calc_kwargs)
        except TypeError as exc:
            raise CalculatorBuildError(
                f"Failed to construct CHGNetCalculator for model={spec.model!r}. "
                f"Unsupported option keys: {sorted(options)}"
            ) from exc


class GRACEProvider(CalculatorProvider):
    """Provider for GRACE foundation models via `tensorpotential.calculator.grace_fm`."""

    DEFAULT_MODEL = "GRACE-1L-OMAT"

    VALID_MODELS = {
        "GRACE-1L-OMAT",
        "GRACE-2L-OMAT",
        "GRACE-1L-OAM",
        "GRACE-2L-OAM",
        "GRACE-1L-MP-r6",
        "GRACE-2L-MP-r5",
        "GRACE-2L-MP-r6",
    }

    @property
    def family(self) -> str:
        return "grace"

    def describe(self) -> str:
        return (
            "GRACE foundation model calculators via tensorpotential.calculator.grace_fm"
        )

    def required_extras(self) -> tuple[str, ...]:
        return ("tensorpotential",)

    def is_available(self) -> bool:
        return importlib.util.find_spec("tensorpotential") is not None

    def list_models(self) -> tuple[str, ...]:
        return tuple(sorted(self.VALID_MODELS))

    def create(self, spec: CalculatorSpec) -> Any:
        if not self.is_available():
            raise OptionalDependencyError(
                "GRACE is not installed. Install the tensorpotential package to use GRACE calculators."
            )

        try:
            from tensorpotential.calculator import grace_fm
        except ImportError as exc:
            raise OptionalDependencyError(
                "GRACE is installed but CALM could not import "
                "tensorpotential.calculator.grace_fm. Install or upgrade "
                "`tensorpotential`."
            ) from exc

        options = spec.options_dict()
        if "model" in options:
            raise CalculatorSpecError(
                "GRACEProvider does not allow 'model' inside options; use spec.model."
            )

        # GRACE model construction does not consume CalculatorSpec.device.
        try:
            return grace_fm(spec.model, **options)
        except TypeError as e:
            raise CalculatorBuildError(
                f"Failed to construct GRACE calculator via grace_fm(model={spec.model!r}). "
                f"Unsupported option keys: {sorted(options)}"
            ) from e


def _as_str_list(values: Any) -> list[str]:
    """Normalize a list-ish input into a list[str]."""

    if values is None:
        return []
    if isinstance(values, (str, Path)):
        return [str(values)]
    if isinstance(values, (list, tuple, set)):
        return [str(v) for v in values]
    return [str(values)]


def _validate_kwargs_for_callable(
    callable_obj: Any,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Return ``kwargs`` after rejecting silently unsupported fields.

    ASE constructor signatures can change across versions. CALM must not adapt
    to those changes by dropping requested settings because that would create a
    calculator different from the persisted specification.
    """

    try:
        sig = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return dict(kwargs)

    # If the callable accepts **kwargs, don't filter.
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            return dict(kwargs)

    allowed = set(sig.parameters.keys())
    unsupported = sorted(set(kwargs) - allowed)
    if unsupported:
        raise CalculatorSpecError(
            f"{callable_obj!r} does not accept requested calculator option(s): "
            f"{unsupported}."
        )
    return dict(kwargs)


class LAMMPSProvider(CalculatorProvider):
    """LAMMPS calculators via ASE.

    This provider is intentionally low-level and forwards options directly into
    ASE's LAMMPS calculators.

    Conventions
    -----------
    * ``spec.model`` is treated as a LAMMPS ``pair_style`` (unless ``model`` is
      ``"custom"``).
    * Provide LAMMPS inputs in ``spec.options`` using either:

      - ``parameters``: a dict of LAMMPS key/value inputs (e.g. ``pair_style``,
        ``pair_coeff``), plus any ASE LAMMPS calculator kwargs.
      - Convenience top-level keys like ``pair_style``, ``pair_coeff``,
        ``parameters_file``, and ``files``.

    Backend selection
    -----------------
    By default, CALM uses :class:`ase.calculators.lammpsrun.LAMMPS` (subprocess
    backend). To use the in-process backend, set ``options={"backend": "lib"}``.
    """

    @property
    def family(self) -> str:
        return "lammps"

    def describe(self) -> str:
        return "LAMMPS calculators via ASE (lammpsrun/lammpslib)"

    def required_extras(self) -> tuple[str, ...]:
        # ASE is a core dependency of CALM.
        return ()

    def is_available(self) -> bool:
        return importlib.util.find_spec("ase") is not None and (
            importlib.util.find_spec("ase.calculators.lammpsrun") is not None
            or importlib.util.find_spec("ase.calculators.lammpslib") is not None
        )

    def list_models(self) -> tuple[str, ...]:
        # LAMMPS supports many pair styles; `model` is treated as pair_style.
        return ("custom",)

    def create(self, spec: CalculatorSpec) -> Any:
        if not self.is_available():
            raise OptionalDependencyError(
                "ASE LAMMPS calculator bindings are not available. Install/upgrade ASE."
            )

        options = spec.options_dict()
        backend = options.pop("backend", "run")
        if not isinstance(backend, str):
            raise CalculatorSpecError("LAMMPS option 'backend' must be a string.")

        # Backend-agnostic convenience inputs.
        parameters = options.pop("parameters", {})
        if parameters is None:
            parameters = {}
        if not isinstance(parameters, dict):
            raise CalculatorSpecError("LAMMPS option 'parameters' must be a dict.")

        files = _as_str_list(options.pop("files", []))
        parameters_file = options.pop("parameters_file", None)
        if parameters_file is not None:
            files.extend(_as_str_list(parameters_file))

        # Promote common LAMMPS inputs from options into parameters.
        for key in (
            "pair_style",
            "pair_coeff",
            "units",
            "atom_style",
            "boundary",
            "kspace_style",
            "kspace_modify",
            "neighbor",
            "neigh_modify",
            "special_bonds",
        ):
            if key in options and key in parameters:
                raise CalculatorSpecError(
                    f"LAMMPS option {key!r} is specified both at the top level "
                    "and inside options['parameters']."
                )
            if key in options:
                parameters[key] = options.pop(key)

        # Treat spec.model as the sole pair_style owner unless the explicit
        # custom mode is selected.
        if spec.model and spec.model != "custom":
            if "pair_style" in parameters:
                raise CalculatorSpecError(
                    "LAMMPS pair_style must be specified either by spec.model "
                    "or in options['parameters'], not both. Use model='custom' "
                    "when parameters owns pair_style."
                )
            parameters["pair_style"] = spec.model

        # Normalize pair_coeff to the common ASE format (list[str]).
        if "pair_coeff" in parameters and isinstance(parameters["pair_coeff"], str):
            parameters["pair_coeff"] = [parameters["pair_coeff"]]

        if backend == "run":
            try:
                from ase.calculators.lammpsrun import LAMMPS as _LAMMPS
            except ImportError as exc:
                raise OptionalDependencyError(
                    "ASE does not expose ase.calculators.lammpsrun.LAMMPS. "
                    "Install/upgrade ASE or use backend='lib' if available."
                ) from exc

            init_kwargs: dict[str, Any] = {
                "parameters": parameters,
                "files": files,
                **options,
            }
            init_kwargs = _validate_kwargs_for_callable(_LAMMPS, init_kwargs)
            return _LAMMPS(**init_kwargs)

        if backend == "lib":
            try:
                from ase.calculators.lammpslib import LAMMPSlib as _LAMMPSlib
            except ImportError as exc:
                raise OptionalDependencyError(
                    "ASE does not expose ase.calculators.lammpslib.LAMMPSlib. "
                    "Install/upgrade ASE or use backend='run'."
                ) from exc

            lmpcmds = options.pop("lmpcmds", None)
            if lmpcmds is not None:
                lmpcmds = _as_str_list(lmpcmds)

            init_kwargs = {
                "lmpcmds": lmpcmds,
                "parameters": parameters,
                "files": files,
                **options,
            }
            # Drop None values to avoid noisy kwargs.
            init_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
            init_kwargs = _validate_kwargs_for_callable(_LAMMPSlib, init_kwargs)
            return _LAMMPSlib(**init_kwargs)

        raise CalculatorSpecError(
            f"Unknown LAMMPS backend {backend!r}. Expected exactly 'run' or 'lib'."
        )
