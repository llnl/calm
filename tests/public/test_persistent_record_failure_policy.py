from __future__ import annotations

import pytest

from calm.public.records.persistence import (
    ProjectRun,
    ProjectSearch,
    RecordAuthority,
    record_authority,
)


def test_record_attribute_failures_do_not_become_missing_fields() -> None:
    class BrokenRun:
        uid_full = "run:test"
        id_short = "r_test"
        run_type = "energy"

        @property
        def status(self):
            raise RuntimeError("status load failed")

    with pytest.raises(RuntimeError, match="status load failed"):
        ProjectRun.from_item(BrokenRun())


def test_record_mapping_adapter_failures_propagate() -> None:
    class BrokenSearch:
        def to_dict(self):
            raise RuntimeError("row conversion failed")

    with pytest.raises(RuntimeError, match="row conversion failed"):
        ProjectSearch.from_item(BrokenSearch())


def test_invalid_explicit_authority_is_not_inferred_away() -> None:
    with pytest.raises(ValueError, match="not a valid RecordAuthority"):
        record_authority({"authority": "historical", "uid_full": "run:test"})

    assert (
        record_authority({"authority": "authoritative"})
        is RecordAuthority.AUTHORITATIVE
    )
