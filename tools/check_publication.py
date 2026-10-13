#!/usr/bin/env python3
"""Reject private inputs and likely credentials in the exact Git content to publish.

Run before committing with --index, or inspect a commit with --ref HEAD. Findings
contain only a path, line number, and rule name; matched values are never printed.
This conservative check supplements review and is not a universal secret scanner.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


PRIVATE_DIRECTORIES = {
    "snapshots", "snapshots_zip", "eval", "starter", "results", "secrets",
    "credentials", "node_modules", "dist", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".aws", ".ssh", "tmp", "data", "local-data",
    ".local-data", ".codex", ".agents",
}
PRIVATE_SUFFIXES = {
    ".zip", ".gz", ".tgz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".pem", ".key", ".p12", ".pfx", ".jks", ".pyc", ".pyo",
    ".sqlite", ".sqlite3", ".db", ".pdf",
}
PRIVATE_NAME = re.compile(
    r"(?:^|[._-])(?:credentials?|secrets?|private[._-]?key|transcript|assignment)"
    r"(?:[._-]|$)|^id_(?:rsa|dsa|ecdsa|ed25519)(?:\.|$)", re.IGNORECASE,
)
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("API token", re.compile(r"\bsk-(?:proj-|ant-api\d+-)?[A-Za-z0-9_-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("credential in URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@", re.IGNORECASE)),
)
SECRET_NAME = (
    r"(?:[A-Za-z_][A-Za-z0-9_.-]*)?(?:api[_-]?key|password|passwd|secret|"
    r"client[_-]?secret|access[_-]?token|auth[_-]?token|secret[_-]?key|private[_-]?key|"
    r"(?:github|gh|gitlab|slack|npm)[_-]?token|aws[_-]?secret[_-]?access[_-]?key)"
)
SECRET_ASSIGNMENT = re.compile(
    rf"[\"']?{SECRET_NAME}[\"']?\s*[:=]\s*"
    r"(?P<quote>[\"'])(?P<value>[^\"'\r\n]+)(?P=quote)", re.IGNORECASE,
)
UNQUOTED_ASSIGNMENT = re.compile(
    rf"^\s*(?:export\s+)?{SECRET_NAME}\s*[:=]\s*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9_./+=:@-]{5,})\s*(?:#.*)?$", re.IGNORECASE,
)
SAFE_PLACEHOLDERS = {"example", "placeholder", "changeme", "change_me", "replace_me", "redacted"}
MAX_BLOB_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    line: int | None = None

    def describe(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{location}: {self.rule}"


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        # Git diagnostics may include remote credentials, so do not relay stderr.
        raise RuntimeError("Unable to read Git content; verify the repository and requested revision.")
    return result.stdout


def private_path(path: str) -> bool:
    normalized = PurePosixPath(path.lower())
    parts = normalized.parts
    if any(part in PRIVATE_DIRECTORIES or part.startswith((".venv", "venv")) for part in parts[:-1]):
        return True
    if "harness" in parts and path != "backend/harness/contract.py":
        return True
    if normalized.name.startswith(".env") and normalized.name != ".env.example":
        return True
    return normalized.suffix in PRIVATE_SUFFIXES or bool(PRIVATE_NAME.search(normalized.name))


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized in SAFE_PLACEHOLDERS
        or bool(re.fullmatch(r"(?:your_[a-z_]+_here|<[^<>]+>|\$\{[A-Z_][A-Z0-9_]*\})", value, re.IGNORECASE))
    )


def content_findings(path: str, data: bytes) -> list[Finding]:
    if len(data) > MAX_BLOB_BYTES:
        return [Finding(path, "file exceeds the publication size limit (2 MiB)")]
    text = data.decode("utf-8", errors="replace")
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(Finding(path, label, line_number))
        for pattern in (SECRET_ASSIGNMENT, UNQUOTED_ASSIGNMENT):
            for match in pattern.finditer(line):
                if not is_placeholder(match["value"]):
                    findings.append(Finding(path, "literal credential assignment", line_number))
        if PurePosixPath(path).name == ".env.example":
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            _, separator, value = stripped.partition("=")
            if not separator or (value.strip().strip("\"'") and not is_placeholder(value.strip().strip("\"'"))):
                findings.append(Finding(path, "environment example must contain only placeholders", line_number))
    return findings


def inspect(repo: Path, ref: str | None = None) -> tuple[int, list[Finding]]:
    """Scan index blobs (not working files), or every blob in a commit tree."""
    entries = git(repo, "ls-tree", "-r", "-z", ref) if ref else git(repo, "ls-files", "--stage", "-z")
    findings = []
    count = 0
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8", errors="replace")
        mode, middle, last = metadata.decode("ascii").split()
        count += 1
        if private_path(path):
            findings.append(Finding(path, "private data or generated artifact must not be published"))
            continue
        if mode != "100644" and mode != "100755":
            findings.append(Finding(path, "only regular files may be published"))
            continue
        if not ref and last != "0":
            findings.append(Finding(path, "unresolved index entry"))
            continue
        # Blob IDs avoid path ambiguity and ensure scanning the content Git will publish.
        blob_id = last if ref else middle
        findings.extend(content_findings(path, git(repo, "cat-file", "blob", blob_id)))
    return count, findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--index", action="store_true", help="scan all index entries (default)")
    scope.add_argument("--ref", help="scan the complete tree at a revision, such as HEAD")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        count, findings = inspect(args.repo, args.ref)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2
    if findings:
        print("Publication blocked:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding.describe()}", file=sys.stderr)
        return 1
    print(f"Publication check passed for {count} Git files ({args.ref or 'index'}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
