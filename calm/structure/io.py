"""I/O helpers for common calm workflows.

These helpers are intentionally thin wrappers around ASE so that example scripts
and downstream tools can use a stable import path (e.g. ``calm.load_structure``)
without importing ``ase.io`` directly.

The computational kernel does not depend on these functions.

Current I/O behavior
--------------------
- Automatic structure validation on load
- Clear error messages for common failures
- Safe writes with backup and atomic operations
- Verification of written files
"""

from __future__ import annotations

import json
import shutil
import tempfile
import warnings
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    from ase import Atoms
except ImportError:  # pragma: no cover
    Atoms = Any  # type: ignore[assignment, misc]


def _is_vasp_format(format: str | None, path: Path | None) -> bool:
    fmt = (format or "").lower()
    if fmt in {"vasp", "poscar"}:
        return True
    if path is not None:
        suf = str(path).lower()
        if suf.endswith(".vasp") or suf.endswith(".poscar"):
            return True
    return False


def _prepare_atoms_for_write(
    atoms, *, format: str | None = None, path: Path | None = None
):
    """Return an atoms object prepared exactly for the requested format.

    VASP/POSCAR output requires deterministic species-block sorting. Import,
    copy, and sorting failures propagate rather than silently writing a
    differently ordered structure.
    """

    if not _is_vasp_format(format, path):
        return atoms

    from ase.build.tools import sort as ase_sort

    return ase_sort(atoms.copy())


def load_structure(
    path: str | Path,
    *,
    index: int | str = 0,
    format: str | None = None,
    validate: bool = True,
    expected_pbc: Optional[Sequence[bool]] = None,
    min_volume: float = 1e-10,
    **kwargs: Any,
) -> Atoms:
    """Load a structure file into an ASE ``Atoms`` object with validation.

    This function loads a structure file and optionally validates it to ensure
    it meets CALM's requirements. Validation checks for common issues like
    empty structures, zero cell volume, and NaN positions.

    Parameters
    ----------
    path : str or Path
        Path to a structure file supported by ASE (e.g., CIF, POSCAR, XYZ).
    index : int or str, optional
        ASE index selector. Defaults to 0 (first frame).
        Use ':' to load all frames, -1 for last frame, etc.
    format : str, optional
        ASE format override. If None, format is auto-detected from extension.
    validate : bool, optional
        If True (default), validate the loaded structure.
    expected_pbc : list[bool], optional
        Expected periodic boundary conditions (e.g., [True, True, True] for bulk).
        Only used if validate=True.
    min_volume : float, optional
        Minimum cell volume in Å³. Only used if ``validate=True``.
    **kwargs
        Additional arguments forwarded to ``ase.io.read``.

    Returns
    -------
    ase.Atoms
        Loaded and optionally validated structure.

    Raises
    ------
    FileIOError
        If file cannot be found, parsed, or validated.

    Examples
    --------
    >>> from calm import load_structure

    >>> # Basic usage
    >>> atoms = load_structure("structure.cif")

    >>> # Load with validation for bulk structure
    >>> atoms = load_structure(
    ...     "bulk.cif",
    ...     validate=True,
    ...     expected_pbc=[True, True, True]
    ... )

    >>> # Load last frame from trajectory
    >>> atoms = load_structure("trajectory.xyz", index=-1)

    >>> # Skip validation for known-good files
    >>> atoms = load_structure("structure.cif", validate=False)
    """
    from ase.io import read

    from calm.exceptions import FileIOError, InvalidStructureError

    # Convert to Path for better error messages
    path = Path(path)

    # Check file exists
    if not path.exists():
        raise FileIOError(
            f"Structure file not found: {path}\n"
            f"Please check the file path and try again."
        )

    # Check file is readable
    if not path.is_file():
        raise FileIOError(
            f"Path exists but is not a file: {path}\n"
            f"Expected a structure file (CIF, POSCAR, XYZ, etc.)"
        )

    # Attempt to load structure
    try:
        atoms = read(str(path), index=index, format=format, **kwargs)
    except FileNotFoundError:
        # Should have been caught above, but handle anyway
        raise FileIOError(f"Structure file not found: {path}") from None
    except PermissionError as e:
        raise FileIOError(f"Permission denied reading {path}: {e}") from e
    except UnicodeDecodeError as e:
        raise FileIOError(
            f"Failed to decode {path} (invalid UTF-8): {e}\n"
            f"File may be binary or corrupted."
        ) from e
    except KeyError as e:
        # ASE raises KeyError for unknown formats
        raise FileIOError(
            f"Unknown or unsupported file format: {path}\n"
            f"Error: {e}\n"
            f"Supported formats: CIF, POSCAR, VASP, XYZ, PDB, etc.\n"
            f"Try specifying format explicitly: load_structure(..., format='cif')"
        ) from e
    except Exception as e:
        # Catch-all for other parsing errors
        raise FileIOError(
            f"Failed to parse structure file {path}: {e}\n"
            f"File may be corrupted or in an unexpected format."
        ) from e

    # Validate if requested
    if validate:
        try:
            from calm.structure.validation import validate_atoms

            validate_atoms(
                atoms,
                expected_pbc=expected_pbc,
                min_volume=min_volume,
                check_finite_positions=True,
                allow_empty=False,
                context=f"loaded from {path.name}",
            )
        except Exception as e:
            raise InvalidStructureError(
                f"Invalid structure in {path}: {e}\n"
                f"The file was parsed successfully but the structure does not meet CALM's requirements."
            ) from e

    return atoms


