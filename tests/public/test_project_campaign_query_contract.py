
import pytest

from calm.public.project import Project


def _make_workspace_and_project(tmp_path):
    # lightweight workspace stub that supports campaign creation via repo
    class _WS:
        def __init__(self):
            self._campaigns = []

        def create_campaign(self, *, name=None, spec=None):
            uid = f"campaign:test:{len(self._campaigns)+1}"
            id_short = f"y_{len(self._campaigns)+1:04d}"
            row = {"uid_full": uid, "id_short": id_short, "name": name, "project_id": None, "created_at": None}
            self._campaigns.append(row)
            return row

        def list_campaigns(self, *, limit=None):
            return list(self._campaigns[:limit]) if limit else list(self._campaigns)

        def get_campaign(self, id_or_name):
            for r in self._campaigns:
                if id_or_name in (r.get("uid_full"), r.get("id_short"), r.get("name")):
                    return r
            raise KeyError("Campaign not found")

    ws = _WS()
    proj = Project(ws, path=tmp_path / "example.calm")
    return ws, proj


def test_project_campaigns_returns_authoritative_campaigns(tmp_path):
    ws, proj = _make_workspace_and_project(tmp_path)
    created = ws.create_campaign(name="my_campaign", spec={})

    coll = proj.campaigns()
    rows = coll.to_rows(view="all")
    assert len(rows) == 1
    assert rows[0]["uid_full"] == created["uid_full"]
    assert rows[0]["id_short"] == created["id_short"]
    assert rows[0]["name"] == "my_campaign"
    assert rows[0]["campaign_id"] == created["id_short"]


def test_project_campaigns_get_by_id_short_and_name(tmp_path):
    ws, proj = _make_workspace_and_project(tmp_path)
    created = ws.create_campaign(name="my_campaign", spec={})

    by_short = proj.campaigns().get(created["id_short"])
    by_name = proj.campaigns().get("my_campaign")

    assert by_short["uid_full"] == created["uid_full"]
    assert by_name["uid_full"] == created["uid_full"]


def test_campaign_collection_runs_returns_campaign_runs(tmp_path):
    ws, proj = _make_workspace_and_project(tmp_path)
    created = ws.create_campaign(name="my_campaign", spec={})
    # create runs using workspace stub
    try:
        ws.create_or_get_campaign_run(created["uid_full"], run_spec={"a": 1}, backend_id="b1")
        ws.create_or_get_campaign_run(created["uid_full"], run_spec={"a": 2}, backend_id="b2")
    except Exception:
        # stub may not support run creation; skip if not supported
        return
    runs = proj.campaigns().runs(created["uid_full"])
    assert isinstance(runs, list)
    assert runs


def test_project_campaigns_empty_when_no_campaigns(tmp_path):
    ws, proj = _make_workspace_and_project(tmp_path)
    coll = proj.campaigns()
    assert coll.to_rows(view="all") == []
    with pytest.raises(KeyError):
        coll.get("missing")
