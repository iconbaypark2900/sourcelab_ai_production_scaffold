from pathlib import Path

from sourcelab.harness.release_gate import verify_release


def test_release_gate_passes_for_scaffold():
    report = verify_release(Path.cwd())
    assert report["status"] == "PASS", report
