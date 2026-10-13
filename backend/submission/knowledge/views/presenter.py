"""Shared deterministic presentation for the evaluator and browser controller."""
from ..adapters.contract import Answer, Conflict, Source
from ..models.domain import Disagreement, Resolution


def present_answer(result: Resolution, coverage_note: str | None = None) -> Answer:
    text = result.text + ('\n' + coverage_note if coverage_note else '')
    return Answer(text, [Source(e.url, e.snapshot_id, e.quote[:1600]) for e in result.evidence],
                  result.confident, result.conflict_note)


def present_conflict(conflict: Disagreement) -> Conflict:
    return Conflict(conflict.topic, list(conflict.values),
                    [Source(e.url, e.snapshot_id, e.quote[:800]) for e in conflict.evidence],
                    conflict.resolution, conflict.reason)
