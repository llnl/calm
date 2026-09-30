from pathlib import Path



def test_orchestrators_reject_entered_uow(tmp_path: Path, sqlite_uow_factory):
    uow = sqlite_uow_factory()
    with uow:
        from calm.project.application.followups.relaxation import RelaxationOrchestrator
        from calm.project.application.followups.registry_search import RegistrySearchOrchestrator
        from calm.project.application.followups.energy import EnergyOrchestrator
        from calm.project.application.followups.strain_scan import StrainPartitionScanOrchestrator

        for cls in (RelaxationOrchestrator, RegistrySearchOrchestrator, EnergyOrchestrator, StrainPartitionScanOrchestrator):
            try:
                raised = False
                cls(uow)
            except Exception:
                raised = True
            assert raised, f"{cls.__name__} must not accept entered UoW"


def test_orchestrators_accept_fresh_non_entered_uow(tmp_path: Path, sqlite_uow_factory):
    uow = sqlite_uow_factory()
    # No enter; construction should succeed. The test owns this deliberately
    # unused UoW, so dispose its engine explicitly rather than leaving a pooled
    # SQLite connection for interpreter teardown.
    from calm.project.application.followups.relaxation import RelaxationOrchestrator
    from calm.project.application.followups.registry_search import RegistrySearchOrchestrator
    from calm.project.application.followups.energy import EnergyOrchestrator
    from calm.project.application.followups.strain_scan import StrainPartitionScanOrchestrator

    try:
        for cls in (
            RelaxationOrchestrator,
            RegistrySearchOrchestrator,
            EnergyOrchestrator,
            StrainPartitionScanOrchestrator,
        ):
            cls(uow)
    finally:
        uow.engine.dispose()


def test_followups_service_rejects_entered_uow_factory() -> None:
    from types import SimpleNamespace

    import pytest

    from calm.project.application.followups.service import FollowupsService

    entered_uow = SimpleNamespace(_depth=1)
    service = FollowupsService(uow_factory=lambda: entered_uow)
    with pytest.raises(ValueError, match="fresh non-entered UnitOfWork"):
        service.start_registry_search(prototypes=["proto:missing"], n_steps=1)


def test_followups_service_accepts_fresh_uow_factory(tmp_path: Path, sqlite_uow_factory):
    from calm.project.application.followups.service import FollowupsService
    # Provide a factory that produces a fresh new UoW instance
    def factory():
        return sqlite_uow_factory()

    svc = FollowupsService(uow_factory=factory)
    run = svc.start_registry_search(prototypes=["proto:missing"], n_steps=1)
    assert hasattr(run, "uid_full")
    assert hasattr(run, "id_short")
