from __future__ import annotations

import json
from zipfile import ZipFile

import pytest

from backend.server.kit import read_snapshots, unpack_snapshots


def test_snapshots_are_complete_and_sorted_by_date(write_snapshot):
    root = write_snapshot("z_older", "2026-05-12")
    write_snapshot("a_newer", "2026-09-28", pages=[])
    older, newer = list(read_snapshots(root))
    assert older.taken_on == "2026-05-12"
    assert len(older.pages) == 1
    assert newer.taken_on == "2026-09-28"
    assert newer.pages == []


def test_manifest_cannot_read_outside_snapshot(write_snapshot, tmp_path):
    root = write_snapshot()
    manifest_path = next(root.glob("*/manifest.json"))
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][0]["file"] = "../../outside.txt"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="escapes"):
        list(read_snapshots(root))


def test_archives_are_unpacked_once(tmp_path):
    archives = tmp_path / "snapshots_zip"
    archives.mkdir()
    with ZipFile(archives / "01_2026-01-01.zip", "w") as archive:
        archive.writestr("01_2026-01-01/manifest.json", json.dumps({
            "snapshot_id": "01_2026-01-01", "taken_on": "2026-01-01", "pages": [],
        }))
    root = tmp_path / "snapshots"
    assert len(list(read_snapshots(root))) == 1
    path = root / "01_2026-01-01" / "manifest.json"
    timestamp = path.stat().st_mtime_ns
    unpack_snapshots(root)
    assert path.stat().st_mtime_ns == timestamp


def test_archive_cannot_escape_snapshot_directory(tmp_path):
    archives = tmp_path / "snapshots_zip"
    archives.mkdir()
    with ZipFile(archives / "bad.zip", "w") as archive:
        archive.writestr("../outside.txt", "untrusted")
    with pytest.raises(ValueError, match="escapes"):
        unpack_snapshots(tmp_path / "snapshots")
    assert not (tmp_path / "outside.txt").exists()
