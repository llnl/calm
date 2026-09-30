from calm.project.infrastructure.db.repos import SqlAlchemyCampaignRepository


def test_workspace_list_and_get_campaign(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    with uow as uu:
        repo = SqlAlchemyCampaignRepository(uu.connection, ids=uu.ids)
        c_uid = "campaign:test:1"
        repo.create_campaign(uid_full=c_uid, name="c1", project_id=None, spec={})
        items = uu.campaigns.list_campaigns()
        assert items
        found = uu.campaigns.get_campaign(c_uid)
        assert found["uid_full"] == c_uid


def test_workspace_campaign_runs_and_provenance(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    with uow as uu:
        repo = SqlAlchemyCampaignRepository(uu.connection, ids=uu.ids)
        c_uid = "campaign:test:2"
        repo.create_campaign(uid_full=c_uid, name="c2", project_id=None, spec={})
        r1 = repo.create_or_get_campaign_run(campaign_uid_full=c_uid, run_spec={"a": 1}, backend_id="b1")
        r2 = repo.create_or_get_campaign_run(campaign_uid_full=c_uid, run_spec={"a": 2}, backend_id="b2")
        runs = repo.list_campaign_runs(campaign_uid_full=c_uid)
        assert len(runs) >= 2
        # ensure get_campaign_run works
        found = repo.get_campaign_run(r1["uid_full"]) if isinstance(r1, dict) else repo.get_campaign_run(r1.uid_full)
        assert found is not None
