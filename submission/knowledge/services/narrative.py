"""Source-derived answers for branch, institutional, and member-service questions.

The routing vocabulary is domain knowledge; dates, claims, addresses, and links
always come from the selected snapshot. News publication dates are retained so
an archived announcement does not silently override a newer one.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
import re
from urllib.parse import urlparse

from ..models.domain import Disagreement, Document, Evidence, Fact, Resolution

_MONTH_DATE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
_BOILERPLATE = re.compile(r"\n(?:#{1,6}\s+Handpicked for You|\*\*ABOUT |ABOUT DUPACO)", re.I)
_STOP_WORDS = set("what which where when how why can could would should does do is are was were will be the a an of on in to for from with and or it its your my me i you dupaco have has tell please give all any more about get find information".split())


def _plain(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_#]", "", text)
    return re.sub(r"\s+", " ", text).strip(" -")


def _body(document: Document, *, include_about: bool = False) -> str:
    pattern = r"\n#{1,6}\s+Handpicked for You" if include_about else _BOILERPLATE
    return re.split(pattern, document.markdown, maxsplit=1)[0]


def _published(document: Document) -> date:
    """Read publication metadata, including the archive's abbreviated months."""
    prefix = document.markdown[:1500]
    month_date = re.search(r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s+\d{4}", prefix, re.I)
    if month_date:
        for format_string in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(month_date.group(), format_string).date()
            except ValueError:
                pass
    iso = re.search(r"(?:^|\n)\s*(?:(?:Published|Updated|Date):?\s*)?(\d{4}-\d{2}-\d{2})\b", prefix, re.I)
    if iso:
        try:
            return date.fromisoformat(iso.group(1))
        except ValueError:
            pass
    return date.min


def _evidence(document: Document, quote: str) -> Evidence:
    return Evidence(document.url, document.snapshot_id, _plain(quote)[:650])


def _answer(text: str, document: Document, quote: str, *, confident: bool = True,
            conflict_note: str | None = None) -> Resolution:
    return Resolution(text, (_evidence(document, quote),), confident, conflict_note)


def _preferred(documents: tuple[Document, ...], path: str) -> Document | None:
    return next((doc for doc in documents if urlparse(doc.url).path.rstrip("/") == path), None)


def _paragraphs(document: Document, *, include_about: bool = False) -> list[str]:
    return [_plain(p) for p in re.split(r"\n\s*\n", _body(document, include_about=include_about))
            if _plain(p) and not p.lstrip().startswith(("!", "#"))]


def _latest(documents: list[Document], requested_date: date) -> Document | None:
    applicable = [doc for doc in documents if _published(doc) <= requested_date]
    return max(applicable, key=lambda doc: (_published(doc), doc.url), default=None)


def _authority(document: Document) -> int:
    """Dedicated contact and product pages outrank archived editorial mentions."""
    path = urlparse(document.url).path.lower()
    return 40 if any(part in path for part in ("/newsroom/", "/learn/blog/")) else 100


def _branch_identity(document: Document, prefix: str) -> str | None:
    """Only explicit branch names form shared keys; generic articles stay separate."""
    headings = re.findall(r"^#{1,6}\s+(.+)$", prefix, re.M)
    contexts = list(reversed(headings)) + [document.title, _plain(prefix)]
    pattern = r"\b([A-Z][\w'’-]*(?:\s+[A-Z][\w'’-]*){0,3})\s+[Bb]ranch\b"
    excluded = {"dupaco", "dupaco community credit union", "learning lab", "newest", "new", "the", "our", "general", "all", "local"}
    for context in contexts:
        for match in re.finditer(pattern, context):
            name = re.sub(r"^(?:The|Our|Dupaco)\s+", "", match.group(1)).strip()
            if name.lower() not in excluded and "credit union" not in name.lower():
                return name
    return None


def _hours_claims(document: Document) -> tuple[Fact, ...]:
    body = _body(document)
    # Supports both the supplied bold labels and ordinary Markdown headings.
    marker = re.compile(r"^(?:#{1,6}\s*|\*\*)(Lobby|Drive[ -]?(?:up|through|thru))(?:\s+hours)?(?:\*\*)?\s*:?\s*", re.I | re.M)
    markers = list(marker.finditer(body))
    claims = []
    for index, match in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        content = re.split(r"\n\s*(?:#{1,6}\s|\*\*[A-Za-z])", body[match.end():end], maxsplit=1)[0]
        schedule = _plain(content).replace("–", "-").replace("—", "-")
        if not re.search(r"\b(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?|weekdays|weekends)\b", schedule, re.I):
            continue
        name = _branch_identity(document, body[:match.start()]) or document.url
        kind = "lobby" if match.group(1).lower() == "lobby" else "drive-up"
        claims.append(Fact("branch_hours", name, (("kind", kind),), (("text", schedule),),
                           _evidence(document, content), _authority(document),
                           effective_on=_published(document)))
    return tuple(claims)


def _narrative_claims(documents: tuple[Document, ...], day: date, category: str) -> tuple[Fact, ...]:
    """Extract typed claims once per requested topic, retaining evidence and dates."""
    claims = []
    for document in documents:
        published = _published(document)
        if published > day:
            continue
        if category == "branch_hours":
            claims.extend(_hours_claims(document))
            continue
        body = _body(document, include_about=True)
        if category == "routing":
            pattern = r"routing\s+(?:number|#)\s*[:*\s]*(\d{9})"
        else:
            pattern = r"\b(\d+)\s+branch office locations\b|\b(?:Dupaco(?:\s+Credit Union)?|We)\s+(?:has|have|operates?|maintains?)\s+(\d+)\s+(?:full.service\s+)?branches\b"
        for match in re.finditer(pattern, body, re.I):
            value = next(group for group in match.groups() if group is not None)
            claims.append(Fact(category, "Dupaco", (), (("text", value),),
                               _evidence(document, match.group()), _authority(document),
                               effective_on=published))
    return tuple(dict.fromkeys(claims))


def _value(claim: Fact) -> str:
    return dict(claim.values)["text"]


def _current_claims(claims: tuple[Fact, ...]) -> tuple[Fact, ...]:
    if not claims:
        return ()
    # Routing is an institutional identity: prefer its direct official pages.
    # Branch counts and schedules are dated states, so newer statements supersede
    # old announcements before considering equal-date source authority.
    if claims[0].category == "routing":
        authority = max(claim.authority for claim in claims)
        claims = tuple(claim for claim in claims if claim.authority == authority)
    newest = max(claim.effective_on or date.min for claim in claims)
    return tuple(claim for claim in claims if (claim.effective_on or date.min) == newest)


def _winner(claims: tuple[Fact, ...]) -> tuple[Fact | None, tuple[Fact, ...]]:
    current = _current_claims(claims)
    if not current:
        return None, ()
    authority = max(claim.authority for claim in current)
    preferred = tuple(claim for claim in current if claim.authority == authority)
    if len({_value(claim).lower() for claim in preferred}) != 1:
        return None, preferred
    return preferred[0], current


def narrative_conflicts(documents: tuple[Document, ...], day: date) -> tuple[Disagreement, ...]:
    """Report contradictions within the same topic, named branch, metric and date.

    Different publication dates are historical changes, not contradictions.
    Unnamed branch announcements are deliberately never merged by title.
    """
    conflicts = []
    for category in ("routing", "branch_hours", "branch_count"):
        groups: dict[tuple, list[Fact]] = {}
        for claim in _narrative_claims(documents, day, category):
            if category == "branch_hours" and claim.entity.startswith(("http://", "https://")):
                continue
            if category in ("branch_count", "branch_hours") and claim.effective_on == date.min and claim.authority < 100:
                # Undated archived announcements cannot establish that two
                # different states applied at the same time.
                continue
            groups.setdefault((claim.entity.lower(), claim.qualifiers, claim.effective_on), []).append(claim)
        for group in groups.values():
            values = tuple(dict.fromkeys(_value(claim) for claim in group))
            if len({value.lower() for value in values}) < 2:
                continue
            winner, _ = _winner(tuple(group))
            first = group[0]
            if category == "branch_hours":
                topic = f"{first.entity} branch {first.qualifier('kind')} hours"
            else:
                topic = "Dupaco routing number" if category == "routing" else "Dupaco branch count"
            when = first.effective_on
            if when and when != date.min:
                topic += f" ({when.isoformat()})"
            reason = ("The direct official page has greater authority than the competing editorial source."
                      if winner else "Equally authoritative sources disagree for the same applicable date; no value is selected.")
            conflicts.append(Disagreement(topic, values, tuple(dict.fromkeys(c.evidence for c in group)),
                                          _value(winner) if winner else None, reason))
    return tuple(conflicts)


def _routing(documents: tuple[Document, ...], day: date) -> Resolution | None:
    claims = _narrative_claims(documents, day, "routing")
    winner, current = _winner(claims)
    if not current:
        return None
    if not winner:
        return Resolution("The authoritative routing-number sources disagree. I cannot provide a reliable routing number from this snapshot.",
                          tuple(claim.evidence for claim in current), False,
                          "Equal-authority routing-number claims conflict; verify with Dupaco before using a number.")
    return Resolution(f"Dupaco's routing number is {_value(winner)}.", (winner.evidence,))

def _hy_vee(question: str, documents: tuple[Document, ...], day: date) -> Resolution | None:
    doc = _latest([d for d in documents if "hy-vee" in d.title.lower()
                   and re.search(r"clos", d.title, re.I)], day)
    if not doc:
        return None
    body = _plain(_body(doc))
    match = re.search(r"(?:will close|close[sd]? on|closure (?:date|on))\s+(" + _MONTH_DATE + ")", body, re.I)
    alternatives = next((p for p in _paragraphs(doc) if "same services" in p.lower()
                         and "branches" in p.lower()), None)
    if re.search(r"where|alternative|full.service|instead|members go", question, re.I) and alternatives:
        return _answer(alternatives, doc, alternatives)
    if match:
        closure = datetime.strptime(match.group(1), "%B %d, %Y").date()
        if re.search(r"open|still|today", question, re.I):
            status = "No. The published closure date for the Hy-Vee branch was" if day >= closure else "The Hy-Vee branch is scheduled to close"
            text = f"{status} {match.group(1)}."
        else:
            text = f"The Hy-Vee branch closure date is {match.group(1)}."
        return _answer(text, doc, match.group())
    return None


def _named_branch(question: str) -> str | None:
    """Identify an explicitly named location without treating 'all branches' as one."""
    match = re.search(r"\b(?:for|of|at)\s+(?:the\s+)?(.+?)\s+branch\b", question, re.I)
    if not match:
        match = re.search(r"(?:the\s+)([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3})\s+branch\b", question)
    if not match:
        match = re.search(r"\b([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3})\s+[Bb]ranch\b", question)
    if match:
        name = match.group(1).strip()
        if name.lower() not in {"all", "all dupaco", "a", "each", "your", "dupaco", "any", "nearest", "general", "which", "what"}:
            return name
    return None


def _hours(question: str, documents: tuple[Document, ...], day: date) -> Resolution:
    kind = "drive-up" if re.search(r"drive[ -]?(?:up|through|thru)", question, re.I) else "lobby"
    named = _named_branch(question)
    candidates = documents
    if named:
        candidates = tuple(doc for doc in documents if named.lower() in (_plain(_body(doc)) + " " + doc.title).lower())
    claims = tuple(claim for claim in _narrative_claims(candidates, day, "branch_hours") if claim.qualifier("kind") == kind)
    if not claims:
        location = f" for the {named} branch" if named else ""
        return Resolution(f"The selected snapshot does not provide grounded {kind} hours{location}. Check the branch locator or contact Dupaco for the exact schedule.", confident=False)
    if named:
        winner, current = _winner(claims)
        if not winner:
            return Resolution(f"Published {kind} schedules for {named} disagree; I cannot choose a reliable schedule.", tuple(claim.evidence for claim in current), False,
                              "Equal-authority schedules for the same branch and date conflict.")
        return Resolution(f"{named} {kind} hours: {_value(winner)}", (winner.evidence,))
    groups: dict[str, list[Fact]] = {}
    for claim in claims:
        groups.setdefault(claim.entity.lower(), []).append(claim)
    resolved = [winner for group in groups.values() if (winner := _winner(tuple(group))[0]) is not None]
    if not resolved:
        return Resolution(f"The published {kind} schedules conflict; no reliable general schedule is available.", confident=False)
    counts = Counter(_value(claim) for claim in resolved)
    ordered = sorted(resolved, key=lambda claim: (-counts[_value(claim)], _value(claim), claim.evidence.url))
    unique: dict[str, Fact] = {}
    for claim in ordered:
        unique.setdefault(_value(claim), claim)
    selected = list(unique.values())[:4]
    text = f"{kind.capitalize()} hours vary by branch. Published schedules include:\n" + "\n".join(f"- {_value(claim)}" for claim in selected)
    text += "\nWhich branch, or all branches, would you like hours for?"
    return Resolution(text, tuple(claim.evidence for claim in selected))


def _branch_address(question: str, documents: tuple[Document, ...]) -> Resolution | None:
    doc = _preferred(documents, "/contact")
    if not doc:
        return None
    named = _named_branch(question)
    if not named:
        return None
    for paragraph in re.split(r"\n\s*\n", doc.markdown):
        line = _plain(paragraph)
        if named.lower() in line.lower() and re.match(r"\d+\s", line) and re.search(r"\b\d{5}(?:-\d{4})?\b", line):
            return _answer(f"The {named} branch address is {line}.", doc, paragraph)
    return Resolution(f"The selected snapshot does not list an address for the {named} branch.", confident=False)


def _branch_count(documents: tuple[Document, ...], day: date) -> Resolution | None:
    claims = _narrative_claims(documents, day, "branch_count")
    winner, current = _winner(claims)
    if not current:
        return None
    if not winner:
        return Resolution("The latest published branch counts disagree, so the total is uncertain.",
                          tuple(claim.evidence for claim in current), False,
                          "Equally authoritative branch counts disagree for the same publication date.")
    text = f"Dupaco has {_value(winner)} branch office locations, according to its latest dated statement in this snapshot"
    if winner.effective_on and winner.effective_on != date.min:
        text += f" ({winner.effective_on.isoformat()})"
    note = None
    if any(_value(claim) != _value(winner) for claim in claims):
        note = "Older dated announcements contain different branch counts. The most recent applicable statement supplies the total; those historical counts are not current alternatives."
    return Resolution(text + ".", (winner.evidence,), True, note)


def _forbes(documents: tuple[Document, ...], day: date) -> Resolution | None:
    doc = _latest([d for d in documents if "forbes" in d.title.lower()
                   and "credit union" in d.title.lower()], day)
    if doc:
        for paragraph in _paragraphs(doc):
            if re.search(r"(?:time|year).*Forbes|Forbes.*(?:named|recognized)", paragraph, re.I):
                return _answer(paragraph, doc, paragraph)
    return None


def _membership(question: str, documents: tuple[Document, ...]) -> Resolution | None:
    doc = _preferred(documents, "/about/join")
    if not doc:
        return None
    if re.search(r"online|how (?:do|can|to)|join (?:dupaco|you)|sign up|application", question, re.I) and not re.search(r"eligible|who|qualif", question, re.I):
        match = re.search(r"\[(?:Become a member|Join Dupaco|Join now)\]\((https?://[^)]+)\)", doc.markdown, re.I)
        if match:
            return _answer(f"Join Dupaco online at {match.group(1)}.", doc, match.group())
    match = re.search(r"#{1,6}[^\n]*Eligible to Join[^\n]*\n(.*?)(?=\n#{1,6} |$)", doc.markdown, re.I | re.S)
    if not match:
        match = re.search(r"(- You live or work.*?)(?=\n#{1,6} |$)", doc.markdown, re.S)
    if match:
        text = "You are eligible if any of these apply: " + _plain(match.group(1))
        locations = next((p for p in _paragraphs(doc) if "Iowa" in p and "Wisconsin" in p), "")
        if locations:
            text += " " + locations.split("And if")[0].strip()
        return _answer(text, doc, match.group(1) + " " + locations)
    return None


def _update_contact(documents: tuple[Document, ...]) -> Resolution | None:
    for doc in documents:
        if "privacy" not in doc.url:
            continue
        for paragraph in _paragraphs(doc, include_about=True):
            if re.search(r"review and change your personal information", paragraph, re.I):
                # Keep the supported update methods, avoiding unrelated policy text.
                text = re.split(r"We may not accommodate", paragraph)[0].strip()
                return _answer(text, doc, paragraph)
    return None


def _volunteer(question: str, documents: tuple[Document, ...], day: date) -> Resolution | None:
    records: list[tuple[int, str, Document, str]] = []
    for doc in documents:
        if "volunteer" not in doc.title.lower() or _published(doc) > day:
            continue
        for line in _body(doc).splitlines():
            paragraph = _plain(line)
            match = re.search(r"(\d+)\s+Dupaco employees.*?used.*?\b(20\d{2})\b.*?Volunteer Time Off", paragraph, re.I)
            if match:
                records.append((int(match.group(2)), match.group(1), doc, paragraph))
    if not records:
        return None
    years = re.findall(r"\b20\d{2}\b", question)
    requested_year = int(years[-1]) if years else day.year - 1 if "last year" in question.lower() else None
    matching = [record for record in records if record[0] == requested_year] if requested_year else []
    selected = sorted(matching or records, key=lambda item: (-item[0], item[2].url))
    unique = {year: (year, count, doc, quote) for year, count, doc, quote in reversed(selected)}
    selected = list(unique.values())
    text = "; ".join(f"{count} employees used Volunteer Time Off in {year}" for year, count, _, _ in selected) + "."
    if requested_year and not matching:
        text = f"The snapshot does not publish a count for {requested_year}. Available dated figures: " + text
    return Resolution(text, tuple(_evidence(doc, quote) for _, _, doc, quote in selected), bool(matching or not requested_year))


def _student(question: str, documents: tuple[Document, ...]) -> Resolution | None:
    doc = _preferred(documents, "/personal/loans/student-loans")
    if not doc:
        return None
    interests = ["flexible", "origination", "prepayment", "funding gap"]
    if "refinanc" in question.lower():
        interests += ["refinance", "federal loans", "eligibility"]
    paragraphs = [p for p in _paragraphs(doc) if any(term in p.lower() for term in interests)
                  and not p.startswith(("Apply for", "Undergraduate and"))]
    if paragraphs:
        text = "Student loans and refinancing: " + " ".join(paragraphs[:5])
        return _answer(text, doc, " ".join(paragraphs[:5]))
    return None


def _wallet(documents: tuple[Document, ...], day: date) -> Resolution | None:
    candidates = [d for d in documents if re.search(r"mobile.?wallet|mobile.?payment", d.title + " " + d.url, re.I)]
    doc = _latest(candidates, day)
    if doc:
        paragraphs = [p for p in _paragraphs(doc) if "add your Dupaco cards" in p or
                      ("debit" in p.lower() and "credit" in p.lower()) or "default" in p.lower()]
        if paragraphs:
            return _answer("Yes. " + " ".join(paragraphs[:4]), doc, " ".join(paragraphs[:4]))
    return None


def _homestart(documents: tuple[Document, ...], day: date) -> Resolution | None:
    doc = _latest([d for d in documents if re.search(r"home[$s]?tart", d.title, re.I)], day)
    if doc:
        paragraph = next((p for p in _paragraphs(doc) if re.search(r"\$[\d,]+", p) and "assistance" in p), None)
        if paragraph:
            return _answer(paragraph, doc, paragraph)
    return None


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2 and word not in _STOP_WORDS}


