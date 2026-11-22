"""Basic educational-use and urgent-care safety handling."""

import re

from config import DISCLAIMER


URGENT_PATTERNS = (
    r"chest pain", r"difficulty breathing", r"shortness of breath", r"can't breathe", r"cannot breathe",
    r"fainted", r"fainting", r"loss of consciousness", r"seizure", r"stroke symptoms",
    r"vomit(?:ing)? blood", r"blood in (?:my )?(?:vomit|stool)", r"black tarry stool",
    r"severe (?:abdominal|stomach|chest|head) pain", r"sudden severe pain", r"suicid(?:al|e)",
)


def urgent_care_warning(text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in URGENT_PATTERNS)


def disclaimer() -> str:
    return DISCLAIMER
