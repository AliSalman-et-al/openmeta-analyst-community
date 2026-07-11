import subprocess
import sys
from pathlib import Path


def test_forest_plot_defaults_are_generated_from_shared_contract():
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, "scripts/generate_forest_plot_defaults.py", "--check"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
