"""Small, explicit query grammar and deterministic historical-date selection."""
from __future__ import annotations

import calendar
from datetime import date
import re

from ..models.domain import QueryIntent

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
PRODUCT_ALIASES = {
    'bright': 'bright savings', 'share savings': 'share savings', 'you name it': 'you name it savings',
    'holiday': 'holiday club savings', 'launchpad': 'launchpad savings',
    'high yield': 'high-yield savings', 'achieve': 'achieve money market', 'money market': "investor's choice money market",
    'investor': "investor's choice money market", 'health savings': 'health savings account', 'hsa': 'health savings account',
    'free checking': 'free checking', '1st rate': '1st rate checking', 'first rate': '1st rate checking',
}
STOP_WORDS = set('a an the is are was were be to of for on in and or with me my your you i what how can could would do does dupaco s tell please get current currently now'.split())
HIGHEST_RATE = re.compile(r'\b(?:highest|maximum|top rate|best rate|most interest|(?:pays?|earns?) (?:the )?most)\b')
LOWEST_RATE = re.compile(r'\b(?:lowest|minimum (?:interest )?(?:rate|apr|apy)|least interest|cheapest)\b')


def tokens(text: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+', text.lower())) - STOP_WORDS


def question_date(question: str) -> date | None:
    """Resolve one explicit date without mistaking a vehicle year for history.

    Missing dates use the controller's latest snapshot. Invalid or conflicting
    dates must raise instead of silently taking that default.
    """
    parsed: list[date] = []
    spans: list[tuple[int, int]] = []

    def record(match: re.Match[str], year: int, month: int, day: int) -> None:
        try:
            parsed.append(date(year, month, day))
        except ValueError as error:
            raise ValueError(f"Invalid question date: {match.group()}. Please enter a valid calendar date.") from error
        spans.append(match.span())

    for match in re.finditer(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', question):
        record(match, int(match[1]), int(match[2]), int(match[3]))
    # The supplied website uses US month/day/year notation.
    for match in re.finditer(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', question):
        record(match, int(match[3]), int(match[1]), int(match[2]))

    month_names = dict(MONTHS)
    month_names.update({name[:3]: number for name, number in MONTHS.items()})
    month_pattern = '|'.join(sorted(month_names, key=len, reverse=True))
    named_date = (r'\b(' + month_pattern + r')\.?\s+'
                  r'(?:(\d{1,2})(?:st|nd|rd|th)?,?\s+)?(\d{4})\b')
    for match in re.finditer(named_date, question, re.I):
        month, year = month_names[match[1].lower()], int(match[3])
        day = int(match[2]) if match[2] else calendar.monthrange(year, month)[1]
        record(match, year, month, day)

    # Identify model-year phrases independently of temporal prepositions. For
    # example, "in 2030 for a 2025 vehicle" contains both kinds of year.
    model_years = [match.span(1) for pattern in (
        r'\b((?:19|20)\d{2})\s+(?:model(?:[ -]year)?|vehicle|car|truck|motorcycle)\b',
        r'\bmodel[ -]?year\s+(?:of\s+)?((?:19|20)\d{2})\b',
        r'\b(?:vehicle|car|truck|motorcycle)\s+(?:from\s+)?((?:19|20)\d{2})\b',
    ) for match in re.finditer(pattern, question, re.I)]
    temporal_year = (r'\b(?:as\s+of|back\s+in|during|in|by|for|through|before|after|year)'
                     r'\s+(?:the\s+year\s+)?((?:19|20)\d{2})\b')
    for match in re.finditer(temporal_year, question, re.I):
        start, end = match.span(1)
        if any(left <= start and end <= right for left, right in spans + model_years):
            continue
        parsed.append(date(int(match[1]), 12, 31))
        spans.append((start, end))

    # Coordinated years inherit an explicit temporal cue: "in 2025 or 2026".
    for match in re.finditer(r'\b(?:19|20)\d{2}\b', question):
        start, end = match.span()
        if any(left <= start and end <= right for left, right in spans + model_years):
            continue
        preceding_ends = [right for _, right in spans if right <= start]
        if preceding_ends and re.fullmatch(r'\s*(?:,|and|or|to|through|[-–])\s*', question[max(preceding_ends):start], re.I):
            parsed.append(date(int(match.group()), 12, 31))
            spans.append((start, end))

    dates = set(parsed)
    if len(dates) > 1:
        labels = ', '.join(day.isoformat() for day in sorted(dates))
        raise ValueError(f'The question contains conflicting explicit dates: {labels}. Please provide one as-of date.')
    return next(iter(dates), None)


def interpret(question: str) -> QueryIntent:
    q = question.lower().replace('–', '-').replace('—', '-').replace('high-yield', 'high yield')
    highest_rate = bool(HIGHEST_RATE.search(q))
    lowest_rate = bool(LOWEST_RATE.search(q))
    category = None
    if re.search(r'\b(certificate|certificates|cds?|term.share)\b', q):
        category = 'ira' if any(x in q for x in ('ira', 'roth', 'traditional')) else 'certificate'
    elif any(x in q for x in ('credit card', 'credit-card', 'visa')) and any(x in q for x in ('rate', 'apr', 'interest', 'offer', 'purchase')):
        category = 'card'
    elif any(x in q for x in ('heloc', 'home equity line')):
        category = 'heloc'
    elif 'home equity' in q and any(x in q for x in ('rate', 'apr')):
        category = 'home_equity'
    elif 'home improvement' in q and any(x in q for x in ('rate', 'apr')):
        category = 'home_improvement'
    elif any(x in q for x in ('mortgage', 'construction loan', 'home loan')) and any(x in q for x in ('rate', 'apr', 'interest')):
        category = 'mortgage'
    elif re.search(r'\b(?:autos?|automobiles?|vehicles?|motorcycles?|cars?)\b', q) and any(x in q for x in ('rate', 'apr', 'apy', 'interest')):
        category = 'auto'
    elif 'personal loan' in q and any(x in q for x in ('rate', 'apr', 'interest')):
        category = 'personal'
    elif any(x in q for x in ('boat', 'rv loan', 'atv', 'snowmobile', 'jet ski')) and any(x in q for x in ('rate', 'apr')):
        category = 'recreational'
    elif 'checking' in q and any(x in q for x in ('rate', 'apy', 'interest', 'dividend')):
        category = 'checking'
    elif any(x in q for x in ('savings', 'money market', 'hsa')) and any(x in q for x in ('rate', 'apy', 'interest', 'dividend', 'pay', 'earn')):
        category = 'savings'
    elif (highest_rate or lowest_rate) and re.search(r'\b(accounts?|deposits?)\b', q) and not re.search(r'\b(loans?|debt|borrow)\b', q):
        category = 'deposit'
    term = re.search(r'\b(\d+)\s*[- ]?\s*(month|year)', q)
    term_months = int(term[1]) * (12 if term[2] == 'year' else 1) if term else None
    year = (re.search(r'\b(20\d{2})\s*(?:model(?:[ -]year)?|vehicle|car|truck|motorcycle)\b', q)
            or re.search(r'\bmodel[ -]?year\s+(?:of\s+)?(20\d{2})\b', q)
            or re.search(r'\b(?:vehicle|car|truck|motorcycle)\s+(?:from\s+)?(20\d{2})\b', q))
    balance = re.search(r'\$([\d,]+(?:\.\d+)?)', q)
    product = next((v for k, v in PRODUCT_ALIASES.items() if k in q), None)
    return QueryIntent(question, category, term_months, int(year[1]) if year else None,
                       float(balance[1].replace(',', '')) if balance else None, product, highest_rate, lowest_rate)
