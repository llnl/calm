from __future__ import annotations

import pytest

pytest.importorskip("ase")

from calm import CampaignCase, CampaignSettings
from calm.public.project import open_project


def test_failed_campaign_reopens_and_reuses_run_identity(tmp_path) -> None:
    project = open_project(tmp_path)
    campaign = project.create_campaign(
        name="missing_search_campaign",
        cases=[CampaignCase(name="missing", search_name="not_present")],
        settings=CampaignSettings(stages=("search",), on_error="record"),
    )

    first = campaign.run()
    assert first.status == "failed"
    assert len(first.failures) == 1
    first_run_uid = first.run.uid_full

    reopened = open_project(tmp_path)
    persisted = reopened.campaign("missing_search_campaign")
    assert persisted.uid_full == campaign.uid_full
    runs = persisted.runs().records()
    assert len(runs) == 1
    assert runs[0].uid_full == first_run_uid
    assert runs[0].status == "failed"

    second = persisted.run(resume=True)
    assert second.run.uid_full == first_run_uid
    assert second.status == "failed"
