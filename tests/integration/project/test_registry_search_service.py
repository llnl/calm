from calm.project.application.followups.service import FollowupsService


def test_start_registry_search_returns_run_for_missing_prototype(
    sqlite_uow_factory,
) -> None:
    uow = sqlite_uow_factory()
    with uow:
        # No prototypes are inserted; the service should still create and return a run.
        pass

    service = FollowupsService(uow_factory=sqlite_uow_factory)
    run = service.start_registry_search(prototypes=["proto:missing"], n_steps=1)

    assert hasattr(run, "uid_full")
    assert hasattr(run, "id_short")
