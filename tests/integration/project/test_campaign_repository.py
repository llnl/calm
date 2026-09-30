from calm.project.infrastructure.db.repos import SqlAlchemyCampaignRepository


def test_campaign_run_determinism(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    with uow as uu:
        repo = SqlAlchemyCampaignRepository(uu.connection, ids=uu.ids)
        # create a campaign
        c_uid = "campaign:test:1"
        repo.create_campaign(uid_full=c_uid, name="test", project_id="p1", spec={"a": 1})

        spec1 = {"targets": [1, 2], "n": 10}
        r1 = repo.create_or_get_campaign_run(
            campaign_uid_full=c_uid,
            run_spec=spec1,
            backend_id="deterministic",
        )
        r2 = repo.create_or_get_campaign_run(
            campaign_uid_full=c_uid,
            run_spec=dict(spec1),
            backend_id="deterministic",
        )
        assert r1["uid_full"] == r2["uid_full"]

        # different backend -> different run
        r3 = repo.create_or_get_campaign_run(
            campaign_uid_full=c_uid,
            run_spec=spec1,
            backend_id="real",
        )
        assert r3["uid_full"] != r1["uid_full"]

        # backend_id None and empty string should normalize to same run
        r4 = repo.create_or_get_campaign_run(
            campaign_uid_full=c_uid,
            run_spec=spec1,
            backend_id=None,
        )
        r5 = repo.create_or_get_campaign_run(
            campaign_uid_full=c_uid,
            run_spec=spec1,
            backend_id="",
        )
        assert r4["uid_full"] == r5["uid_full"]


def test_campaign_run_list_and_get(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    with uow as uu:
        repo = SqlAlchemyCampaignRepository(uu.connection, ids=uu.ids)
        c_uid = "campaign:test:list"
        repo.create_campaign(uid_full=c_uid, name="listtest", project_id="p1", spec={})
        r1 = repo.create_or_get_campaign_run(campaign_uid_full=c_uid, run_spec={"a": 1}, backend_id="b1")
        r2 = repo.create_or_get_campaign_run(campaign_uid_full=c_uid, run_spec={"a": 2}, backend_id="b2")
        runs = repo.list_campaign_runs(campaign_uid_full=c_uid)
        assert len(runs) >= 2
        found = repo.get_campaign_run(r1["uid_full"]) if isinstance(r1, dict) else repo.get_campaign_run(r1.uid_full)
        assert found is not None
