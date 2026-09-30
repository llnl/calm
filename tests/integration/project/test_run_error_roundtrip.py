from calm.project.infrastructure.db.tables import runs as runs_t
import json


def test_run_error_roundtrip(tmp_path, schema_uow_factory):
    uow = schema_uow_factory()
    err = {"n_failed": 1, "msg": "x"}
    with uow as uu:
        uu.connection.execute(runs_t.insert().values(uid_full="run:1", id_short="r1", run_type="test", status="done", spec_json=json.dumps({}), error_json=json.dumps(err)))
    with uow as uu:
        run = uu.runs.get_by_uid_full("run:1")
        assert run is not None
        assert isinstance(run.error, dict)
        assert run.error.get("n_failed") == 1
