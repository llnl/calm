"""Surface and structure-export helpers for the public Project facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from calm.structure.io import safe_write_structure
from calm.public.presentation.reporting import ensure_console_reporter


def _material_for_surface_generation(project: Any, material: Any) -> Any:
    from calm.public.inputs.materials import Material

    if isinstance(material, str):
        return project.material(material)
    if isinstance(material, Material):
        return material
    return Material.from_workspace(material)


def _persist_surface_material(project: Any, material: Any, reporter: Any) -> Any:
    if getattr(material, "id_short", None):
        return material

    to_ase = getattr(material, "to_ase", None)
    atoms = to_ase() if callable(to_ase) else None
    if atoms is None:
        raise ValueError(
            "Material must be persisted to the project before generating "
            "surfaces (missing id_short)"
        )

    reporter.info(
        "Material has no id_short: saving material to project before "
        "generating surfaces"
    )
    saved = project.add_material(
        material,
        name=getattr(material, "label", None) or getattr(material, "name", None),
    )
    from calm.public.inputs.materials import Material

    return Material.from_workspace(saved)


def _require_atomistic_parent_bulk(project: Any, material: Any) -> Any:
    """Return the authoritative parent bulk after atomistic preflight validation."""

    identifier = getattr(material, "id_short", None)
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(
            "Surface generation requires a persisted material with id_short."
        )
    try:
        persisted = project._adapter.get_bulk(identifier)
    except (AttributeError, KeyError) as exc:
        raise ValueError(
            f"Persisted parent material could not be resolved: {identifier!r}."
        ) from exc

    payload = getattr(persisted, "payload", None)
    atoms = payload.get("atoms") if isinstance(payload, dict) else None
    if not isinstance(atoms, dict):
        raise ValueError(
            "Surface generation requires an authoritative atomistic parent "
            f"material; {identifier!r} has no current atoms payload."
        )
    return persisted


def _missing_atom_payloads(slabs: list[Any]) -> list[str | None]:
    missing: list[str | None] = []
    for slab in slabs:
        atoms = getattr(slab, "atoms", None)
        if atoms is None:
            atoms = getattr(slab, "atoms_conventional", None)
        payload = getattr(slab, "payload", None)
        structure = payload.get("structure") if isinstance(payload, dict) else None
        payload_atoms = structure.get("atoms") if isinstance(structure, dict) else None
        if atoms is None and payload_atoms is None:
            missing.append(getattr(slab, "id_short", None) or getattr(slab, "id", None))
    return missing


def generate_surfaces(
    project: Any,
    material: str | Any | list[Any],
    *,
    millers: list[tuple[int, int, int]],
    layers: int | None = None,
    thickness: float | None = None,
    vacuum: float | None = None,
    enumerate_terminations: bool = True,
    reporter: Any | None = None,
) -> list[Any]:
    """Generate persisted surfaces and return canonical public surface records."""
    rep = ensure_console_reporter(reporter)

    if isinstance(material, (list, tuple)):
        slabs: list[Any] = []
        for item in material:
            slabs.extend(
                generate_surfaces(
                    project,
                    item,
                    millers=millers,
                    layers=layers,
                    thickness=thickness,
                    vacuum=vacuum,
                    enumerate_terminations=enumerate_terminations,
                    reporter=rep,
                )
            )
        return slabs

    public_material = _material_for_surface_generation(project, material)
    public_material = _persist_surface_material(project, public_material, rep)

    millers_exact = [tuple(int(value) for value in miller) for miller in millers]
    params: dict[str, Any] = {}
    if layers is not None:
        params["layers"] = int(layers)
    if thickness is not None:
        params["target_width"] = float(thickness)
    if vacuum is not None:
        params["vacuum"] = float(vacuum)

    _require_atomistic_parent_bulk(project, public_material)

    label = (
        getattr(public_material, "label", None)
        or getattr(public_material, "name", None)
        or getattr(public_material, "id_short", None)
        or str(public_material)
    )
    with rep.stage(f"Generate surfaces: {label}", millers=millers_exact):
        rep.info(
            "Miller indices: " + ", ".join(str(miller) for miller in millers_exact)
        )
        slabs = list(
            project._adapter.build_slabs(
                public_material.id_short,
                millers=millers_exact,
                params=params or None,
                enumerate_terminations=bool(enumerate_terminations),
            )
        )
        missing = _missing_atom_payloads(slabs)
        if missing:
            raise RuntimeError(
                "Surface construction returned non-materialized slab records: "
                f"{missing}."
            )
        from calm.public.records.generated_surface import GeneratedSurface

        surfaces = [
            GeneratedSurface.from_workspace(
                slab,
                workspace=project._workspace,
            )
            for slab in slabs
        ]
        rep.info(f"Generated {len(surfaces)} surfaces for {label}")
    return surfaces


def _surface_filename(surface: Any, default_name: str, *, format: str) -> str:
    material = str(
        getattr(surface, "material", None)
        or getattr(surface, "label", None)
        or default_name
    ).replace(" ", "_")
    miller = getattr(surface, "miller", None)
    miller_text = "" if miller is None else "_" + "".join(str(int(x)) for x in miller)
    identity = str(
        getattr(surface, "id_short", None)
        or getattr(surface, "uid_full", None)
        or default_name
    ).replace("/", "_")
    suffix = ".vasp" if format in {"vasp", "poscar"} else f".{format}"
    return f"{material}{miller_text}_{identity}{suffix}"


def export_surfaces(
    project: Any,
    *ids_or_names: str,
    directory: str | Path,
    format: str = "vasp",
    materials: list[str] | None = None,
    millers: list[tuple[int, int, int]] | None = None,
    reporter: Any | None = None,
) -> list[Path]:
    """Export exact authoritative surface selections."""
    if ids_or_names and (materials is not None or millers is not None):
        raise TypeError(
            "export_surfaces() accepts explicit identifiers or material/Miller "
            "criteria, not both."
        )
    if not ids_or_names and materials is None and millers is None:
        raise ValueError(
            "export_surfaces() requires identifiers or selection criteria."
        )

    collection = project.surfaces(include_empty=True)
    if ids_or_names:
        surfaces = [collection.get(identifier) for identifier in ids_or_names]
        requested = [str(identifier) for identifier in ids_or_names]
    else:
        material_set = {str(value).casefold() for value in (materials or [])}
        miller_set = {tuple(int(x) for x in value) for value in (millers or [])}
        surfaces = []
        for surface in collection.records():
            if material_set:
                values = {
                    str(value).casefold()
                    for value in (
                        getattr(surface, "material", None),
                        getattr(surface, "bulk_id_short", None),
                        getattr(surface, "bulk_uid_full", None),
                    )
                    if value not in (None, "")
                }
                if not values.intersection(material_set):
                    continue
            if miller_set:
                value = getattr(surface, "miller", None)
                if value is None or tuple(int(x) for x in value) not in miller_set:
                    continue
            surfaces.append(surface)
        requested = [
            str(
                getattr(surface, "id_short", None) or getattr(surface, "uid_full", None)
            )
            for surface in surfaces
        ]
        if not surfaces:
            raise KeyError("No authoritative surfaces matched the export criteria.")

    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    rep = ensure_console_reporter(reporter)
    written: list[Path] = []
    with rep.stage("export_surfaces", directory=str(output)):
        for requested_name, surface in zip(requested, surfaces, strict=True):
            atoms = surface.to_ase()
            if atoms is None:
                raise ValueError(
                    f"Surface {requested_name!r} has no authoritative atomistic payload."
                )
            path = output / _surface_filename(surface, requested_name, format=format)
            safe_write_structure(path, atoms, format=format)
            transforms = getattr(getattr(surface, "_object", None), "transforms", None)
            if transforms is not None:
                from calm.slab.oriented.sidecar import write_transforms_sidecar

                write_transforms_sidecar(path, transforms)
            written.append(path)
        rep.mapping(
            {"n_requested": len(requested), "n_written": len(written)},
            title="Export surfaces summary",
        )
        rep.paths([str(path) for path in written], title="Written files")

    import json

    summary = {"requested": requested, "written": [str(path) for path in written]}
    (output / "export_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return written


def export_materials(
    project: Any,
    *names: str,
    directory: str | Path,
    format: str = "vasp",
    reporter: Any | None = None,
) -> list[Path]:
    """Export exact authoritative materials by supported identifier or label."""
    if not names:
        raise ValueError("export_materials() requires at least one material.")
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    rep = ensure_console_reporter(reporter)
    written: list[Path] = []
    with rep.stage("export_materials", directory=str(output)):
        for name in names:
            material = project.material(name)
            label = material.label or material.name or material.id_short or str(name)
            written.append(
                material.to_file(output / str(label).replace(" ", "_"), format=format)
            )
        rep.mapping(
            {"n_requested": len(names), "n_written": len(written)},
            title="Export materials summary",
        )
        rep.paths([str(path) for path in written], title="Written files")
    return written


def surface(
    project: Any,
    id_or_name: str | None = None,
    *,
    material: Any | None = None,
    miller: tuple[int, int, int] | None = None,
    termination: str | None = None,
    termination_top: str | None = None,
    termination_bottom: str | None = None,
    termination_shift: int | None = None,
):
    """Resolve exactly one persisted generated surface.

    Direct identifiers and scientific-identity filters are intentionally
    separate contracts. Passing both is rejected so no selector is silently
    ignored.
    """
    filters_used = any(
        value is not None
        for value in (
            material,
            miller,
            termination,
            termination_top,
            termination_bottom,
            termination_shift,
        )
    )
    if id_or_name is not None:
        if filters_used:
            raise TypeError(
                "surface() accepts either id_or_name or material/Miller/"
                "termination filters, not both"
            )
        return project.surfaces(include_empty=True).get(id_or_name)

    if material is None or miller is None:
        raise TypeError("surface() requires id_or_name or both material and miller")

    selected = project.surfaces(
        material=material,
        miller=miller,
        termination=termination,
        termination_top=termination_top,
        termination_bottom=termination_bottom,
        termination_shift=termination_shift,
    )
    selection = (
        f"material={material!r}, miller={tuple(miller)!r}, "
        f"termination={termination!r}, "
        f"termination_top={termination_top!r}, "
        f"termination_bottom={termination_bottom!r}, "
        f"termination_shift={termination_shift!r}"
    )
    return selected.one(selection=selection)
