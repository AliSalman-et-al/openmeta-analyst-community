"""Keep workflow and script callers aligned with the application command surface."""

from scripts.check_script_contracts import ROOT, stale_calls


def test_scripts_use_supported_automation_commands():
    assert stale_calls(ROOT) == []
