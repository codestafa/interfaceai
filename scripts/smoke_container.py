"""Build-independent Docker smoke test using only generated, synthetic evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def docker(*arguments: str) -> str:
    return subprocess.run(["docker", *arguments], check=True, capture_output=True,
                          text=True, timeout=60).stdout.strip()


def request(base: str, path: str, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        body = response.read().decode()
        return json.loads(body) if "application/json" in response.headers.get("Content-Type", "") else body


def smoke(image: str) -> None:
    name = f"knowledge-smoke-{uuid.uuid4().hex[:10]}"
    with tempfile.TemporaryDirectory(prefix="knowledge-smoke-") as directory:
        data = Path(directory)
        data.chmod(0o755)
        snapshot = data / "01_2026-01-01"
        (snapshot / "pages").mkdir(parents=True)
        (snapshot / "pages/rates.md").write_text(
            "# Auto Loans\n## Rates\n"
            "| Loan Program | Term | Annual Percentage Rate (As Low As) |\n"
            "| --- | --- | --- |\n| 2024-27 Model Year | 60 Months | 5.67% APR |\n")
        (snapshot / "manifest.json").write_text(json.dumps({
            "snapshot_id": snapshot.name, "taken_on": "2026-01-01", "pages": [{
                "url": "https://example.test/personal/loans/auto-loans/", "title": "Auto Loans",
                "file": "pages/rates.md", "fetched_at": "2026-01-01",
            }],
        }))
        try:
            docker("run", "--detach", "--rm", "--name", name, "--read-only", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp:size=16m",
                   "--publish", "127.0.0.1::8000", "--mount",
                   f"type=bind,source={data},target=/data/snapshots,readonly", image)
            base = "http://" + docker("port", name, "8000/tcp").splitlines()[0]
            deadline = time.monotonic() + 60
            while True:
                try:
                    status = request(base, "/api/status")
                    if status["state"] == "error":
                        raise AssertionError("Synthetic snapshots failed to load")
                    if status["state"] == "ready":
                        break
                except (urllib.error.URLError, ConnectionError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("Container did not become ready within 60 seconds")
                time.sleep(0.5)
            assert len(status["snapshots"]) == 1
            html = request(base, "/")
            asset = re.search(r'src="(/assets/[^\"]+\.js)"', html)
            assert asset and request(base, asset.group(1)), "Compiled frontend asset missing"
            answer = request(base, "/api/answer", {
                "question": "What is the APR for a 60-month auto loan on a 2025 model-year vehicle?",
            })
            assert answer["confident"] and "5.67%" in answer["text"], answer["text"]
            assert answer["sources"][0]["url"].startswith("https://example.test/")
            feedback = request(base, "/api/validate", {"question": "What is the rate on a car loan?"})
            assert feedback["status"] == "needs_info" and not feedback["blocking"]
            assert request(base, "/api/conflicts") == []
            docker("exec", name, "python", "-c",
                   "import os; from pathlib import Path; assert os.getuid() != 0; "
                   "assert all(not Path('/app', p).exists() for p in "
                   "['eval', 'snapshots', 'snapshots_zip', 'results', '.env', '.git', 'starter']); "
                   "assert sorted(p.name for p in Path('/app/harness').iterdir()) == ['contract.py']")
            print("Container passed: frontend assets, readiness, answer, guidance, conflicts, nonroot runtime, and private-data exclusion.")
        finally:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="knowledge-desk:local")
    smoke(parser.parse_args().image)
