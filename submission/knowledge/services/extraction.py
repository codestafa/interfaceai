"""Extract qualified financial facts from labeled tables and card descriptions."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models.domain import Document, Evidence, Fact
from .markdown import plain

PERCENT = re.compile(r'\d+(?:\.\d+)?%')


def normalized(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().replace('–', '-').replace('—', '-').replace(',', '')).strip()


def authority(document: Document, category: str) -> int:
    path = urlparse(document.url).path.rstrip('/')
    preferred = {
        'certificate': ('/personal/savings-account',), 'savings': ('/personal/savings-account', '/savings-account/online-savings-account'),
        'checking': ('/personal/checking-accounts',), 'auto': ('/personal/loans/auto-motorcycle-loans',),
        'mortgage': ('/personal/loans/home-loans',), 'personal': ('/personal/loans/personal-loans',),
        'card': ('/personal/credit-cards', '/business/credit-cards'),
    }
    if path in preferred.get(category, ()):
        return 100
    if path in ('/rates', '/business-rates'):
        return 90
    if '/calculators/' in path or 'calculator' in path:
        return 20
    if '/learn/' in path or '/newsroom/' in path:
        return 30
    return 60


def _category(headers: tuple[str, ...], context: str, row: tuple[str, ...]) -> str | None:
    h, c = ' '.join(headers).lower(), context.lower()
    if 'apy' in h or 'annual percentage yield' in h:
        if any(w in h for w in ('certificate', 'ira type')) or 'month' in row[0].lower():
            return 'ira' if 'ira' in h or any(s in row[0].lower() for s in ('roth', 'traditional')) else 'certificate'
        return 'ira' if 'ira' in c or row[0].lower().startswith(('roth:', 'traditional:')) else 'checking' if 'checking' in row[0].lower() or 'checking' in c else 'savings'
    if 'apr' not in h and 'annual percentage rate' not in h:
        return None
    if 'card type' in h or 'credit card' in h or 'visa' in h:
        return 'card'
    if 'points' in h or ('program' in h and 'rate' in h and 'term' not in h):
        return 'mortgage'
    if 'model year' in row[0].lower():
        return 'recreational' if any(x in c for x in ('atv', 'snowmobile', 'jet ski')) else 'auto'
    if 'heloc' in c or 'heloc' in row[0].lower():
        return 'heloc'
    if 'home equity' in c:
        return 'home_equity'
    if 'home improvement' in c:
        return 'home_improvement'
    if 'boat' in c or 'rv ' in c:
        return 'recreational'
    if headers[0].lower() == 'term' or 'personal loan' in c:
        return 'personal'
    return None


def _term(text: str) -> str:
    match = re.search(r'(\d+)\s*[- ]?\s*(month|mo\b|year)', text, re.I)
    return str(int(match[1]) * (12 if match[2].lower() == 'year' else 1)) if match else ''


def _model_years(text: str) -> list[int]:
    match = re.search(r'(20\d{2})(?:\s*[-–]\s*(\d{2,4}))?', text)
    if not match:
        return []
    first, last = int(match[1]), int(match[2] or match[1])
    if last < 100:
        last += first // 100 * 100
    if 'older' in text.lower():
        return [first]  # A bounded qualifier handles older vehicles at query time.
    return list(range(min(first, last), max(first, last) + 1))


def extract_facts(document: Document) -> tuple[Fact, ...]:
    facts = []
    for table in document.tables:
        for row in table.rows:
            category = _category(table.headers, table.heading, row)
            if not category:
                continue
            entity = row[0]
            qualifiers = {}
            if category in ('savings', 'checking', 'certificate', 'ira'):
                qualifiers['customer_type'] = 'business' if '/business' in urlparse(document.url).path else 'personal'
            if table.headers[0].lower() in ('balance', 'balance tier'):
                context = table.heading + ' ' + document.title
                labels = ('Share Savings', 'Bright Savings', 'High-Yield Savings', 'Health Savings Account',
                          '1st Rate Checking', 'Free Checking', 'Achieve Money Market', 'Launchpad Savings')
                entity = next((label for label in labels if label.lower() in context.lower()), table.heading.split('|')[-1].strip())
                if 'investor' in context.lower():
                    entity = "Investor's Choice Money Market"
                if 'health' in context.lower() or 'hsa' in context.lower():
                    entity = 'Health Savings Account'
                if category == 'ira':
                    entity = row[0].split(':')[0] + ' Variable IRA'
            if category == 'card' and 'visa' in table.headers[0].lower():
                entity = table.headers[0]
            intro_values = []
            if category == 'card':
                if entity.lower() == 'standard':
                    entity = 'Rewards Visa' if 'reward' in table.heading.lower() else table.heading.split('|')[-1].strip()
                if 'intro' in entity.lower():
                    entity = 'Platinum Visa'
                    qualifiers['offer'] = 'introductory'
                else:
                    entity = re.sub(r'\s+Rate$', '', entity, flags=re.I)
                    qualifiers['offer'] = 'standard'
            if category == 'certificate' and 'certificate' not in entity.lower():
                entity += ' Certificate'
            values = []
            for header, value in zip(table.headers, row):
                h = header.lower()
                if h == 'term' or h in ('certificate', 'ira type', 'program', 'product'):
                    term = _term(value)
                    if term:
                        qualifiers['term_months'] = term
                if h in ('balance tier', 'balance', 'loan amount'):
                    qualifiers['balance'] = normalized(value)
                    qualifiers['balance_label'] = value
                if h in ('min. to earn', 'min. to open'):
                    qualifiers['minimum' if 'earn' in h else 'opening_minimum'] = value
                percentages = PERCENT.findall(value)
                if not percentages:
                    continue
                if 'yield' in h or 'apy' in h:
                    attribute = 'APY'
                elif 'apr' in h or 'annual percentage rate' in h:
                    attribute = 'APR'
                elif 'rate' in h:
                    attribute = 'Dividend rate' if 'dividend' in h else 'Interest rate'
                else:
                    continue
                if 'intro' in h or '1st' in h or 'first' in h:
                    intro_values.append((attribute, '–'.join(percentages)))
                else:
                    # An introductory card row may describe its later standard
                    # APR too. The row's advertised intro rate is the first one.
                    if qualifiers.get('offer') == 'introductory':
                        percentages = percentages[:1]
                    values.append((attribute, '–'.join(percentages)))
            if not values:
                continue
            if category in ('certificate', 'ira'):
                qualifiers['term_months'] = _term(entity)
                qualifiers['tier'] = 'jumbo' if 'jumbo' in entity.lower() else 'standard'
                qualifiers['offer'] = 'special' if 'special' in entity.lower() else 'regular'
            if category in ('auto', 'recreational') and 'model year' in entity.lower():
                qualifiers['model_year_label'] = entity
                qualifiers['older'] = str('older' in entity.lower())
                entity = 'Auto loan' if category == 'auto' else 'Recreational vehicle loan'
                years = _model_years(row[0])
            else:
                years = []
            if category == 'mortgage':
                qualifiers['purpose'] = 'refinance' if 'refinance' in entity.lower() else 'purchase'
                amount = re.search(r'\$([\d,]+)', entity)
                if amount:
                    qualifiers['loan_limit'] = amount[1].replace(',', '')
                entity = 'Fixed mortgage' if 'fixed' in entity.lower() else entity
            if category == 'personal':
                entity = 'Personal loan'
            quote = table.heading + '\n' + ' | '.join(f'{h}: {v}' for h, v in zip(table.headers, row))
            evidence = Evidence(document.url, document.snapshot_id, quote)
            base = dict(category=category, entity=entity, values=tuple(values), evidence=evidence,
                        authority=authority(document, category), effective_on=table.effective_on, expires_on=table.expires_on)
            for year in years or [None]:
                variant = dict(qualifiers)
                if year is not None:
                    variant['model_year'] = str(year)
                facts.append(Fact(qualifiers=tuple(sorted(variant.items())), **base))
                if intro_values:
                    introductory = dict(variant, offer='introductory')
                    facts.append(Fact(qualifiers=tuple(sorted(introductory.items())),
                                      **dict(base, values=tuple(intro_values))))
    # Product pages sometimes advertise card ranges in prose instead of tables.
    if urlparse(document.url).path.rstrip('/') in ('/personal/credit-cards', '/business/credit-cards'):
        for section in document.sections:
            if 'visa' not in section.heading.lower():
                continue
            for line in section.text.splitlines():
                if ('apr' not in line.lower() and 'percentage rate' not in line.lower()) or any(word in line.lower() for word in ('intro', 'new cardmember', 'after that')):
                    continue
                percentages = PERCENT.findall(line)
                if percentages:
                    facts.append(Fact('card', plain(section.heading), (('offer', 'standard'),),
                                      (('APR', '–'.join(percentages)),),
                                      Evidence(document.url, document.snapshot_id, line), authority(document, 'card')))
    return tuple(facts)
