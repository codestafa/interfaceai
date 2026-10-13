from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.import_kit import import_kit


def write_kit(path: Path, *, unsafe_snapshot: bool = False, contract: str = "contract"):
    snapshot = BytesIO()
    with ZipFile(snapshot, "w") as zipped:
        name = "../escaped.txt" if unsafe_snapshot else "01_2026-01-01/manifest.json"
        zipped.writestr(name, '{"pages": []}')
    with ZipFile(path, "w") as kit:
        kit.writestr("participant/snapshots_zip/01_2026-01-01.zip", snapshot.getvalue())
        kit.writestr("participant/harness/contract.py", contract)
        kit.writestr("participant/harness/run_eval.py", "# original evaluator")
        kit.writestr("participant/eval/public_eval.jsonl", "{}")
        kit.writestr("participant/README.md", "Do not replace project documentation")


def test_local_import_preserves_official_files_and_unpacks_for_read_only_mount(tmp_path):
    archive, destination = tmp_path / "kit.zip", tmp_path / "local"
    write_kit(archive)
    assert import_kit(archive, destination, unpack=True) == 1
    assert (destination / "snapshots/01_2026-01-01/manifest.json").is_file()
    assert (destination / "harness/run_eval.py").read_text() == "# original evaluator"
    assert (destination / "eval/public_eval.jsonl").read_text() == "{}"
    assert not (destination / "README.md").exists()
    path = destination / "snapshots/01_2026-01-01/manifest.json"
    timestamp = path.stat().st_mtime_ns
    import_kit(archive, destination, unpack=True)
    assert path.stat().st_mtime_ns == timestamp


def test_import_rejects_different_contract_before_writing(tmp_path):
    archive, destination = tmp_path / "kit.zip", tmp_path / "local"
    write_kit(archive)
    (destination / "harness").mkdir(parents=True)
    (destination / "harness/contract.py").write_text("existing contract")
    with pytest.raises(ValueError, match="contract differs"):
        import_kit(archive, destination)
    assert not (destination / "snapshots_zip").exists()


def test_unpack_rejects_path_traversal(tmp_path):
    archive, destination = tmp_path / "kit.zip", tmp_path / "local"
    write_kit(archive, unsafe_snapshot=True)
    with pytest.raises(ValueError, match="unsafe archive path"):
        import_kit(archive, destination, unpack=True)
    assert not (destination / "escaped.txt").exists()
