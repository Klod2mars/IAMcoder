import subprocess
import sys
from pathlib import Path


def test_cli_version_exits_zero_and_prints_version():
    root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, str(root / "main.py"), "version"],
        capture_output=True,
        text=True,
        cwd=str(root),
        check=False,
    )
    assert proc.returncode == 0
    stdout = proc.stdout + proc.stderr
    assert "AIHomeCoder v" in stdout


