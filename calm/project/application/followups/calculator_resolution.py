"""Calculator provenance resolution for followups.

Traces calculator provenance through the chain:
Prototype → Slabs → Bulk → Calculator
"""

from __future__ import annotations

from calm.calculators.exceptions import CalculatorProvenanceError
from calm.calculators.spec import CalculatorSpec

from ...ports.uow import UnitOfWork


def resolve_calculator_from_prototype(
    uow: UnitOfWork, prototype_uid_full: str
) -> CalculatorSpec | None:
    """Resolve calculator from prototype provenance chain.

    Traces: Prototype → Slab → Bulk → Calculator

    Parameters
    ----------
    uow : UnitOfWork
        Unit of work for database access
    prototype_uid_full : str
        Prototype UID (proto:...)

    Returns
    -------
    CalculatorSpec | None
        Calculator spec if bulk was optimized with a calculator, None otherwise

    Raises
    ------
    ValueError
        If prototype or slabs not found
    """
    # 1. Get prototype
    prototype = uow.prototypes.get_by_uid_full(prototype_uid_full)
    if prototype is None:
        raise CalculatorProvenanceError(
            f"Prototype not found while resolving calculator provenance: "
            f"{prototype_uid_full}"
        )

    # 2. Get slab A (could use slab B, both should have same bulk provenance)
    slab = uow.slabs.get_by_uid_full(prototype.slab_a_uid_full)
    if slab is None:
        raise CalculatorProvenanceError(
            f"Slab A not found for prototype {prototype_uid_full}: "
            f"{prototype.slab_a_uid_full}"
        )

    # 3. Get bulk from slab
    bulk = uow.bulks.get_by_uid_full(slab.bulk_uid_full)
    if bulk is None:
        raise CalculatorProvenanceError(
            f"Bulk not found for slab {slab.uid_full}: {slab.bulk_uid_full}"
        )

    # 4. Get calculator from bulk
    if bulk.optimized_with_calculator_uid_full is None:
        # Bulk was not optimized with a calculator (e.g., reference structure)
        return None

    calc_record = uow.calculators.get_by_uid_full(
        bulk.optimized_with_calculator_uid_full
    )
    if calc_record is None:
        raise CalculatorProvenanceError(
            f"Calculator not found: {bulk.optimized_with_calculator_uid_full}"
        )

    # 5. Rehydrate the exact canonical specification persisted with the row.
    return CalculatorSpec.from_dict(calc_record.spec)


def require_calculator_from_prototype(
    uow: UnitOfWork,
    prototype_uid_full: str,
) -> CalculatorSpec:
    """Return the authoritative calculator or fail with provenance context."""

    spec = resolve_calculator_from_prototype(uow, prototype_uid_full)
    if spec is None:
        raise CalculatorProvenanceError(
            "No authoritative calculator provenance is recorded for prototype "
            f"{prototype_uid_full}."
        )
    return spec
