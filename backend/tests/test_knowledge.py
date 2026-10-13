from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest

from backend.submission.solution import build
from backend.submission.knowledge.adapters.contract import Answer, Page, Snapshot
from backend.submission.knowledge.models.domain import Evidence, Fact
from backend.submission.knowledge.services.resolution import choose, detect_conflicts

AUTO_URL = "https://www.dupaco.com/personal/loans/auto-motorcycle-loans"


def auto_page(rate="4.25%", *, url=AUTO_URL, prefix="", suffix="", extra_rows=""):
    text = f"""# Auto Loans
## Rates
{prefix}
| Loan Program | Term | Annual Percentage Rate (As Low As) |
| --- | --- | --- |
| 2024-27 Model Year | 60 Months | {rate} APR |
{extra_rows}
{suffix}
"""
    return Page(url, "Auto Loans", text, "2026-05-12")


def snapshot(day, pages, sid=None):
    return Snapshot(sid or f"snapshot_{day}", day, pages)


def rate_question():
    return "What is the APR for a 60-month auto loan on a 2025 vehicle?"


def test_harness_types_and_worker_thread_are_supported():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page()]))
    with ThreadPoolExecutor(max_workers=1) as pool:
        answer = pool.submit(engine.answer, rate_question()).result(timeout=2)
    assert isinstance(answer, Answer)
    assert answer.confident and "4.25%" in answer.text
    assert answer.sources[0].url == AUTO_URL
    assert "4.25%" in answer.sources[0].quote


def test_history_respects_snapshot_boundaries_and_explicit_date():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page("4.25%")]))
    engine.ingest(snapshot("2026-05-19", [auto_page("4.50%")]))
    engine.ingest(snapshot("2026-09-28", [auto_page("4.75%")]))
    assert "4.75%" in engine.answer(rate_question()).text
    assert "4.25%" in engine.answer(rate_question(), "2026-05-18").text
    assert "4.50%" in engine.answer(rate_question(), "2026-05-19").text
    assert "4.50%" in engine.answer(rate_question() + " As of May 2026.").text
    assert "4.25%" in engine.answer(rate_question() + " As of September 2026.", "2026-05-12").text
    assert not engine.answer(rate_question(), "2026-01-01").confident
    assert engine.conflicts() == []  # Changes across dates alone are not contradictions.


def test_future_request_discloses_coverage_limit():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page()]))
    answer = engine.answer(rate_question(), "2026-12-01")
    assert "4.25%" in answer.text
    assert "2026-05-12" in answer.text and "coverage" in answer.text.lower()


def test_removed_page_does_not_leak_into_latest_answer():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page()]))
    engine.ingest(snapshot("2026-09-28", []))
    latest = engine.answer(rate_question())
    assert not latest.confident and "4.25%" not in latest.text
    assert "4.25%" in engine.answer(rate_question(), "2026-05-12").text


def test_repeated_ingestion_replaces_membership_without_duplicates():
    engine = build()
    source = snapshot("2026-05-12", [auto_page()])
    engine.ingest(source)
    engine.ingest(source)
    assert len(engine.snapshot_dates) == 1
    assert len(engine.answer(rate_question()).sources) == 1
    engine.ingest(snapshot("2026-05-12", [], sid=source.snapshot_id))
    assert not engine.answer(rate_question()).confident


def test_official_table_wins_over_calculator_without_polluting_answer():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page(), auto_page("3.15%", url="https://www.dupaco.com/calculators/auto-loan")]))
    answer = engine.answer(rate_question())
    assert answer.confident and "4.25%" in answer.text and "3.15%" not in answer.text
    assert answer.conflict_note
    conflicts = engine.conflicts()
    assert conflicts and all("4.25%" in conflict.resolution for conflict in conflicts)


def test_equal_authority_disagreement_refuses_to_guess():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page(url="https://example.test/rates-one"), auto_page("3.15%", url="https://example.test/rates-two")]))
    answer = engine.answer(rate_question())
    assert not answer.confident
    assert "4.25%" not in answer.text and "3.15%" not in answer.text
    assert engine.conflicts() and all(c.resolution is None for c in engine.conflicts())


def test_terms_and_model_year_tiers_do_not_conflict():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page(extra_rows="| 2021-23 Model Year | 60 Months | 5.50% APR |\n| 2024-27 Model Year | 84 Months | 6.25% APR |")]))
    answer = engine.answer(rate_question())
    assert answer.confident and "4.25%" in answer.text
    assert "5.50%" not in answer.text and "6.25%" not in answer.text
    assert engine.conflicts() == []


@pytest.mark.parametrize("placement", ["prefix", "suffix"])
@pytest.mark.parametrize("restriction", ["Expires on 2026-05-01", "Effective 2026-06-01"])
def test_inapplicable_rates_are_excluded(placement, restriction):
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page(**{placement: restriction})]))
    assert not engine.answer(rate_question()).confident


def test_metric_subsets_are_compatible_and_do_not_create_false_conflicts():
    evidence = Evidence("https://example.test/rates", "snapshot", "Published values")
    def fact(values):
        return Fact("savings", "Share Savings", (), values, evidence, 100)
    candidates = [fact((("APY", "4.00%"),)), fact((("APY", "4.0%"), ("Dividend rate", "3.93%")))]
    winner, disagreement = choose(candidates)
    assert winner is not None and not disagreement
    assert detect_conflicts(tuple(candidates), date(2026, 5, 12)) == ()
    assert detect_conflicts((fact((("APY", "4.00%"),)), fact((("Interest rate", "3.93%"),))), date(2026, 5, 12)) == ()


