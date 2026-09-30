"""Package-owned structures used by CALM's public tutorials."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ase import Atoms

_TUTORIAL_RESOURCES: dict[str, str] = {
    "lif": "lif.json",
    "li2o": "li2o.json",
    "cu": "cu.json",
    "ni": "ni.json",
}


def _tutorial_payload(name: str) -> dict[str, Any]:
    if not isinstance(name, str):
        raise TypeError("tutorial structure name must be a string")
    if name not in _TUTORIAL_RESOURCES:
        available = ", ".join(_TUTORIAL_RESOURCES)
        raise ValueError(
            f"Unknown tutorial structure {name!r}. Available names: {available}."
        )

    resource = files("calm").joinpath(
        "data",
        "tutorials",
        _TUTORIAL_RESOURCES[name],
    )
    try:
        payload = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - installation defect
        raise RuntimeError(
            f"CALM installation is missing tutorial structure {name!r}."
        ) from exc

    from calm.structure.payloads import canonical_atoms_payload

    return canonical_atoms_payload(payload)


def tutorial_structure(name: str) -> "Atoms":
    """Return a fresh ASE ``Atoms`` object for one packaged tutorial structure.

    Parameters
    ----------
    name
        Exact tutorial structure name. Supported values are ``"lif"``,
        ``"li2o"``, ``"cu"``, and ``"ni"``.

    Returns
    -------
    ase.Atoms
        A newly constructed fully periodic bulk structure. Mutating the returned
        object does not change the packaged tutorial resource or later calls.

    Notes
    -----
    The LiF/Li2O pair supports the calculator-free geometry tutorials. The
    Cu/Ni pair supports the ASE EMT workflow tutorial. Tutorial systems are
    chosen to demonstrate CALM operation; they do not establish calculator
    suitability for another material system.
    """

    from calm.structure.payloads import atoms_from_dict

    return atoms_from_dict(_tutorial_payload(name))
