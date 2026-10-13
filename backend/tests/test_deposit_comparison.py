from __future__ import annotations

import pytest

from backend.submission.knowledge.adapters.contract import Page, Snapshot
from backend.submission.solution import build


def deposit_engine():
    engine = build()
    engine.ingest(Snapshot('latest', '2026-09-28', [
        Page('https://www.dupaco.com/personal/savings-account', 'Savings rates', '''# Savings rates
## Savings
| Product | Balance Tier | APY |
| --- | --- | --- |
| Share Savings | $0 and over | 0.50% |
| Bright Savings | $0 and over | 3.50% |
## Certificates
| Certificate | APY | Min. to Earn |
| --- | --- | --- |
| 17 Month Fixed Jumbo Certificate Special | 4.20% | $100,000 |
| 17 Month Fixed Certificate Special | 4.10% | $1,000 |
''', '2026-09-28'),
        Page('https://www.dupaco.com/personal/checking-accounts', 'Checking rates', '''# Checking rates
| Product | Balance Tier | APY |
| --- | --- | --- |
| 1st Rate Checking | $0 and over | 2.50% |
''', '2026-09-28'),
        Page('https://www.dupaco.com/business-rates', 'Business rates', '''# Business rates
| Product | Balance Tier | APY |
| --- | --- | --- |
| Business Savings | $0 and over | 9.50% |
''', '2026-09-28'),
        Page('https://www.dupaco.com/calculators/vehicle-affordability', 'Example calculator', '''# Calculator example
| Product | Balance | APY |
| --- | --- | --- |
| 2023-26 Model Year | 60 Months | 8.54% |
''', '2026-09-28'),
        Page('https://www.dupaco.com/learn/debt', 'Debt advice',
             '# Debt advice\n\nThe debt with the highest interest rate may not have the smallest balance.', '2026-09-28'),
    ]))
    return engine


@pytest.mark.parametrize('question', [
    'what account has the highest interest rate',
    'Which deposit account offers the best rate?',
    'Which account pays the most interest?',
])
def test_highest_account_compares_deposit_yields_instead_of_debt_articles(question):
    answer = deposit_engine().answer(question)
    assert answer.confident
    assert '17 Month Fixed Jumbo Certificate Special' in answer.text
    assert '4.20% APY' in answer.text and '$100,000' in answer.text
    assert '8.54%' not in answer.text and '9.50%' not in answer.text
    assert 'smallest balance' not in answer.text
    assert answer.sources[0].url.endswith('/personal/savings-account')
    assert '4.20%' in answer.sources[0].quote


def test_savings_only_comparison_does_not_default_to_share_savings_or_include_cds():
    answer = deposit_engine().answer('Which savings account pays the highest interest rate?')
    assert answer.confident and 'Bright Savings' in answer.text and '3.50% APY' in answer.text
    assert '4.20%' not in answer.text


@pytest.mark.parametrize('balance, product, rate', [
    ('$5,000', '17 Month Fixed Certificate Special', '4.10%'),
    ('$500', 'Bright Savings', '3.50%'),
])
def test_comparison_respects_deposit_minimums(balance, product, rate):
    answer = deposit_engine().answer(f'What account has the highest interest rate for {balance}?')
    assert answer.confident and product in answer.text and rate in answer.text
    assert '4.20%' not in answer.text


def test_comparison_without_deposit_rate_evidence_does_not_use_keyword_fallback():
    engine = build()
    engine.ingest(Snapshot('empty', '2026-09-28', [
        Page('https://example.test/debt', 'Debt advice',
             '# Advice\n\nThe account with the highest interest rate is the debt to prioritize.', '2026-09-28'),
    ]))
    answer = engine.answer('What account has the highest interest rate?')
    assert not answer.confident and not answer.sources
    assert 'debt to prioritize' not in answer.text
