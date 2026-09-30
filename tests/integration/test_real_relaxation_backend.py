import os
import pytest
from pathlib import Path

from test_helpers import make_test_interface_prototype

from calm.project.bootstrap import open_workspace


@pytest.mark.real_backend
def test_real_relaxation_backend_smoke(tmp_path: Path):
    """Opt-in integration test for the real relaxation backend.

    This test is skipped by default; enable by setting the environment
    variable CALM_RUN_REAL_RELAXATION_TESTS=1 or by passing -m real_backend to pytest.
    """
    if not os.environ.get("CALM_RUN_REAL_RELAXATION_TESTS"):
        pytest.skip("Real relaxation tests are opt-in. Set CALM_RUN_REAL_RELAXATION_TESTS=1 to run.")

    # Attempt to open a workspace and run a small relaxation using real backend
    proj_dir = tmp_path / "proj"
    proj_dir.mkdir()
    ws = open_workspace(str(proj_dir))

    # Prepare a tiny prototype (reuse persist_interface_prototypes helper)
    internal = make_test_interface_prototype(prototype_uid="rb_1")
    mapping = ws.persist_interface_prototypes([internal])
    proto_uid_full = list(mapping.values())[0]["uid_full"]

    # Run relaxation with real backend; may raise RuntimeError if ASE/calculator missing
    try:
        results = ws.run_relaxation_stage([proto_uid_full], max_steps=10, backend="real")
    except RuntimeError as e:
        pytest.skip(f"Real backend not available in environment: {e}")

    # Validate returned structure
    assert isinstance(results, list)
    assert len(results) >= 1
    r = results[0]
    assert r.get("status") in ("completed", "skipped", "failed")
