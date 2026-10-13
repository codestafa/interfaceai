from __future__ import annotations

from threading import Event

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from submission.knowledge.adapters.contract import Answer, Conflict, Source


class RecordingEngine:
    """A contract fixture that proves HTTP delivery does not rewrite answers."""
    def __init__(self):
        self.snapshots = []
        self.calls = []

    def ingest(self, snapshot):
        self.snapshots.append(snapshot)

    def answer(self, question, as_of=None):
        self.calls.append((question, as_of))
        return Answer("A supported fact.", [Source("https://example.test/rates", self.snapshots[0].snapshot_id, "Evidence.")])

    def conflicts(self):
        return [Conflict("Example", ["old", "new"], [], "new", "Authoritative evidence.")]


def wait_loaded(client, app):
    client.portal.call(app.state.runtime.ready.wait)


def test_api_uses_controller_and_preserves_contract(write_snapshot, tmp_path):
    engine = RecordingEngine()
    app = create_app(write_snapshot(), engine_factory=lambda: engine, static_root=tmp_path / "missing")
    with TestClient(app) as client:
        wait_loaded(client, app)
        status = client.get("/api/status").json()
        assert status["state"] == "ready"
        assert status["latest_date"] == "2026-05-12"
        assert status["snapshots"][0]["page_count"] == 1
        response = client.post("/api/answer", json={"question": "  A question?  ", "as_of": "2026-05-20"})
        assert response.status_code == 200
        result = response.json()
        assert result["text"] == "A supported fact."
        assert result["sources"][0]["quote"] == "Evidence."
        assert result["selected_snapshot_date"] == "2026-05-12"
        assert engine.calls == [("A question?", "2026-05-20")]
        assert client.get("/api/conflicts").json()[0]["resolution"] == "new"


@pytest.mark.parametrize("payload", [
    {"question": " "}, {"question": "x" * 4001},
    {"question": "A question?", "as_of": "2026-02-30"}, {},
])
def test_invalid_questions_get_validation_errors(write_snapshot, payload):
    app = create_app(write_snapshot(), engine_factory=RecordingEngine)
    with TestClient(app) as client:
        assert client.post("/api/answer", json=payload).status_code == 422


def test_loading_does_not_publish_partial_engine(write_snapshot):
    gate = Event()

    class SlowEngine(RecordingEngine):
        def ingest(self, snapshot):
            gate.wait(timeout=10)
            super().ingest(snapshot)

    app = create_app(write_snapshot(), engine_factory=SlowEngine)
    with TestClient(app) as client:
        try:
            assert client.get("/api/status").json()["state"] == "loading"
            assert client.post("/api/answer", json={"question": "Hello"}).status_code == 503
            assert client.get("/api/conflicts").status_code == 503
        finally:
            gate.set()
        wait_loaded(client, app)
        assert client.get("/api/status").json()["state"] == "ready"


def test_missing_data_is_actionable_and_keeps_server_available(tmp_path):
    app = create_app(tmp_path / "missing", engine_factory=RecordingEngine)
    with TestClient(app) as client:
        wait_loaded(client, app)
        status = client.get("/api/status").json()
        assert status["state"] == "error"
        assert "KNOWLEDGE_SNAPSHOTS" in status["error"]
        assert client.post("/api/answer", json={"question": "Hello"}).status_code == 503


def test_built_frontend_is_served_without_shadowing_api(write_snapshot, tmp_path):
    assets = tmp_path / "dist"
    assets.mkdir()
    (assets / "index.html").write_text("<h1>Knowledge Desk</h1>")
    app = create_app(write_snapshot(), engine_factory=RecordingEngine, static_root=assets)
    with TestClient(app) as client:
        assert "Knowledge Desk" in client.get("/").text
        assert client.get("/api/status").status_code == 200
