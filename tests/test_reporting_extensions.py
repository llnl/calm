from __future__ import annotations

from calm.public.presentation.reporting import ConsoleReporter, ensure_console_reporter
from test_helpers import CaptureReporter


def test_console_reporter_section_mapping_paths_and_summary(capsys) -> None:
    reporter = ConsoleReporter(enabled=True)

    with reporter.section("demo", foo="bar"):
        reporter.mapping({"a": 1, "b": 2}, title="MapTitle")
        reporter.paths(["one", "two"], title="PathsTitle")
        reporter.summary("finished")

    output = capsys.readouterr().out
    assert "[section] demo" in output
    assert "[info] MapTitle" in output
    assert "- one" in output and "- two" in output
    assert "[summary] finished" in output


def test_ensure_console_reporter_preserves_explicit_reporter() -> None:
    reporter = CaptureReporter()
    assert ensure_console_reporter(reporter) is reporter


def test_ensure_console_reporter_returns_console_default() -> None:
    assert isinstance(ensure_console_reporter(None), ConsoleReporter)
