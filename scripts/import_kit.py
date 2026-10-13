"""Import the organizer's private kit locally; never publish its data files."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import shutil
import stat
from zipfile import ZipFile, ZipInfo


def safe_member(member: ZipInfo) -> PurePosixPath:
    path = PurePosixPath(member.filename)
    if (path.is_absolute() or ".." in path.parts or "\\" in member.filename
            or stat.S_ISLNK(member.external_attr >> 16)):
        raise ValueError("The kit contains an unsafe archive path or symbolic link.")
    return path


def unpack_archives(destination: Path) -> None:
    snapshots = destination / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    for archive in sorted((destination / "snapshots_zip").glob("*.zip")):
        if (snapshots / archive.stem / "manifest.json").is_file():
            continue
        with ZipFile(archive) as zipped:
            for member in zipped.infolist():
                relative = safe_member(member)
                target = (snapshots / str(relative)).resolve()
                if not target.is_relative_to(snapshots.resolve()):
                    raise ValueError("A snapshot path escapes the destination.")
            zipped.extractall(snapshots)


def import_kit(archive: Path, destination: Path, *, unpack: bool = False) -> int:
    """Copy only official harness/eval/starter files and snapshot archives."""
    with ZipFile(archive) as kit:
        selected = []
        for member in kit.infolist():
            parts = safe_member(member).parts
            if member.is_dir() or len(parts) < 3:
                continue
            relative = PurePosixPath(*parts[1:])
            if relative.parts[0] not in {"harness", "eval", "starter", "snapshots_zip"}:
                continue
            if relative.parts[0] == "snapshots_zip" and (len(relative.parts) != 2 or relative.suffix != ".zip"):
                continue
            target = destination / str(relative)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("A kit path escapes the destination.")
            if relative.as_posix() == "harness/contract.py" and target.exists():
                if target.read_bytes() != kit.read(member):
                    raise ValueError("The supplied contract differs from this prototype; review compatibility before replacing it.")
            selected.append((member, target))
        count = sum(target.parent.name == "snapshots_zip" for _, target in selected)
        if not count:
            raise ValueError("This archive contains no participant snapshots_zip entries.")
        for member, target in selected:
            target.parent.mkdir(parents=True, exist_ok=True)
            with kit.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    if unpack:
        unpack_archives(destination)
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Local kit directory (defaults to the repository root).")
    parser.add_argument("--unpack", action="store_true", help="Also extract snapshots for a read-only container mount.")
    args = parser.parse_args()
    count = import_kit(args.archive, args.destination, unpack=args.unpack)
    print(f"Imported {count} snapshot archives and official evaluator files into {args.destination}.")