def _fallback(question: str, documents: tuple[Document, ...], day: date) -> Resolution | None:
    """Conservative extractive retrieval for policies not covered by an exact route.

    Never manufacture a yes/no answer from lexical similarity. Require topic
    coverage in both a page title and the quoted paragraph, and label uncertainty.
    """
    query = _tokens(question)
    if len(query) < 2 or re.search(r"\b(?:rate|apr|apy|percent|hours|address)\b", question, re.I):
        return None
    candidates: list[tuple[float, Document, str]] = []
    for doc in documents:
        if _published(doc) > day or not (_tokens(doc.title) & query):
            continue
        title_overlap = len(_tokens(doc.title) & query)
        for paragraph in _paragraphs(doc):
            overlap = len(_tokens(paragraph) & query)
            if len(paragraph) >= 60 and overlap >= 2 and overlap / len(query) >= .6:
                candidates.append((overlap + title_overlap / 2, doc, paragraph))
    if candidates:
        _, doc, paragraph = max(candidates, key=lambda item: (item[0], _published(item[1]), item[1].url))
        return _answer("Related information in the selected snapshot: " + paragraph, doc, paragraph, confident=False)
    return None


def answer_narrative(question: str, documents: tuple[Document, ...], requested_date: date) -> Resolution | None:
    """Answer from documents belonging only to the controller-selected snapshot."""
    q = question.lower()
    if re.search(r"routing|aba (?:number|code)", q):
        return _routing(documents, requested_date)
    if "hy-vee" in q or "hy vee" in q:
        return _hy_vee(question, documents, requested_date)
    if re.search(r"\bhours\b|(?:when|what time).*(?:open|close)", q) and re.search(r"branch|lobby|drive[ -]?(?:up|through|thru)", q):
        return _hours(question, documents, requested_date)
    if ("address" in q or "where" in q) and "branch" in q and _named_branch(question):
        return _branch_address(question, documents)
    if re.search(r"(?:how many|number of|total).*branch", q):
        return _branch_count(documents, requested_date)
    if re.search(r"locator|(?:url|link|website).*(?:branch|atm)", q):
        doc = _preferred(documents, "/contact")
        if doc:
            return _answer(f"Dupaco's branch and ATM locator is at {doc.url}.", doc, "Find a Location Near You")
    if "forbes" in q:
        return _forbes(documents, requested_date)
    if re.search(r"(?:update|change|correct).*(?:contact|personal|address|phone|email)", q):
        return _update_contact(documents)
    if re.search(r"join|become.*member|membership eligib|eligible.*member|who.*member", q):
        return _membership(question, documents)
    if re.search(r"volunteer|\bvto\b", q):
        return _volunteer(question, documents, requested_date)
    if re.search(r"student|university|college.*loan", q):
        return _student(question, documents)
    if re.search(r"mobile wallet|digital wallet|apple pay|google pay|samsung pay", q):
        return _wallet(documents, requested_date)
    if re.search(r"home[$s]?tart", q):
        return _homestart(documents, requested_date)
    return _fallback(question, documents, requested_date)
