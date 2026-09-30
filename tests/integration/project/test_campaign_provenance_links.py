from calm.project.application.campaigns import CampaignService


def test_campaign_run_emits_run_of_campaign_and_dataset_links(
    tmp_path,
    schema_uow_factory,
):
    service = CampaignService(uow_factory=schema_uow_factory)
    campaign = service.create_or_get(name="c1", spec={})
    run = service.create_or_get_run(
        campaign.uid_full,
        run_spec={"a": 1},
        backend_id="deterministic",
    )

    with schema_uow_factory() as uow:
        edges = uow.edges.list(
            src_uid_full=run.uid_full,
            kind="run_of_campaign",
        )
        assert any(edge.dst_uid_full == campaign.uid_full for edge in edges)

        dataset_uid = "dataset:test:link"
        uow.datasets.create_dataset(uid_full=dataset_uid, name="ds1")
        uow.edges.add(
            src_uid_full=dataset_uid,
            dst_uid_full=campaign.uid_full,
            kind="belonged_to_campaign",
            payload={"campaign_uid_full": campaign.uid_full},
        )
        uow.edges.add(
            src_uid_full=dataset_uid,
            dst_uid_full=run.uid_full,
            kind="produced_by",
            payload={"campaign_run_uid_full": run.uid_full},
        )

        belonged = uow.edges.list(
            src_uid_full=dataset_uid,
            kind="belonged_to_campaign",
        )
        produced = uow.edges.list(
            src_uid_full=dataset_uid,
            kind="produced_by",
        )
        assert belonged[0].payload.get("campaign_uid_full") == campaign.uid_full
        assert produced[0].payload.get("campaign_run_uid_full") == run.uid_full
