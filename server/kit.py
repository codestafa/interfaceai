"""Read the participant kit without importing or changing its evaluator."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator
from zipfile import ZipFile

from submission.knowledge.adapters.contract import Page, Snapshot


def _inside(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Snapshot path escapes its directory: {relative}")
    return target


def unpack_snapshots(root: Path) -> None:
    """Unpack supplied archives when their matching manifest is absent."""
    archive_root = root.parent / "snapshots_zip"
    for archive in sorted(archive_root.glob("*.zip")):
        if (root / archive.stem / "manifest.json").is_file():
            continue
        root.mkdir(parents=True, exist_ok=True)
        with ZipFile(archive) as zipped:
            for item in zipped.infolist():
                _inside(root, item.filename)
            zipped.extractall(root)


def read_snapshots(root: Path) -> Iterator[Snapshot]:
    """Yield full snapshots in date order; retain each manifest's membership."""
    unpack_snapshots(root)
    manifests = []
    for path in root.glob("*/manifest.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests.append((manifest["taken_on"], path.parent, manifest))
    if not manifests:
        raise FileNotFoundError(
            "No snapshots found. Put the supplied snapshots_zip folder beside "
            "snapshots, or set KNOWLEDGE_SNAPSHOTS to the extracted snapshot directory."
        )
    for _, directory, manifest in sorted(manifests, key=lambda item: item[0]):
        pages = [
            Page(
                url=page["url"],
                title=page.get("title", ""),
                markdown=_inside(directory, page["file"]).read_text(encoding="utf-8"),
                fetched_at=page.get("fetched_at", manifest["taken_on"]),
            )
            for page in manifest["pages"]
        ]
        yield Snapshot(manifest["snapshot_id"], manifest["taken_on"], pages)