def write_structure(
    path: str | Path,
    atoms: Atoms,
    *,
    format: str | None = None,
    **kwargs: Any,
) -> None:
    """Write an ASE ``Atoms`` object to disk.

    This is a thin wrapper around ``ase.io.write`` for basic writes.
    For safer writes with backup and verification, use ``safe_write_structure()``.

    Parameters
    ----------
    path : str or Path
        Output file path.
    atoms : ase.Atoms
        Structure to write.
    format : str, optional
        ASE format override. If None, format is inferred from extension.
    **kwargs
        Additional arguments forwarded to ``ase.io.write``.

    Raises
    ------
    FileIOError
        If write operation fails.

    See Also
    --------
    safe_write_structure : Safer write with backup and verification
    """
    from ase.io import write

    from calm.exceptions import FileIOError

    path = Path(path)

    try:
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare atoms for format-specific pre-processing (e.g., VASP sorting)
        atoms_to_write = _prepare_atoms_for_write(atoms, format=format, path=Path(path))
        # Write structure
        write(str(path), atoms_to_write, format=format, **kwargs)
    except PermissionError as e:
        raise FileIOError(f"Permission denied writing to {path}: {e}") from e
    except OSError as e:
        raise FileIOError(f"Failed to write structure to {path}: {e}") from e
    except Exception as e:
        raise FileIOError(f"Unexpected error writing structure to {path}: {e}") from e


