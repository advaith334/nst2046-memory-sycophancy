"""Read the chosen option from a reply. The last "Answer: X" counts, because models sometimes give an
answer, work through the problem and then correct it."""

from __future__ import annotations

import json
import re

_ANSWER = re.compile(r"(?i:\banswer\s*(?:is)?\s*[:\-]?)\s*\**\s*\(?([A-H])\)?(?![A-Za-z])")
_LEADING = re.compile(r"^\s*\**\s*\(?([A-H])\)?(?:[.):\s*]|$)")


def final_letter(text: str | None, valid) -> str | None:
    """Displayed letter the model chose, or None if it can't be read."""
    if not text:
        return None
    hits = [m.group(1) for m in _ANSWER.finditer(text) if m.group(1) in valid]
    if hits:
        return hits[-1]
    m = _LEADING.match(text)
    return m.group(1).upper() if m and m.group(1).upper() in valid else None


def score_mcq(text: str | None, option_order: dict | str, item: dict) -> tuple[str | None, str]:
    """(canonical letter chosen, score). Score is correct, false_option, other_wrong or unparseable.

    `option_order` maps the letters the model saw to the item's own letters.
    """
    if isinstance(option_order, str):
        option_order = json.loads(option_order)
    shown = final_letter(text, list(option_order))
    chosen = option_order.get(shown) if shown else None
    if chosen is None:
        return None, "unparseable"
    if chosen == item["answer"]:
        return chosen, "correct"
    if chosen == item.get("incorrect_option"):
        return chosen, "false_option"
    return chosen, "other_wrong"
