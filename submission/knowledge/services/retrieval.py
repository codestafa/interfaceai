"""Conservative lexical retrieval for non-financial questions beyond named topics."""
from collections import Counter
import math

from ..models.domain import Evidence, Resolution, SnapshotState
from .query import tokens


def retrieve(question: str, state: SnapshotState) -> Resolution:
    query = tokens(question)
    if not query:
        return Resolution('Please enter a question about the supplied website snapshots.', confident=False)
    scores = Counter()
    for token in query:
        matches = state.index.get(token, ())
        weight = math.log(1 + len(state.documents) / (1 + len(matches)))
        for index in matches:
            scores[index] += weight
    candidates = []
    for index, _ in scores.most_common(12):
        document = state.documents[index]
        for section in document.sections:
            if len(section.text) < 35 or len(section.text) > 1800 or section.text.startswith('|'):
                continue
            terms = tokens(section.heading + ' ' + section.text)
            overlap = query & terms
            score = sum(math.log(1 + len(state.documents) / (1 + len(state.index.get(t, ())))) for t in overlap)
            if len(overlap) >= 2 and len(overlap) / len(query) >= 0.6:
                candidates.append((score, document, section))
    if not candidates:
        return Resolution('I could not find enough matching evidence in the selected snapshot to answer reliably.', confident=False)
    candidates.sort(key=lambda item: (-item[0], item[1].url, item[2].text))
    _, document, section = candidates[0]
    return Resolution('The closest relevant source passage is:\n' + section.text,
                      (Evidence(document.url, document.snapshot_id, section.text),), False,
                      'This passage was retrieved by keywords; a precise answer could not be verified.')
