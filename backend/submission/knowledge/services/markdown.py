"""Parse source Markdown without executing links, HTML, or document instructions."""
from __future__ import annotations

from datetime import datetime
from html import unescape
import re

from ..models.domain import Section, Table

LINK = re.compile(r'(?<!!)\[([^\]]*)\]\(([^\s)]+)(?:\s+"[^"]*")?\)')
DATE = r'(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})'


def plain(text: str) -> str:
    text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', text)
    text = LINK.sub(r'\1', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return unescape(text).replace('\\r\\n', ' ').replace('\\', '').replace('**', '').replace('__', '').strip()


def parse_date(text: str):
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%B %d, %Y', '%B %d %Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _cells(line: str) -> tuple[str, ...]:
    return tuple(plain(cell).strip() for cell in line.strip().strip('|').split('|'))


def parse_markdown(markdown: str) -> tuple[tuple[Section, ...], tuple[Table, ...]]:
    lines = markdown.replace('\xa0', ' ').splitlines()
    sections, tables = [], []
    heading, context, paragraph = '', [], []

    def flush():
        if paragraph:
            text = plain('\n'.join(paragraph))
            if text:
                sections.append(Section(heading, text))
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|[\s:|\-]+\|\s*$', lines[i + 1]):
            flush()
            headers = _cells(line)
            preceding_lines = []
            for previous_line in reversed(lines[:i]):
                if previous_line.strip().startswith('|'):
                    break
                if previous_line.strip():
                    preceding_lines.append(previous_line)
                if len(preceding_lines) == 5:
                    break
            preceding = plain(' '.join(reversed(preceding_lines)))
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = _cells(lines[i])
                if len(row) == len(headers):
                    rows.append(row)
                i += 1
            following_lines = []
            for next_line in lines[i:]:
                if next_line.strip().startswith(('|', '#')):
                    break
                if next_line.strip():
                    following_lines.append(next_line)
                if len(following_lines) == 5:
                    break
            following = plain('\n'.join(following_lines))
            effective = re.search(r'(?:effective\s+(?:as of\s*|on\s*)?)' + DATE, following, re.I) or re.search(r'(?:effective\s+(?:as of\s*|on\s*)?)' + DATE, preceding, re.I)
            expiry = re.search(r'(?:expires?|ends?|valid through|available through)\s+(?:on\s+)?' + DATE, following + ' ' + preceding, re.I)
            tables.append(Table(' | '.join([heading] + context[-2:]), headers, tuple(rows),
                                parse_date(effective[1]) if effective else None,
                                parse_date(expiry[1]) if expiry else None))
            context = []
            continue
        if line.startswith('#'):
            flush()
            heading = plain(line.lstrip('#').strip())
            context = []
        elif not line:
            flush()
        else:
            paragraph.append(line)
            if len(line) < 120 and not line.startswith(('[', '!', '-', '*')):
                context.append(plain(line))
        i += 1
    flush()
    return tuple(sections), tuple(tables)
