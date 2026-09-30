from __future__ import annotations


def test_dataset_repository_get_and_list_are_authoritative(schema_uow_factory):
    uow = schema_uow_factory()
    try:
        with uow as active:
            created = active.datasets.create_dataset(
                uid_full="dataset:phase1",
                name="phase1",
                description="typed query contract",
                metadata={"schema_version": 1},
            )
            active.datasets.create_dataset(
                uid_full="dataset:phase1:second",
                name="second",
            )

            fetched = active.datasets.get_dataset(created.uid_full)
            listed = active.datasets.list_datasets()
            limited = active.datasets.list_datasets(limit=1)
    finally:
        uow.engine.dispose()

    assert fetched is not None
    assert fetched.uid_full == "dataset:phase1"
    assert fetched.name == "phase1"
    assert fetched.metadata == {"schema_version": 1}
    assert {dataset.uid_full for dataset in listed} == {
        "dataset:phase1",
        "dataset:phase1:second",
    }
    assert len(limited) == 1
