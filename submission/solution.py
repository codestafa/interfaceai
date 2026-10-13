"""Evaluator entrypoint; both the browser and harness use this factory."""
from pathlib import Path
import sys

if __package__:
    from .knowledge.controllers.knowledge import KnowledgeController
else:
    # The harness loads this file dynamically from an arbitrary team folder.
    _submission_dir = str(Path(__file__).resolve().parent)
    if _submission_dir not in sys.path:
        sys.path.insert(0, _submission_dir)
    from knowledge.controllers.knowledge import KnowledgeController


def build() -> KnowledgeController:
    return KnowledgeController()
