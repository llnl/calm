from test_helpers import CaptureReporter
from calm.public.project import open_project
from pathlib import Path


def test_open_project_summarize_false_is_quiet(tmp_path, capsys):
    p = tmp_path / "proj.calm"
    p.mkdir()
    _ = open_project(str(p), summarize=False)
    out = capsys.readouterr().out
    assert out == ""


def test_open_project_reports_summary_to_reporter(tmp_path):
    p = tmp_path / "proj2.calm"
    p.mkdir()
    rep = CaptureReporter()
    _ = open_project(str(p), reporter=rep, summarize=True)

    # Ensure some events were captured: section + summary expected
    kinds = [e.kind for e in rep.events]
    assert "stage_start" in kinds or any(e.kind.startswith("section") or e.kind == "summary" for e in rep.events)
