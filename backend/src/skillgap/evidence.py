"""Deterministic check that an evidence quote really appears in the CV text (no LLM).

Known limits (by design, for the UI owner):
* Fragments shorter than 8 characters are ignored; if none is left the result is False.
* A literal "..." inside a genuine quote is treated as an ellipsis (the quote is split there).
* Zero-width characters are removed, not replaced by a space.
* A fragment must match on word boundaries: "team of 5" does not match "team of 50".
"""
import re
import unicodedata

MIN_FRAGMENT = 8

_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"), None)
_TYPOGRAPHY = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2018": "'", "\u2019": "'", "\u201a": "'",
    "\u2013": "-", "\u2014": "-", "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2212": "-",
})
_SPACES = re.compile(r"\s+")


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.translate(_INVISIBLE).translate(_TYPOGRAPHY)
    return _SPACES.sub(" ", value).strip()


def _is_word(char: str) -> bool:
    return char.isalnum() or char == "_"


def _find_bounded(haystack: str, fragment: str, start: int) -> int:
    """Index of the first occurrence at/after `start` not glued to a word character, or -1."""
    first_is_word, last_is_word = _is_word(fragment[0]), _is_word(fragment[-1])
    pos = haystack.find(fragment, start)
    while pos >= 0:
        end = pos + len(fragment)
        if not (first_is_word and pos > 0 and _is_word(haystack[pos - 1])) and not (
                last_is_word and end < len(haystack) and _is_word(haystack[end])):
            return pos
        pos = haystack.find(fragment, pos + 1)
    return -1


def verify_evidence(evidence: str, text: str) -> bool:
    """True when every fragment (split on ellipses) of `evidence` occurs, in order, in `text`."""
    haystack = _normalize(text)
    # NFKC turns the ellipsis character into "...", so one split covers both forms
    fragments = [f.strip() for f in _normalize(evidence).split("...")]
    fragments = [f for f in fragments if len(f) >= MIN_FRAGMENT]
    if not fragments or not haystack:
        return False
    position = 0
    for fragment in fragments:
        found = _find_bounded(haystack, fragment, position)
        if found < 0:
            return False
        position = found + len(fragment)
    return True
