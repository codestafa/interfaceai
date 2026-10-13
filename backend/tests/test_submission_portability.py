"""The grader may copy a submission into a folder with a different name."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


def test_submission_loads_from_renamed_folder_outside_project(tmp_path):
    root = Path(__file__).resolve().parents[2]
    team = tmp_path / "renamed_team"
    shutil.copytree(root / "backend" / "submission", team, ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / "harness").mkdir()
    shutil.copy2(root / "harness" / "contract.py", tmp_path / "harness" / "contract.py")
    script = """
import importlib.util
import sys
from pathlib import Path
team = Path(sys.argv[1])
sys.path.insert(0, str(team))
spec = importlib.util.spec_from_file_location('solution', team / 'solution.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
engine = module.build()
from contract import Answer, Snapshot
engine.ingest(Snapshot('empty', '2026-05-12', []))
assert isinstance(engine.answer('What is the auto loan APR?'), Answer)
assert engine.conflicts() == []
"""
    result = subprocess.run([sys.executable, "-c", script, str(team)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