def test_conflict_inventory_normalizes_formatting_and_retains_latest_evidence():
    def checking_page(url, value, separator):
        return Page(url, "Checking rates", f"""# Checking rates
| Product | Balance Tier | APY |
| --- | --- | --- |
| 1st Rate Checking | $5,000 {separator} $24,999.99 | {value} |
""", "2026-05-12")
    engine = build()
    for day, separator, correct, stale in [("2026-05-12", "-", "2.50%", "3.00%"), ("2026-09-28", "–", "2.5%", "3.0%")]:
        engine.ingest(snapshot(day, [
            checking_page("https://www.dupaco.com/personal/checking-accounts", correct, separator),
            checking_page("https://www.dupaco.com/rates", stale, separator),
        ]))
    conflicts = engine.conflicts()
    assert len(conflicts) == 1
    assert {source.snapshot_id for source in conflicts[0].sources} == {"snapshot_2026-09-28"}


def test_missing_product_returns_no_invented_numbers():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page()]))
    answer = engine.answer("What is the rate for a construction loan?")
    assert not answer.confident and not any(character.isdigit() for character in answer.text)


def test_independent_paraphrases_return_same_supported_fact():
    engine = build()
    engine.ingest(snapshot("2026-05-12", [auto_page()]))
    questions = [rate_question(), "For a 2025 car, what APR applies to an auto loan over 60 months?", "Tell me the interest rate for a 60-month car loan, 2025 model year."]
    answers = [engine.answer(question) for question in questions]
    assert all(answer.confident and "4.25%" in answer.text for answer in answers)
    assert len({answer.text for answer in answers}) == 1


def test_explicit_branch_closure_is_evaluated_against_requested_date():
    page = Page("https://www.dupaco.com/newsroom/hy-vee-closure", "Hy-Vee branch closure",
                "# Hy-Vee branch closure\n\nJanuary 1, 2026\n\nThis location will close March 31, 2026.", "2026-01-05")
    engine = build()
    engine.ingest(snapshot("2026-01-05", [page]))
    before = engine.answer("Is the Hy-Vee branch still open?", "2026-02-01")
    after = engine.answer("Is the Hy-Vee branch still open?", "2026-04-01")
    assert "scheduled" in before.text.lower()
    assert after.text.startswith("No.")


def test_named_branch_hours_override_generic_schedules():
    generic = Page("https://www.dupaco.com/newsroom/general", "General branch hours",
                   "# General branch hours\n\nJanuary 1, 2026\n\n**Lobby**\nMonday through Friday: 9am-5pm", "2026-05-12")
    specific = Page("https://www.dupaco.com/newsroom/mullan", "Mullan Avenue branch hours",
                    "# Mullan Avenue branch hours\n\nJanuary 1, 2026\n\n**Lobby**\nMonday through Friday: 8am-4pm", "2026-05-12")
    engine = build()
    engine.ingest(snapshot("2026-05-12", [generic, specific]))
    answer = engine.answer("What are the lobby hours for the Mullan Avenue branch?")
    assert answer.confident and "8am-4pm" in answer.text and "9am-5pm" not in answer.text


def test_contradictory_authoritative_routing_numbers_are_reported_and_not_guessed():
    engine = build()
    pages = [Page(url, "Contact", f"# Contact\n\nRouting number: {number}", "2026-05-12")
             for url, number in [("https://www.dupaco.com/contact", "123456789"),
                                 ("https://www.dupaco.com/contact/", "987654321")]]
    engine.ingest(snapshot("2026-05-12", pages))
    answer = engine.answer("What is the routing number?")
    assert not answer.confident
    assert "123456789" not in answer.text and "987654321" not in answer.text
    conflicts = [conflict for conflict in engine.conflicts() if "routing" in conflict.topic.lower()]
    assert len(conflicts) == 1 and conflicts[0].resolution is None


def test_same_branch_and_publication_date_hours_conflict_is_in_inventory():
    pages = [Page(f"https://www.dupaco.com/newsroom/mullan-{index}", "Mullan Avenue branch hours",
                  f"# Mullan Avenue branch hours\n\nMay 1, 2026\n\n**Lobby**\nMonday through Friday: {hours}", "2026-05-12")
             for index, hours in enumerate(["8am-4pm", "9am-5pm"])]
    engine = build()
    engine.ingest(snapshot("2026-05-12", pages))
    assert not engine.answer("What are the lobby hours for the Mullan Avenue branch?").confident
    conflicts = [c for c in engine.conflicts() if "mullan" in c.topic.lower()]
    assert len(conflicts) == 1 and conflicts[0].resolution is None


def test_ordinary_changes_to_published_branch_count_are_not_conflicts():
    pages = [Page(f"https://www.dupaco.com/newsroom/count-{index}", "Branch update",
                  f"# Branch update\n\n{published}\n\nDupaco has {count} branch office locations.", "2026-05-12")
             for index, (published, count) in enumerate([("January 1, 2026", 12), ("April 1, 2026", 14)])]
    engine = build()
    engine.ingest(snapshot("2026-05-12", pages))
    answer = engine.answer("How many branches does Dupaco have?")
    assert answer.confident and "14 branch" in answer.text
    assert engine.conflicts() == []


def test_same_date_branch_count_disagreement_is_reported():
    pages = [Page(f"https://www.dupaco.com/newsroom/count-{count}", "Branch update",
                  f"# Branch update\n\nApril 1, 2026\n\nDupaco has {count} branch office locations.", "2026-05-12")
             for count in [12, 14]]
    engine = build()
    engine.ingest(snapshot("2026-05-12", pages))
    assert not engine.answer("How many branches does Dupaco have?").confident
    conflicts = [c for c in engine.conflicts() if "branch" in c.topic.lower()]
    assert len(conflicts) == 1 and conflicts[0].resolution is None
