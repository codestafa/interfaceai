import pytest

from submission.knowledge.adapters.contract import Page, Snapshot
from submission.knowledge.services.query_validation import question_issue
from submission.solution import build


@pytest.mark.parametrize('question', [
    'What is Chase Bank’s routing number?',
    "What is Bank of America's 17-month certificate APY?",
    'What is the routing number for Another Credit Union?',
    "What is Example Bank's savings rate?",
])
def test_other_institutions_are_not_answered_with_dupaco_facts(question):
    engine = build()
    engine.ingest(Snapshot('one', '2026-05-12', [
        Page('https://www.dupaco.com/contact', 'Contact',
             '# Contact\n\nRouting Number: 123456789', '2026-05-12'),
    ]))
    answer = engine.answer(question)
    assert not answer.confident and not answer.sources
    assert '123456789' not in answer.text
    assert 'only cover Dupaco' in answer.text


@pytest.mark.parametrize('question', [
    "What is Dupaco's routing number?",
    "What's the interest rate for a 60-month auto loan?",
    "What is the APY on Dupaco's 17-month special certificate?",
    "What is the APY of Investor's Choice Money Market?",
    'What credit cards do you offer and what are their APRs?',
    'What is the rate for a 60-month (5-year) auto loan?',
])
def test_supported_wording_is_not_over_rejected(question):
    assert question_issue(question) is None


@pytest.mark.parametrize('question, expected', [
    ('Which account pays the highest APY for -$500?', 'non-negative'),
    ('Which account pays the highest APY for $-500?', 'non-negative'),
    ('What is the APR for a 60-month auto loan with a 72-month term?', 'one term'),
    ('What is the rate on a sixty-month auto loan?', 'using digits'),
    ('What is the routing number and who is eligible for membership?', 'one topic'),
    ('What is the weather and the auto loan rate?', 'one topic'),
])
def test_ambiguous_or_partial_requests_get_actionable_clarification(question, expected):
    engine = build()
    engine.ingest(Snapshot('one', '2026-05-12', []))
    answer = engine.answer(question)
    assert not answer.confident and not answer.sources
    assert expected in answer.text


def test_future_rate_forecast_is_not_reported_as_a_current_fact():
    engine = build()
    engine.ingest(Snapshot('one', '2026-05-12', []))
    answer = engine.answer('What will the 17-month certificate rate be in 2030?')
    assert not answer.confident and 'cannot predict' in answer.text
    assert '2026-05-12' in answer.text


def test_invalid_question_date_is_visible_and_does_not_fall_back_to_today():
    engine = build()
    engine.ingest(Snapshot('one', '2026-05-12', []))
    answer = engine.answer('What was the savings rate as of February 30, 2026?')
    assert not answer.confident and 'February 30, 2026' in answer.text
