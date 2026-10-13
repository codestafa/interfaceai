from datetime import date

import pytest

from submission.knowledge.adapters.contract import Page, Snapshot
from submission.knowledge.services.query import question_date
from submission.solution import build


@pytest.mark.parametrize("text", [
    "What was the rate on February 30, 2026?",
    "What was the rate on 2026-13-01?",
    "What was the rate on 2026-2-30?",
    "What was the rate on 02/29/2025?",
])
def test_invalid_explicit_calendar_dates_raise(text):
    with pytest.raises(ValueError, match="Invalid question date"):
        question_date(text)


@pytest.mark.parametrize("text, expected", [
    ("Rate as of May 2026?", date(2026, 5, 31)),
    ("Rate on Feb 29, 2024?", date(2024, 2, 29)),
    ("Rate on May 12th, 2026?", date(2026, 5, 12)),
    ("Rate on 05/19/2026?", date(2026, 5, 19)),
    ("What will the 17-month certificate rate be in 2030?", date(2030, 12, 31)),
    ("What were auto rates during 2024?", date(2024, 12, 31)),
    ("Auto rates in 2030 for a 2025 vehicle?", date(2030, 12, 31)),
    ("Rates as of 2026-05-31, May 31, 2026?", date(2026, 5, 31)),
])
def test_explicit_date_and_temporal_year_resolution(text, expected):
    assert question_date(text) == expected


@pytest.mark.parametrize("text", [
    "What is the APR for a 60-month auto loan on a 2025 vehicle?",
    "What is the APR for model year 2025?",
    "What is the APR for a vehicle from 2025?",
    "Rate for a 2024 model-year car?",
    "What is the rate for a $2030 balance?",
    "What is the rate for a balance of 2030?",
])
def test_model_years_and_amounts_are_not_question_dates(text):
    assert question_date(text) is None


@pytest.mark.parametrize("text", [
    "What was the rate on 2026-05-12 or 2026-05-19?",
    "Rates as of May 2026 and September 2026?",
    "What was the rate in 2025 and in 2026?",
    "What was the rate in 2025 or 2026?",
    "What was the rate during 2024-2026?",
])
def test_conflicting_dates_are_rejected(text):
    with pytest.raises(ValueError, match="conflicting explicit dates"):
        question_date(text)


def test_explicit_as_of_overrides_invalid_or_conflicting_question_dates():
    engine = build()
    page = Page("https://example.test/rates", "Certificate rates", """# Certificate rates
| Certificate | APY |
| --- | --- |
| 17 Month Certificate | 4.10% |
""", "2026-05-12")
    engine.ingest(Snapshot("first", "2026-05-12", [page]))
    for dates in ("February 30, 2026", "May 2026 and September 2026"):
        question = f"What is the 17-month certificate rate as of {dates}?"
        assert not engine.answer(question).confident
        assert "4.10%" in engine.answer(question, as_of="2026-05-12").text


def test_future_question_year_reaches_coverage_disclosure():
    engine = build()
    engine.ingest(Snapshot("first", "2026-05-12", []))
    answer = engine.answer("What will the 17-month certificate rate be in 2030?")
    assert "coverage" in answer.text.lower()
    assert "2026-05-12" in answer.text
