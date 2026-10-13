from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def write_snapshot(tmp_path):
    def write(snapshot_id="01_2026-05-12", taken_on="2026-05-12", pages=None):
        pages = pages if pages is not None else [("https://example.test/rates", "Rates", "# Rates\nA supported fact.")]
        directory = tmp_path / "snapshots" / snapshot_id
        (directory / "pages").mkdir(parents=True)
        manifest = {"snapshot_id": snapshot_id, "taken_on": taken_on, "pages": []}
        for index, (url, title, markdown) in enumerate(pages):
            filename = f"pages/{index}.md"
            (directory / filename).write_text(markdown, encoding="utf-8")
            manifest["pages"].append({"file": filename, "url": url, "title": title, "fetched_at": taken_on})
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return directory.parent
    return write