def safe_write_structure(
    path: str | Path,
    atoms: Atoms,
    *,
    format: str | None = None,
    backup: bool = True,
    verify: bool = True,
    validate: bool = True,
    **kwargs: Any,
) -> None:
    """Write structure with backup, atomic operation, and verification.

    This function provides safer structure writes by:
    1. Creating backup of existing file (if requested)
    2. Writing to temporary file first
    3. Validating structure before write (if requested)
    4. Verifying written file by reading back (if requested)
    5. Atomic rename to final location (prevents partial writes)

    Parameters
    ----------
    path : str or Path
        Output file path.
    atoms : ase.Atoms
        Structure to write.
    format : str, optional
        ASE format override. If None, format is inferred from extension.
    backup : bool, optional
        If True (default) and file exists, create .bak backup before overwriting.
    verify : bool, optional
        If True (default), verify write by reading file back and comparing.
    validate : bool, optional
        If True (default), validate structure before writing.
    **kwargs
        Additional arguments forwarded to ``ase.io.write``.

    Raises
    ------
    FileIOError
        If write, backup, or verification fails.
    InvalidStructureError
        If structure validation fails.

    Examples
    --------
    >>> from calm.structure.io import safe_write_structure

    >>> # Basic safe write
    >>> safe_write_structure("output.cif", atoms)

    >>> # Write without backup (overwrite directly)
    >>> safe_write_structure("output.cif", atoms, backup=False)

    >>> # Write without verification (faster)
    >>> safe_write_structure("output.cif", atoms, verify=False)

    >>> # Skip all safety checks (equivalent to write_structure)
    >>> safe_write_structure("output.cif", atoms, backup=False, verify=False, validate=False)
    """
    from ase.io import read, write

    from calm.exceptions import FileIOError, InvalidStructureError

    path = Path(path)

    # Validate structure before writing (optional)
    if validate:
        try:
            from calm.structure.validation import validate_atoms

            validate_atoms(
                atoms,
                check_finite_positions=True,
                allow_empty=False,
                context=f"before writing to {path.name}",
            )
        except Exception as e:
            raise InvalidStructureError(
                f"Cannot write invalid structure to {path}: {e}"
            ) from e

    # Create backup if file exists and backup requested
    backup_path = None
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")

        try:
            shutil.copy2(path, backup_path)
        except Exception as e:
            raise FileIOError(
                f"Failed to create backup at {backup_path}: {e}\n"
                f"Aborting write to prevent data loss."
            ) from e

    # Ensure parent directory exists
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise FileIOError(f"Failed to create directory {path.parent}: {e}") from e

    # Write to temporary file first (atomic operation)
    temp_fd = None
    temp_path = None

    try:
        # Create temp file in same directory (ensures same filesystem for atomic rename)
        temp_fd, temp_path_str = tempfile.mkstemp(
            dir=path.parent, suffix=path.suffix, prefix=".tmp_"
        )
        temp_path = Path(temp_path_str)

        # Close the file descriptor (ASE will open it)
        import os

        os.close(temp_fd)
        temp_fd = None

        # Prepare atoms for format-specific pre-processing (e.g., VASP sorting)
        atoms_to_write = _prepare_atoms_for_write(atoms, format=format, path=path)
        # Write to temp file
        write(str(temp_path), atoms_to_write, format=format, **kwargs)

        # Verify by reading back (optional)
        if verify:
            try:
                atoms_readback = read(str(temp_path), format=format)

                # Basic checks
                if len(atoms_readback) != len(atoms_to_write):
                    raise FileIOError(
                        f"Verification failed: atom count mismatch "
                        f"(wrote {len(atoms_to_write)}, read back {len(atoms_readback)})"
                    )

                # Check positions approximately equal (allow for rounding in file format)
                import numpy as np

                # Compare the written atoms (after pre-processing) to the
                # read-back atoms. Use atoms_to_write rather than original
                # `atoms` to account for format-specific preparations (e.g., sorting).
                pos_diff = np.abs(
                    atoms_to_write.get_positions() - atoms_readback.get_positions()
                )
                max_diff = np.max(pos_diff) if pos_diff.size else 0.0
                if max_diff > 1e-3:  # 0.001 Å tolerance for file round-trip
                    warnings.warn(
                        f"Verification warning: positions differ by up to {max_diff:.6f} Å after write/read. "
                        f"This may be due to precision limits in the file format.",
                        UserWarning,
                    )

            except Exception as e:
                # Clean up temp file
                if temp_path and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass

                # Restore from backup if we made one
                if backup_path and backup_path.exists():
                    try:
                        shutil.move(str(backup_path), str(path))
                    except Exception:
                        pass

                raise FileIOError(
                    f"Verification failed for {path}: {e}\n"
                    f"Write aborted, backup restored (if exists)."
                ) from e

        # Atomic rename (replaces existing file)
        temp_path.replace(path)

        # Success - keep backup if present; user may remove it later

    except FileIOError:
        # Re-raise our own exceptions
        raise
    except Exception as e:
        # Clean up temp file on any error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass  # Ignore cleanup errors

        # Restore from backup if we made one
        if backup_path and backup_path.exists():
            try:
                shutil.move(str(backup_path), str(path))
            except Exception:
                pass  # Ignore restore errors

        raise FileIOError(
            f"Failed to write structure to {path}: {e}\nBackup restored (if exists)."
        ) from e
    finally:
        # Clean up file descriptor if still open
        if temp_fd is not None:
            try:
                import os

                os.close(temp_fd)
            except Exception:
                pass


def write_json(
    path: str | Path,
    obj: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
) -> None:
    """Write an object to a JSON file.

    This is a small convenience helper used throughout the UX surface
    (examples, notebooks, lightweight scripting).

    Parameters
    ----------
    path : str or Path
        Output path.
    obj
        JSON-serializable object.
    indent : int, optional
        Pretty-print indentation level. Defaults to 2.
    sort_keys : bool, optional
        If True, sort keys in dictionaries. Defaults to False.
    ensure_ascii : bool, optional
        If True, escape non-ASCII characters. Defaults to False.

    Raises
    ------
    FileIOError
        If write fails or object is not JSON-serializable.
    """
    from calm.exceptions import FileIOError

    p = Path(path)

    try:
        p.parent.mkdir(parents=True, exist_ok=True)

        with p.open("w", encoding="utf-8") as f:
            json.dump(
                obj, f, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii
            )
            f.write("\n")
    except TypeError as e:
        raise FileIOError(f"Object is not JSON-serializable: {e}") from e
    except Exception as e:
        raise FileIOError(f"Failed to write JSON to {path}: {e}") from e
