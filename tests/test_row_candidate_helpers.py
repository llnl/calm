from __future__ import annotations

from calm.public.projections.candidate import normalize_candidate_row


def test_normalize_candidate_row_minimal():
    src = {"candidate_id": "c1", "prototype_uid": "p1", "score": 0.5}
    out = normalize_candidate_row(src)
    assert out["candidate_id"] == "c1"
    assert out["prototype_uid"] == "p1"
    # authoritative ids preserved when present
    src2 = {"candidate_id": "c2", "project_prototype_uid": "uid:abc", "run_uid": "run:1"}
    out2 = normalize_candidate_row(src2)
    assert out2.get("project_prototype_uid") == "uid:abc"
    assert out2.get("run_uid") == "run:1"
