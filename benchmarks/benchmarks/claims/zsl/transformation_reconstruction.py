"""Reconstruct integer source transformations from retained ZSL vectors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from ..matrix_conventions import (
    TransformationReconstruction,
    integer_transform,
    reconstruct_integer_transform_from_row_vectors,
)
from ..schemas import ProjectedMatch, RawExternalMatch


PROJECTION_KIND = "zsl_integer_source_reconstruction"


def _fields(raw: RawExternalMatch) -> Mapping[str, Any]:
    value = raw.payload.get("fields")
    return value if isinstance(value, Mapping) else {}


def _source_match_id(raw: RawExternalMatch) -> str:
    value = raw.payload.get("source_match_id")
    if not isinstance(value, str) or not value.strip():
        return f"{raw.tool}:{raw.fixture_id}:{raw.raw_index}"
    return value


def _declared_transform_diagnostics(value: Any) -> dict[str, Any]:
    if value is None:
        return {"status": "missing"}
    try:
        row_left = integer_transform(value, name="declared_transformation")
    except (TypeError, ValueError) as exc:
        return {
            "status": "invalid",
            "error": f"{type(exc).__name__}: {exc}",
            "raw": value,
        }

    # pymatgen transforms row-vector matrices by left multiplication. Under
    # CALM's column convention S = A @ N, the same integer map is N = T.T.
    column_right = row_left.T
    determinant = int(round(float(np.linalg.det(column_right))))
    return {
        "status": "valid",
        "pymatgen_row_left_matrix": row_left.tolist(),
        "calm_column_right_matrix": column_right.tolist(),
        "determinant": determinant,
        "source_index": abs(determinant),
        "orientation_sign": 0 if determinant == 0 else (1 if determinant > 0 else -1),
    }


def _reconstruct_side(
    fields: Mapping[str, Any],
    *,
    side: str,
    atol: float,
    rtol: float,
) -> tuple[TransformationReconstruction | None, str | None]:
    primitive_name = f"{side}_vectors"
    supercell_name = f"{side}_sl_vectors"
    if primitive_name not in fields:
        return None, f"missing {primitive_name}"
    if supercell_name not in fields:
        return None, f"missing {supercell_name}"
    try:
        reconstruction = reconstruct_integer_transform_from_row_vectors(
            fields[primitive_name],
            fields[supercell_name],
            atol=atol,
            rtol=rtol,
        )
    except (TypeError, ValueError, np.linalg.LinAlgError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not reconstruction.success:
        return reconstruction, "nearest integer transform failed residual check"
    if reconstruction.determinant == 0:
        return reconstruction, "nearest integer transform is singular"
    return reconstruction, None


def reconstruct_zsl_source_pair(
    raw: RawExternalMatch,
    *,
    atol: float = 1.0e-8,
    rtol: float = 1.0e-8,
) -> ProjectedMatch:
    """Reconstruct film and substrate integer maps without dropping failures."""

    fields = _fields(raw)
    film, film_error = _reconstruct_side(
        fields,
        side="film",
        atol=atol,
        rtol=rtol,
    )
    substrate, substrate_error = _reconstruct_side(
        fields,
        side="substrate",
        atol=atol,
        rtol=rtol,
    )

    failure_reasons = [
        reason
        for reason in (
            f"film: {film_error}" if film_error else None,
            f"substrate: {substrate_error}" if substrate_error else None,
        )
        if reason is not None
    ]
    status = "reconstructed" if not failure_reasons else "failed"

    identity: dict[str, Any] = {}
    if film is not None:
        identity.update(
            {
                "film_integer_matrix": [list(row) for row in film.integer_matrix],
                "film_source_index": film.source_index,
                "film_orientation_sign": film.orientation_sign,
            }
        )
    if substrate is not None:
        identity.update(
            {
                "substrate_integer_matrix": [
                    list(row) for row in substrate.integer_matrix
                ],
                "substrate_source_index": substrate.source_index,
                "substrate_orientation_sign": substrate.orientation_sign,
            }
        )

    declared_film = _declared_transform_diagnostics(
        fields.get("film_transformation")
    )
    declared_substrate = _declared_transform_diagnostics(
        fields.get("substrate_transformation")
    )
    if film is not None and declared_film.get("status") == "valid":
        declared_film["source_index_matches_reconstruction"] = bool(
            declared_film["source_index"] == film.source_index
        )
    if substrate is not None and declared_substrate.get("status") == "valid":
        declared_substrate["source_index_matches_reconstruction"] = bool(
            declared_substrate["source_index"] == substrate.source_index
        )

    diagnostics = {
        "atol": float(atol),
        "rtol": float(rtol),
        "failure_reasons": failure_reasons,
        "film_reconstruction": None if film is None else film.to_dict(),
        "substrate_reconstruction": (
            None if substrate is None else substrate.to_dict()
        ),
        "declared_film_transformation": declared_film,
        "declared_substrate_transformation": declared_substrate,
    }
    return ProjectedMatch(
        source_match_id=_source_match_id(raw),
        projection_kind=PROJECTION_KIND,
        status=status,
        identity=identity,
        diagnostics=diagnostics,
    )
