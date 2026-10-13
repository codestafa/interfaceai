import pytest

from fastapi.testclient import TestClient

from backend.server.app import create_app
from backend.submission.knowledge.adapters.contract import Snapshot
from backend.submission.solution import build


def engine():
    instance = build()
    instance.ingest(Snapshot('first', '2026-05-12', []))
    instance.ingest(Snapshot('latest', '2026-09-28', []))
    return instance


@pytest.mark.parametrize('question, detail', [
    ('What is the rate on a car loan?', 'model year'),
    ('What is the rate on a 60-month auto loan?', 'model year'),
    ('What is the rate on a 2025 vehicle?', 'loan term'),
    ('What is the mortgage rate?', 'loan amount'),
    ('What is the highest account interest rate?', 'amount'),
])
def test_missing_qualifiers_produce_optional_specific_hints(question, detail):
    feedback = engine().validate(question)
    assert feedback.status == 'needs_info' and not feedback.blocking
    assert detail in feedback.message


@pytest.mark.parametrize('question', [
    'What is the APR for a 60-month auto loan on a 2025 model-year vehicle?',
    'List all auto loan rates.',
    'What is the lowest APR for a 2025 model-year car?',
    "What is Dupaco's routing number?",
])
def test_valid_and_intentionally_broad_requests_are_ready(question):
    feedback = engine().validate(question)
    assert feedback.status == 'ready' and not feedback.blocking


@pytest.mark.parametrize('question', [
    'What was the lowest interest rate for a car in 2025?',
    'What was the savings rate as of February 30, 2026?',
    'What is the rate on a 60-month auto loan with a 72-month term?',
    'What is the highest APY for -$500?',
    "What is Chase Bank's routing number?",
])
def test_blocking_feedback_matches_the_answer_engines_rejection(question):
    instance = engine()
    feedback = instance.validate(question)
    answer = instance.answer(question)
    assert feedback.blocking
    assert not answer.confident and answer.text == feedback.message


def test_selected_date_updates_validation_and_overrides_question_date():
    instance = engine()
    question = 'What was the lowest APR for a car in 2025?'
    assert instance.validate(question).blocking
    assert not instance.validate(question, '2026-09-28').blocking
    future = instance.validate('What is the certificate rate?', '2030-01-01')
    assert not future.blocking and '2026-09-28' in future.message


def test_validation_endpoint_uses_the_loaded_controller(write_snapshot):
    app = create_app(write_snapshot())
    with TestClient(app) as client:
        client.portal.call(app.state.runtime.ready.wait)
        result = client.post('/api/validate', json={'question': 'What is the rate on a car loan?'})
        assert result.status_code == 200
        assert result.json()['status'] == 'needs_info'
        assert result.json()['blocking'] is False
        assert 'model year' in result.json()['message']
        assert client.post('/api/validate', json={'question': ' '}).status_code == 422
