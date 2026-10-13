"""Financial queries filter qualified facts before resolving source disagreements."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

from ..models.domain import Document, Evidence, Fact, QueryIntent, Resolution
from .markdown import LINK
from .resolution import balance_matches, choose, group_facts, topic, value_label

DEPOSIT_CATEGORIES = frozenset(('savings', 'checking', 'certificate'))


def _minimum_met(fact: Fact, balance: float) -> bool:
    for name in ('minimum', 'opening_minimum'):
        amount = re.search(r'\$?([\d,]+(?:\.\d+)?)', fact.qualifier(name))
        if amount and balance < float(amount[1].replace(',', '')):
            return False
    return True


def _comparison_candidate(fact: Fact, intent: QueryIntent) -> bool:
    if not (intent.highest_rate or intent.lowest_rate):
        return True
    if fact.authority < 60:
        return False
    if fact.category not in DEPOSIT_CATEGORIES:
        return True
    if intent.category == 'deposit' and any(word in intent.question.lower() for word in ('intro', 'promot')):
        if fact.qualifier('offer') != 'introductory':
            return False
    # Calculator defaults and educational examples are not advertised yields.
    return (fact.authority >= 60 and 'APY' in dict(fact.values)
            and (intent.balance is None or _minimum_met(fact, intent.balance)))


def _matches(fact: Fact, intent: QueryIntent) -> bool:
    q = intent.question.lower()
    if fact.qualifier('customer_type') and fact.qualifier('customer_type') != ('business' if 'business' in q else 'personal'):
        return False
    if intent.term_months and fact.qualifier('term_months') != str(intent.term_months):
        return False
    if intent.model_year:
        model = int(fact.qualifier('model_year', '0'))
        if model != intent.model_year and not (fact.qualifier('older') == 'True' and intent.model_year < model):
            return False
    if intent.specific_product and fact.entity.lower() != intent.specific_product:
        return False
    if fact.category in ('savings', 'checking') and (('intro' in q or 'promot' in q) != (fact.qualifier('offer') == 'introductory')):
        return False
    if intent.category == 'savings' and not intent.specific_product and not (intent.highest_rate or intent.lowest_rate) and fact.entity.lower() != 'share savings':
        return False
    if intent.balance is not None and fact.qualifier('balance') and not balance_matches(fact.qualifier('balance'), intent.balance):
        return False
    if fact.category in ('certificate', 'ira'):
        if 'jumbo' in q and fact.qualifier('tier') != 'jumbo':
            return False
        if any(x in q for x in ('non-jumbo', 'standard', 'regular')) and fact.qualifier('tier') == 'jumbo':
            return False
        if 'special' in q and fact.qualifier('offer') != 'special':
            return False
        if 'regular' in q and fact.qualifier('offer') != 'regular':
            return False
        if 'roth' in q and 'roth' not in fact.entity.lower():
            return False
        if 'traditional' in q and 'traditional' not in fact.entity.lower():
            return False
    if intent.category == 'card':
        if ('intro' in q or 'transfer' in q) != (fact.qualifier('offer') == 'introductory'):
            return False
        if 'platinum' in q and 'platinum' not in fact.entity.lower():
            return False
        if 'rewards' in q and 'rewards' not in fact.entity.lower():
            return False
        if 'business' in q and 'business' not in fact.entity.lower():
            return False
        if 'business' not in q and ('platinum' in q or 'rewards' in q) and 'business' in fact.entity.lower():
            return False
    if intent.category == 'mortgage':
        requested_program = next((program for program in ('fha', 'usda', 'jumbo', 'rate relief') if program in q), None)
        if re.search(r'\bva\b', q):
            requested_program = 'va'
        if requested_program and requested_program not in fact.evidence.quote.lower():
            return False
        purpose = 'refinance' if 'refinanc' in q else 'purchase'
        if fact.qualifier('purpose') != purpose:
            return False
    return True



def _ranked_rates(facts: list[Fact], intent: QueryIntent) -> tuple[list[Fact], str]:
    """Compare one metric and one end of any advertised range consistently."""
    question = intent.question.lower()
    if re.search(r'\bapr\b', question):
        attribute = 'APR'
    elif re.search(r'\bapy\b', question):
        attribute = 'APY'
    elif 'dividend' in question:
        attribute = 'Dividend rate'
    elif intent.category in DEPOSIT_CATEGORIES | {'deposit', 'ira'}:
        attribute = 'APY'
    else:
        attribute = 'Interest rate' if any('Interest rate' in dict(f.values) for f in facts) else 'APR'
    scored = []
    for fact in facts:
        value = dict(fact.values).get(attribute)
        if value is None:
            continue
        percentages = [Decimal(number) for number in re.findall(r'(\d+(?:\.\d+)?)%', value)]
        if percentages:
            score = min(percentages) if intent.lowest_rate else max(percentages)
            scored.append((fact, score))
    if not scored:
        return [], attribute
    target = (min if intent.lowest_rate else max)(score for _, score in scored)
    return [fact for fact, score in scored if score == target], attribute


def _sort_key(fact: Fact):
    if fact.category in ('certificate', 'ira'):
        return (0, '', '', int(fact.qualifier('term_months', '0') or '0'), fact.entity.lower())
    return (int(fact.qualifier('loan_limit', '0')), fact.entity.lower(), fact.qualifier('balance'),
            int(fact.qualifier('term_months', '0') or '0'), fact.qualifier('model_year'))


def _describe(fact: Fact, compact: bool = False) -> str:
    q = dict(fact.qualifiers)
    label = fact.entity
    if fact.category in ('auto', 'recreational') and q.get('model_year_label'):
        label += f" ({q['model_year_label']}, {q.get('term_months', '')} months)"
    elif fact.category in ('personal', 'mortgage', 'home_equity', 'home_improvement') and q.get('term_months'):
        months = int(q['term_months'])
        term = f'{months // 12}-year' if fact.category == 'mortgage' else f'{months}-month'
        label = f'{term} {label}'
    if q.get('loan_limit'):
        label += f" (loans up to ${int(q['loan_limit']):,})"
    if q.get('balance_label'):
        label += f" ({q['balance_label']})"
    values = ', '.join(f'{value} {attribute}' for attribute, value in fact.values
                       if not compact or attribute != 'Dividend rate')
    result = f'{label}: {values}'
    if q.get('minimum') and fact.category in ('certificate', 'ira'):
        result += f"; minimum {q['minimum']}"
    return result


def answer_financial(intent: QueryIntent, facts: tuple[Fact, ...], documents: tuple[Document, ...], day: date) -> Resolution | None:
    if not intent.category:
        return None
    q = intent.question.lower()
    if intent.highest_rate and intent.lowest_rate:
        return Resolution('Please ask for either the lowest or the highest rate so I can compare one direction.', confident=False)
    if intent.category == 'certificate' and any(x in q for x in ('link', 'url', 'website')):
        docs = sorted((d for d in documents if any(f.category == 'certificate' and f.evidence.url == d.url and f.authority >= 90 for f in facts)),
                      key=lambda d: ('/personal/savings-account' not in d.url, d.url))
        if docs:
            document = docs[0]
            links = [url for label, url in LINK.findall(document.markdown) if '#rates' in url and ('saving' in url or 'rate' in label.lower())]
            url = links[0] if links else document.url
            return Resolution(f'Certificate rates: {url}', (Evidence(document.url, document.snapshot_id, 'Certificate rate table'),))
    if intent.category == 'mortgage' and any(x in q for x in ('construction', 'adjustable', '7/1', '5/1', 'arm')):
        matching = tuple(Evidence(d.url, d.snapshot_id, d.title) for d in documents if '/personal/loans/home-loans' in d.url)
        return Resolution('The supplied snapshots do not publish a matching rate for that mortgage program. Please contact a mortgage lender for a quote.', matching[:1], False)
    categories = DEPOSIT_CATEGORIES if intent.category == 'deposit' else {intent.category}
    candidates = [f for f in facts if f.category in categories and f.applies_on(day)
                  and _matches(f, intent) and _comparison_candidate(f, intent)]
    if intent.category == 'mortgage' and intent.balance is not None:
        limits = sorted({int(f.qualifier('loan_limit')) for f in candidates if f.qualifier('loan_limit') and int(f.qualifier('loan_limit')) >= intent.balance})
        candidates = [f for f in candidates if not f.qualifier('loan_limit') or (limits and int(f.qualifier('loan_limit')) == limits[0])]
    winners, conflicts, unresolved = [], [], []
    for group in group_facts(candidates).values():
        winner, disagreement = choose(group)
        if winner is None:
            unresolved.extend(group)
        else:
            winners.append(winner)
            if disagreement:
                conflicts.append(f'{topic(winner)}: selected {value_label(winner)} from the applicable official product/rate table; other pages disagree.')
    if unresolved:
        return Resolution('Equally authoritative sources disagree for the requested product and tier. I cannot provide a reliable single rate.',
                          tuple(dict.fromkeys(f.evidence for f in unresolved)), False,
                          'Conflicting claims: ' + '; '.join(sorted({value_label(f) for f in unresolved})))
    if not winners:
        return Resolution('No matching published rate was found in the selected snapshot. Please contact the credit union for a quote.', (), False)
    # Collapse expanded model-year rows back to their published tier for broad lists.
    unique = {}
    for fact in winners:
        key = (fact.entity, fact.values, tuple((k, v) for k, v in fact.qualifiers if k != 'model_year'))
        unique.setdefault(key, fact)
    winners = sorted(unique.values(), key=_sort_key)
    comparison_metric = None
    if intent.highest_rate or intent.lowest_rate:
        winners, comparison_metric = _ranked_rates(winners, intent)
        if not winners:
            return Resolution(f'No matching published {comparison_metric} was found for this comparison in the selected snapshot.', confident=False)
    compact = len(winners) > 2
    descriptions = [_describe(f, compact) for f in winners]
    text = ('\n'.join('- ' + line for line in descriptions) if len(descriptions) > 1 else descriptions[0])
    if (intent.highest_rate or intent.lowest_rate) and intent.category in DEPOSIT_CATEGORIES | {'deposit'}:
        scope = ('personal' if 'business' not in q else 'business')
        products = 'savings, checking, and certificate accounts' if intent.category == 'deposit' else f'{intent.category} accounts'
        offers = 'introductory offers' if 'intro' in q or 'promot' in q else 'excluding introductory savings/checking offers'
        direction = 'Lowest' if intent.lowest_rate else 'Highest'
        text = f'{direction} published {comparison_metric} among {scope} {products} ({offers}):\n' + text
    elif comparison_metric:
        direction = 'Lowest' if intent.lowest_rate else 'Highest'
        text = f'{direction} published {comparison_metric} among the matching tiers:\n' + text
    requested_rate = re.search(r'(\d+(?:\.\d+)?)\s*%', q)
    if requested_rate and any(x in q for x in ('any', 'pay', 'earn')):
        exists = any(float(requested_rate[1]) == float(v.split('%')[0]) for f in winners for attr, v in f.values if attr == 'APY')
        text = ('Yes. ' if exists else 'No matching APY appears in the published tiers for this account. ') + text
    dates = sorted({f.effective_on.isoformat() for f in winners if f.effective_on})
    if dates:
        text += '\nPublished effective date' + ('s' if len(dates) > 1 else '') + ': ' + ', '.join(dates) + '.'
    evidence = tuple(dict.fromkeys(evidence for fact in winners for evidence in (fact.supporting_evidence or (fact.evidence,))))
    # Cite each source once while retaining excerpts from every returned tier.
    by_source = {}
    for item in evidence:
        by_source.setdefault((item.url, item.snapshot_id), []).append(item.quote)
    evidence = tuple(Evidence(url, sid, '\n'.join(quotes)[:1600]) for (url, sid), quotes in by_source.items())
    return Resolution(text, evidence, True, '\n'.join(conflicts) or None)
