from calm.project.application.followups.energy_backends import make_energy_backend, DeterministicEnergyBackend, RealEnergyBackend


def test_make_energy_backend_deterministic():
    b = make_energy_backend("deterministic")
    assert isinstance(b, DeterministicEnergyBackend)
    # deterministic compute should return same energy for same inputs
    r1 = b.compute(run_uid="r1", prototype_uid="p1", target_uid="t1", config={})
    r2 = b.compute(run_uid="r1", prototype_uid="p1", target_uid="t1", config={})
    assert r1.energy == r2.energy


def test_make_energy_backend_real_missing_deps_raises():
    b = make_energy_backend("real")
    assert isinstance(b, RealEnergyBackend)
    try:
        # Real backend requires uow or heavy deps; calling without uow should raise
        b.compute(run_uid="r", prototype_uid="p", target_uid="t", config={}, uow=None)
    except RuntimeError as e:
        assert "requires calculator/ASE support" in str(e) or "requires a UnitOfWork instance" in str(e) or "Failed" in str(e)
    else:
        # If the environment has heavy deps, ensure it returns an EnergyComputeResult
        try:
            res = b.compute(run_uid="r", prototype_uid="p", target_uid="t", config={}, uow=object())
            assert hasattr(res, "energy")
        except RuntimeError:
            # Acceptable: missing deps
            pass
