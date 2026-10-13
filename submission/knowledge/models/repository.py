"""Full immutable snapshot states and a content-addressed parsing cache."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib

from .domain import Document, SnapshotState
from ..services.extraction import extract_facts
from ..services.markdown import parse_markdown
from ..services.query import tokens


class SnapshotRepository:
    def __init__(self):
        self._states: dict[str, SnapshotState] = {}
        self._parsed: dict[str, tuple] = {}

    @property
    def states(self) -> tuple[SnapshotState, ...]:
        return tuple(sorted(self._states.values(), key=lambda state: (state.taken_on, state.snapshot_id)))

    def ingest(self, snapshot) -> None:
        taken_on = date.fromisoformat(snapshot.taken_on)
        documents = []
        for page in sorted(snapshot.pages, key=lambda p: p.url):
            digest = hashlib.sha256(page.markdown.encode()).hexdigest()
            if digest not in self._parsed:
                self._parsed[digest] = parse_markdown(page.markdown)
            sections, tables = self._parsed[digest]
            documents.append(Document(page.url, page.title, page.markdown, sections, tables, snapshot.snapshot_id))
        facts = tuple(fact for document in documents for fact in extract_facts(document))
        index = defaultdict(list)
        for i, document in enumerate(documents):
            for token in tokens(document.title + ' ' + ' '.join(section.text for section in document.sections)):
                index[token].append(i)
        state = SnapshotState(snapshot.snapshot_id, taken_on, tuple(documents), facts,
                              {token: tuple(indices) for token, indices in index.items()})
        # Re-ingesting a snapshot replaces its entire state, including removed URLs.
        self._states[snapshot.snapshot_id] = state

    def select(self, day: date) -> SnapshotState | None:
        return next((state for state in reversed(self.states) if state.taken_on <= day), None)
