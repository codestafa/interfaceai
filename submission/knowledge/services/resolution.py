"""Resolve only comparable claims; normal time changes are not contradictions."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from dataclasses import replace
from decimal import Decimal
import re

from ..models.domain import Disagreement, Fact

DISPLAY_QUALIFIERS = {'balance_label', 'model_year_label', 'minimum', 'opening_minimum', 'older'}


def claim_key(fact: Fact) -> tuple:
    return (fact.category, fact.entity.lower(), tuple((k, v) for k, v in fact.qualifiers if k not in DISPLAY_QUALIFIERS))


def rank(fact: Fact) -> tuple[int, date]:
    return fact.authority, fact.effective_on or date.min


def value_label(fact: Fact) -> str:
    return ', '.join(f'{value} {attribute}' for attribute, value in fact.values)


def normalized_value(value: str) -> tuple[str, ...]:
    """Formatting (20.5 vs 20.50) never creates a contradiction."""
    numbers = re.findall(r'\d+(?:\.\d+)?', value)
    return tuple(str(Decimal(number).normalize()) for number in numbers) or (value.lower(),)



def conflict_key(conflict: Disagreement) -> tuple:
    """Deduplicate presentation-only changes while keeping distinct claim units."""
    def normalize(text: str) -> str:
        text = text.lower().replace('–', '-').replace('—', '-')
        text = re.sub(r'\d+(?:,\d{3})*(?:\.\d+)?',
                      lambda match: format(Decimal(match.group().replace(',', '')).normalize(), 'f'), text)
        text = re.sub(r'\s*-\s*', '-', text)
        return ' '.join(text.split())

    # The metric ordering in a table can change without changing its claims.
    values = {tuple(sorted(normalize(metric) for metric in value.split(', ')))
              for value in conflict.values}
    return normalize(conflict.topic), tuple(sorted(values))


def disputed_attributes(facts: list[Fact]) -> set[str]:
    attributes = defaultdict(set)
    for fact in facts:
        for attribute, value in fact.values:
            attributes[attribute].add(normalized_value(value))
    return {attribute for attribute, values in attributes.items() if len(values) > 1}


def choose(facts: list[Fact]) -> tuple[Fact | None, bool]:
    if not facts:
        return None, False
    # Compare each metric separately: APY, interest rate and APR are distinct
    # quantities. A source omitting a metric does not contradict that metric.
    by_attribute = defaultdict(list)
    for fact in facts:
        for attribute, value in fact.values:
            by_attribute[attribute].append((fact, value))
    values, support = [], []
    for attribute, claims in by_attribute.items():
        best_rank = max(rank(fact) for fact, _ in claims)
        best = [(fact, value) for fact, value in claims if rank(fact) == best_rank]
        if len({normalized_value(value) for _, value in best}) > 1:
            return None, True
        fact, value = min(best, key=lambda item: (item[0].evidence.url, item[0].evidence.quote))
        values.append((attribute, value))
        support.append(fact.evidence)
    winner = min(facts, key=lambda fact: (-fact.authority, -(fact.effective_on or date.min).toordinal(),
                                        -len(fact.values), fact.evidence.url, fact.evidence.quote))
    return replace(winner, values=tuple(values), supporting_evidence=tuple(dict.fromkeys(support))), bool(disputed_attributes(facts))


def group_facts(facts):
    groups = defaultdict(list)
    for fact in facts:
        groups[claim_key(fact)].append(fact)
    return groups


def topic(fact: Fact) -> str:
    labels = [fact.entity]
    if fact.qualifier('term_months') and fact.category not in ('certificate', 'ira'):
        labels.append(f"{fact.qualifier('term_months')}-month")
    for key in ('model_year', 'balance_label', 'purpose', 'loan_limit', 'offer'):
        if fact.qualifier(key):
            labels.append(f'{key.replace("_", " ")}: {fact.qualifier(key)}')
    return ' · '.join(labels)


def detect_conflicts(facts: tuple[Fact, ...], day: date) -> tuple[Disagreement, ...]:
    conflicts = []
    for candidates in group_facts(f for f in facts if f.applies_on(day)).values():
        if not disputed_attributes(candidates):
            continue
        values = tuple(sorted({value_label(f) for f in candidates}))
        winner, _ = choose(candidates)
        sources = tuple(dict.fromkeys(f.evidence for f in sorted(candidates, key=lambda f: (-f.authority, f.evidence.url))))
        reason = ('The applicable official product/rate table has higher authority; explicit effective dates break ties between equally authoritative sources.'
                  if winner else 'Equally authoritative applicable sources disagree; no value was selected.')
        conflicts.append(Disagreement(topic(candidates[0]), values, sources,
                                      value_label(winner) if winner else None, reason))
    return tuple(sorted(conflicts, key=lambda c: c.topic))


def balance_matches(label: str, amount: float) -> bool:
    numbers = [float(s.replace(',', '')) for s in re.findall(r'\d[\d,]*(?:\.\d+)?', label)]
    if not numbers:
        return True
    if len(numbers) >= 2:
        return numbers[0] <= amount <= numbers[1]
    if '+' in label or re.search(r'\b(?:and over|and above|or more)\b', label, re.I):
        return amount >= numbers[0]
    return amount == numbers[0]
