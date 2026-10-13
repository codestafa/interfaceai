"""Thin HTTP controller: the browser and evaluator use the same knowledge core."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Literal, Protocol

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from server.kit import read_snapshots
from submission.knowledge.adapters.contract import Answer, Conflict, Snapshot
from submission.knowledge.models.domain import QuestionFeedback
from submission.solution import build

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


class Engine(Protocol):
    def ingest(self, snapshot: Snapshot) -> None: ...
    def answer(self, question: str, as_of: str | None = None) -> Answer: ...
    def validate(self, question: str, as_of: str | None = None) -> QuestionFeedback: ...
    def conflicts(self) -> list[Conflict]: ...


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    as_of: date | None = None

    @field_validator("question")
    @classmethod
    def require_nonblank(cls, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Enter a question.")
        return question


@dataclass(frozen=True)
class SnapshotSummary:
    snapshot_id: str
    taken_on: str
    page_count: int


@dataclass
class Runtime:
    state: Literal["loading", "ready", "error"] = "loading"
    snapshots: tuple[SnapshotSummary, ...] = ()
    engine: Engine | None = None
    error: str | None = None
    ready: asyncio.Event = field(default_factory=asyncio.Event)


class AnswerResponse(BaseModel):
    text: str
    sources: list[dict[str, str | None]]
    confident: bool
    conflict_note: str | None
    selected_snapshot_date: str | None
    coverage_note: str | None = None


class ValidationResponse(BaseModel):
    status: Literal['ready', 'needs_info', 'unavailable']
    message: str
    blocking: bool


def _prepare(snapshot_root: Path, engine_factory: Callable[[], Engine]):
    engine = engine_factory()
    summaries = []
    for snapshot in read_snapshots(snapshot_root):
        engine.ingest(snapshot)
        summaries.append(SnapshotSummary(snapshot.snapshot_id, snapshot.taken_on, len(snapshot.pages)))
    return engine, tuple(summaries)


async def _load(runtime: Runtime, snapshot_root: Path, engine_factory: Callable[[], Engine]) -> None:
    try:
        engine, summaries = await asyncio.to_thread(_prepare, snapshot_root, engine_factory)
        # Publish complete state only after every snapshot is ingested.
        runtime.engine, runtime.snapshots = engine, summaries
        runtime.state = "ready"
    except Exception as exc:
        LOGGER.exception("Could not load the snapshot kit")
        runtime.error = str(exc)
        runtime.state = "error"
    finally:
        runtime.ready.set()


def create_app(
    snapshot_root: Path | None = None,
    *,
    engine_factory: Callable[[], Engine] = build,
    static_root: Path | None = None,
) -> FastAPI:
    runtime = Runtime()
    snapshot_root = snapshot_root or Path(os.environ.get("KNOWLEDGE_SNAPSHOTS", ROOT / "snapshots"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loader = asyncio.create_task(_load(runtime, snapshot_root, engine_factory))
        yield
        # Let the bounded loader finish instead of abandoning its worker thread.
        await loader

    app = FastAPI(title="Knowledge Desk", version="0.1.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None)
    app.state.runtime = runtime

    def require_engine() -> Engine:
        if runtime.state != "ready" or runtime.engine is None:
            raise HTTPException(503, detail=runtime.error or "Snapshots are still loading. Please try again shortly.")
        return runtime.engine

    @app.get("/api/status")
    def status():
        return {
            "state": runtime.state,
            "snapshots": [asdict(snapshot) for snapshot in runtime.snapshots],
            "latest_date": runtime.snapshots[-1].taken_on if runtime.snapshots else None,
            "error": runtime.error,
        }

    @app.post("/api/answer", response_model=AnswerResponse)
    def answer(request: QuestionRequest):
        result = require_engine().answer(request.question, request.as_of.isoformat() if request.as_of else None)
        dates = {snapshot.snapshot_id: snapshot.taken_on for snapshot in runtime.snapshots}
        source_dates = [dates[source.snapshot_id] for source in result.sources if source.snapshot_id in dates]
        return {
            **asdict(result),
            "selected_snapshot_date": max(source_dates) if source_dates else None,
            "coverage_note": None,
        }

    @app.post('/api/validate', response_model=ValidationResponse)
    def validate(request: QuestionRequest):
        result = require_engine().validate(request.question, request.as_of.isoformat() if request.as_of else None)
        return asdict(result)

    @app.get("/api/conflicts")
    def conflicts():
        return [asdict(conflict) for conflict in require_engine().conflicts()]

    assets = static_root if static_root is not None else ROOT / "web" / "dist"
    if assets.is_dir():
        app.mount("/", StaticFiles(directory=assets, html=True), name="frontend")
    else:
        @app.get("/")
        def frontend_missing():
            return {"message": "Build the browser app with npm ci && npm run build in web/, then restart the server."}
    return app


app = create_app()
