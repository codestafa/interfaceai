"""Immutable domain objects: source evidence stays attached to every claim."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class Evidence:
    url: str
    snapshot_id: str
    quote: str


@dataclass(frozen=True)
class Section:
    heading: str
    text: str


@dataclass(frozen=True)
class Table:
    heading: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    effective_on: date | None = None
    expires_on: date | None = None


@dataclass(frozen=True)
class Document:
    url: str
    title: str
    markdown: str
    sections: tuple[Section, ...]
    tables: tuple[Table, ...]
    snapshot_id: str


@dataclass(frozen=True)
class Fact:
    category: str
    entity: str
    qualifiers: tuple[tuple[str, str], ...]
    values: tuple[tuple[str, str], ...]
    evidence: Evidence
    authority: int
    effective_on: date | None = None
    expires_on: date | None = None

    supporting_evidence: tuple[Evidence, ...] = ()

    def qualifier(self, name: str, default: str = "") -> str:
        return dict(self.qualifiers).get(name, default)

    @property
    def key(self) -> tuple:
        return self.category, self.entity.lower(), self.qualifiers

    def applies_on(self, day: date) -> bool:
        return (self.effective_on is None or self.effective_on <= day) and (self.expires_on is None or day <= self.expires_on)


@dataclass(frozen=True)
class Resolution:
    text: str
    evidence: tuple[Evidence, ...] = ()
    confident: bool = True
    conflict_note: str | None = None


@dataclass(frozen=True)
class QueryIntent:
    question: str
    category: str | None
    term_months: int | None = None
    model_year: int | None = None
    balance: float | None = None
    specific_product: str | None = None
    highest_rate: bool = False
    lowest_rate: bool = False


@dataclass(frozen=True)
class SnapshotState:
    snapshot_id: str
    taken_on: date
    documents: tuple[Document, ...]
    facts: tuple[Fact, ...]
    index: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class QueryContext:
    snapshot: SnapshotState
    requested_on: date
    intent: QueryIntent


@dataclass(frozen=True)
class QuestionFeedback:
    status: Literal['ready', 'needs_info', 'unavailable']
    message: str
    blocking: bool = False


@dataclass(frozen=True)
class Disagreement:
    topic: str
    values: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    resolution: str | None
    reason: str
