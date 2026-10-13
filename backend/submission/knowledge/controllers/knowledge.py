"""Application controller; transport concerns stay outside the knowledge core."""
from __future__ import annotations

from datetime import date

from ..models.domain import QueryContext, QuestionFeedback, Resolution
from ..models.repository import SnapshotRepository
from ..services.financial import answer_financial
from ..services.narrative import answer_narrative, narrative_conflicts
from ..services.query import interpret, question_date
from ..services.query_validation import completeness_feedback, question_issue, requests_forecast
from ..services.resolution import conflict_key, detect_conflicts
from ..services.retrieval import retrieve
from ..views.presenter import present_answer, present_conflict


class KnowledgeController:
    def __init__(self, repository: SnapshotRepository | None = None):
        self.repository = repository or SnapshotRepository()
        self._conflicts = ()

    @property
    def snapshot_dates(self) -> tuple[str, ...]:
        return tuple(state.taken_on.isoformat() for state in self.repository.states)

    def ingest(self, snapshot) -> None:
        self.repository.ingest(snapshot)
        # Historical transitions alone are not conflicts. Keep contradictory claims
        # that coexist in a full snapshot, deduplicated across repeated snapshots.
        inventory = {}
        for state in self.repository.states:
            conflicts = detect_conflicts(state.facts, state.taken_on) + narrative_conflicts(state.documents, state.taken_on)
            for conflict in conflicts:
                inventory[conflict_key(conflict)] = conflict
        self._conflicts = tuple(inventory[key] for key in sorted(inventory))

    def _prepare_query(self, question: str, as_of: str | None = None) -> QueryContext | QuestionFeedback:
        if not isinstance(question, str) or not question.strip():
            return QuestionFeedback('needs_info', 'Please enter a non-empty question.', True)
        if len(question) > 4000:
            return QuestionFeedback('needs_info', 'Please shorten the question to 4,000 characters or fewer.', True)
        states = self.repository.states
        if not states:
            return QuestionFeedback('unavailable', 'No snapshots have been loaded yet.', True)
        try:
            requested = date.fromisoformat(as_of) if as_of else question_date(question) or states[-1].taken_on
        except (ValueError, TypeError) as error:
            message = 'Use a valid as-of date in YYYY-MM-DD format.' if as_of else str(error)
            return QuestionFeedback('needs_info', message, True)
        state = self.repository.select(requested)
        if state is None:
            return QuestionFeedback('unavailable', f'No saved pages are available on or before {requested.isoformat()}. The first snapshot is {states[0].taken_on.isoformat()}.', True)
        issue = question_issue(question)
        if issue:
            return QuestionFeedback('needs_info', issue, True)
        if requested > states[-1].taken_on and requests_forecast(question):
            return QuestionFeedback('unavailable',
                f'I cannot predict future rates or account details. Data coverage ends on {states[-1].taken_on.isoformat()}. Please ask about a date within the available history.',
                True,
            )
        intent = interpret(question)
        if intent.highest_rate and intent.lowest_rate:
            return QuestionFeedback('needs_info', 'Please ask for either the lowest or the highest rate so I can compare one direction.', True)
        feedback = completeness_feedback(intent)
        if feedback.blocking:
            return feedback
        return QueryContext(state, requested, intent)

    def validate(self, question: str, as_of: str | None = None) -> QuestionFeedback:
        context = self._prepare_query(question, as_of)
        if isinstance(context, QuestionFeedback):
            return context
        if context.requested_on > self.repository.states[-1].taken_on:
            return QuestionFeedback('needs_info', f'Saved pages only cover dates through {self.repository.states[-1].taken_on.isoformat()}. Continuing will use the latest available evidence.')
        return completeness_feedback(context.intent)

    def answer(self, question: str, as_of: str | None = None):
        context = self._prepare_query(question, as_of)
        if isinstance(context, QuestionFeedback):
            return present_answer(Resolution(context.message, confident=False))
        state, requested = context.snapshot, context.requested_on
        result = answer_financial(context.intent, state.facts, state.documents, requested)
        if result is None:
            result = answer_narrative(question, state.documents, requested)
        if result is None:
            result = retrieve(question, state)
        latest = self.repository.states[-1].taken_on
        coverage = (f'Data coverage ends on {latest.isoformat()}; this answer uses the latest available snapshot.'
                    if requested > latest else None)
        return present_answer(result, coverage)

    def conflicts(self):
        return [present_conflict(conflict) for conflict in self._conflicts]
