"""The only dependency on the participant harness; preserve its class identity."""
from pathlib import Path
import sys

# The evaluator imports `contract` as a top-level module. Browser imports must do
# the same so both entrypoints return the exact supplied contract dataclasses.
_harness = next((p / 'harness' for p in Path(__file__).resolve().parents if (p / 'harness' / 'contract.py').is_file()), None)
if _harness is None:
    raise ImportError('Place the submission beside the participant harness directory.')
if str(_harness) not in sys.path:
    sys.path.insert(0, str(_harness))
from contract import Answer, Conflict, Page, Snapshot, Source  # noqa: E402,F401
