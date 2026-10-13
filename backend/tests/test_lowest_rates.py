from datetime import date

import pytest

from backend.submission.knowledge.adapters.contract import Page, Snapshot
from backend.submission.knowledge.services.query import interpret, question_date
from backend.submission.solution import build


AUTO_URL = 'https://www.dupaco.com/personal/loans/auto-motorcycle-loans'


def auto_page(rate='4.25%', *, url=AUTO_URL):
    return Page(url, 'Auto loans', f'''# Auto loan rates
| Loan Program | Term | APR |
| --- | --- | --- |
| 2024-27 Model Year | 48 Months | {rate} |
| 2024-27 Model Year | 60 Months | 4.75% |
| 2021-23 Model Year | 48 Months | 3.25% |
''', '2026-05-12')


def auto_engine():
    engine = build()
    engine.ingest(Snapshot('first', '2026-05-12', [auto_page()]))
    engine.ingest(Snapshot('latest', '2026-09-28', [
        auto_page('3.75%'),
        auto_page('1.25%', url='https://www.dupaco.com/calculators/auto'),
    ]))
    return engine


def test_exact_user_question_uses_history_and_declines_missing_2025_data():
    question = 'what was the lowest interest rate for a car in 2025'
    intent = interpret(question)
    assert intent.category == 'auto' and intent.lowest_rate
    assert intent.model_year is None
    assert question_date(question) == date(2025, 12, 31)
    answer = auto_engine().answer(question)
    assert not answer.confident and not answer.sources
    assert '2025-12-31' in answer.text and '2026-05-12' in answer.text
    assert '%' not in answer.text


@pytest.mark.parametrize('question', [
    'What is the lowest APR for a 2025 model-year car?',
    'What is the minimum APR for a car, model year 2025?',
    'What is the lowest interest rate for a 2025 vehicle?',
])
def test_lowest_auto_apr_filters_model_year_and_excludes_calculator_defaults(question):
    assert question_date(question) is None
    answer = auto_engine().answer(question)
    assert answer.confident and '3.75% APR' in answer.text and '48 months' in answer.text
    assert all(value not in answer.text for value in ('1.25%', '3.25%', '4.75%'))
    assert answer.sources[0].url == AUTO_URL


def test_lowest_comparison_keeps_requested_term_and_snapshot():
    engine = auto_engine()
    question = 'What is the lowest APR for a 2025 car?'
    assert '4.25%' in engine.answer(question, '2026-05-12').text
    answer = engine.answer('What is the lowest APR for a 2025 car over 60 months?')
    assert '4.75%' in answer.text and '3.75%' not in answer.text


def test_highest_auto_comparison_still_uses_maximum_matching_apr():
    answer = auto_engine().answer('What is the highest APR for a 2025 car?')
    assert answer.confident and '4.75%' in answer.text and '3.75%' not in answer.text


def test_car_word_boundaries_do_not_capture_credit_cards():
    assert interpret('What is the lowest credit card APR?').category == 'card'
    assert interpret('What is the lowest card printing rate?').category is None


def test_apy_is_not_substituted_with_apr_for_a_loan():
    answer = auto_engine().answer('What is the lowest APY for a 2025 car?')
    assert not answer.confident and '%' not in answer.text


def test_interest_rate_and_apr_use_distinct_comparison_columns():
    engine = build()
    engine.ingest(Snapshot('latest', '2026-09-28', [
        Page(AUTO_URL, 'Auto loans', '''# Auto loans
| Loan Program | Term | Interest Rate | APR |
| --- | --- | --- | --- |
| 2024-27 Model Year | 48 Months | 4.00% | 4.50% |
| 2024-27 Model Year | 60 Months | 3.75% | 4.75% |
''', '2026-09-28'),
    ]))
    apr = engine.answer('What is the lowest APR for a 2025 car?')
    interest = engine.answer('What is the lowest interest rate for a 2025 car?')
    assert '48 months' in apr.text and '60 months' not in apr.text
    assert '60 months' in interest.text and '48 months' not in interest.text


def test_opposed_comparison_directions_do_not_silently_select_one():
    answer = auto_engine().answer('What is the highest and lowest APR for a 2025 car?')
    assert not answer.confident


def test_rate_range_comparison_uses_the_requested_end_of_the_range():
    engine = build()
    engine.ingest(Snapshot('latest', '2026-09-28', [
        Page('https://www.dupaco.com/business/credit-cards', 'Business cards', '''# Business cards
| Card Type | APR |
| --- | --- |
| Business Platinum Visa | 10.50%–20.50% |
| Business Rewards Visa | 12.50%–19.50% |
''', '2026-09-28'),
    ]))
    for direction in ('lowest', 'highest'):
        answer = engine.answer(f'What is the {direction} business credit card APR?')
        assert answer.confident and 'Business Platinum Visa' in answer.text
        assert 'Business Rewards Visa' not in answer.text
