"""Conservative clarification checks before rules select a supported answer."""
from __future__ import annotations

import re

from .query import STOP_WORDS
from ..models.domain import QueryIntent, QuestionFeedback

_FINANCIAL_FACT = r'(?:routing|rates?|interest|apr|apy|certificates?|mortgages?|savings|checking)'
_POSSESSOR = re.compile(
    r"\b([a-z][a-z .&-]*?)[’']s\s+(?=(?:(?:\d+[- ]?(?:month|year)|special|standard)\s+)*"
    + _FINANCIAL_FACT + r'\b)', re.I,
)
_GENERIC_OWNERS = STOP_WORDS | {'which', 'bank', 'credit', 'union', 'account', 'company'}
_TOPICS = (
    r'\brouting\s+(?:number|#)\b',
    r'\b(?:membership|eligible|eligibility|join|become a member)\b',
    r'\b(?:lobby|drive[ -]?up|branches|branch|atm locator)\b',
    r'\b(?:rates?|apr|apy|interest)\b',
    r'\b(?:contact information|phone number|email address)\b',
    r'\b(?:weather|forecast|temperature)\b',
    r'\b(?:poem|story|recipe|song)\b',
)
_NUMBER_WORD = r'(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)'


def _foreign_institution(question: str) -> bool:
    """Reject a named owner of a requested financial fact, rather than substituting Dupaco."""
    owners = [match[1] for match in _POSSESSOR.finditer(question)]
    trailing_owner = re.search(
        r'\brouting\s+number\s+(?:for|of|at)\s+([a-z][a-z .&-]*)[?.!]*$', question, re.I,
    )
    if trailing_owner:
        owners.append(trailing_owner[1])
    for owner in owners:
        words = set(re.findall(r'[a-z]+', owner.lower()))
        if 'dupaco' in words:
            continue
        if words - _GENERIC_OWNERS:
            return True
    return False


def question_issue(question: str) -> str | None:
    if _foreign_institution(question):
        return 'The saved pages only cover Dupaco. I cannot verify another institution’s rates or account details from this data.'
    if re.search(r'(?:-\s*\$\s*|\$\s*-\s*)\d', question):
        return 'Please provide a non-negative deposit or loan amount; I cannot treat a negative amount as a positive balance.'
    terms = {int(value) * (12 if unit.lower().startswith('year') else 1)
             for value, unit in re.findall(r'\b(\d+)\s*[- ]?\s*(months?|years?)\b', question, re.I)}
    if len(terms) > 1:
        return 'Your question includes more than one loan or certificate term. Please ask about one term at a time.'
    if re.search(r'\b' + _NUMBER_WORD + r'(?:[ -]+' + _NUMBER_WORD + r')*[ -]+(?:months?|years?)\b', question, re.I):
        if re.search(r'\b(?:rates?|apr|apy|interest|loan)\b', question, re.I):
            return 'Please write the term and model year using digits, such as “60 months” and “2025 model year,” so I can match the correct rate.'
    # Do not silently answer just the first of several independent requests.
    compound = bool(re.search(r'\band\b|[;?].*\w', question, re.I))
    if compound and sum(bool(re.search(pattern, question, re.I)) for pattern in _TOPICS) > 1:
        return 'Please ask one topic at a time so I can give a complete, supported answer to each part.'
    return None


def requests_forecast(question: str) -> bool:
    return bool(re.search(r'\b(?:will|predict|prediction|forecast|future)\b', question, re.I))


def completeness_feedback(intent: QueryIntent) -> QuestionFeedback:
    """Optional narrowing hints never prevent intentional broad comparisons."""
    question = intent.question.lower()
    broad = bool(re.search(r'\b(?:all|list|compare|every)\b', question))
    if intent.highest_rate or intent.lowest_rate:
        if intent.category in ('deposit', 'savings', 'checking', 'certificate') and intent.balance is None:
            return QuestionFeedback('needs_info', 'Add the amount you would deposit to narrow the comparison to matching balance tiers and minimums. You can also compare all published tiers.')
        return QuestionFeedback('ready', 'Ready to compare the matching published rates.')
    if intent.category in ('auto', 'recreational') and not broad:
        missing = []
        if intent.model_year is None:
            missing.append('vehicle model year')
        if intent.term_months is None:
            missing.append('loan term')
        if missing:
            return QuestionFeedback('needs_info', 'Add the ' + ' and '.join(missing) + ' to narrow the rate—for example, a 2025 model-year vehicle over 60 months. You can also ask for all rates.')
    if intent.category == 'mortgage' and not broad and (intent.balance is None or intent.term_months is None):
        return QuestionFeedback('needs_info', 'Add the loan amount and repayment term for a more specific mortgage rate. You can also ask for all published rates.')
    if intent.category in ('savings', 'checking') and not broad and intent.balance is None:
        return QuestionFeedback('needs_info', 'Add your balance to find the matching account tier, or continue to see the published tiers.')
    if intent.category is None and re.search(r'\b(?:rate|rates|apr|apy|interest)\b', question):
        return QuestionFeedback('needs_info', 'Which product do you mean—for example, a savings account, certificate, or car loan?', True)
    if intent.category is None and not re.search(r'\b(?:routing|branch|branches|lobby|drive|atm|member|membership|eligible|join|fee|fees|contact|address|phone|wallet|debit|overdraft|policy|policies|forbes|volunteer|home\$tart)\b', question):
        return QuestionFeedback('needs_info', 'Try naming the Dupaco product or service you want to know about. I can check saved account, loan, branch, and membership information.')
    return QuestionFeedback('ready', 'Ready to look this up in the saved pages.')
