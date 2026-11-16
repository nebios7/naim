"""An answer that copies whole sentences of Naim's earlier answers in the same conversation, found before it is shown.

A small model asked to "do it again" or "continue" often writes a new first line, then pastes back the explanation,
the check and the closing question of its previous answer, word for word, turn after turn. The start of the answer
differs, so a check on the start misses it: here every sentence of the answer is compared with the earlier answers.

check(text, earlier) -> the copied sentences (empty when the answer says something new). Code blocks, formulas
on their own line and short lines are left out: a corrected drawing or a repeated formula is not a copy.
"""
import re

FENCE_RE = re.compile(r"```.*?(```|$)", re.S)
DISPLAY_MATH_RE = re.compile(r"\$\$.*?\$\$", re.S)
MIN_CHARS = 40          # a sentence shorter than this (a title, "Vérification :") is not counted
MIN_COPIED = 3          # at least this many copied sentences
MIN_SHARE = 0.4         # and at least this share of the answer's sentences


def _norm(s):
    s = re.sub(r"[*_`#>]", "", s)               # markdown marks
    s = re.sub(r"^\s*([-•]|\d+[.)])\s+", "", s)  # list bullets and numbers
    return " ".join(s.lower().split()).strip(" .:;!?")


def sentences(text):
    """The sentences of an answer worth comparing: prose only, one per line or per full stop."""
    text = FENCE_RE.sub("\n", str(text or ""))
    text = DISPLAY_MATH_RE.sub("\n", text)
    out = []
    for line in text.split("\n"):
        for part in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý])", line):
            n = _norm(part)
            if len(n) >= MIN_CHARS:
                out.append((part.strip(), n))
    return out


def check(text, earlier):
    """The sentences of `text` already written word for word in one of the `earlier` answers, when they make up a
    good part of it; else an empty list."""
    mine = sentences(text)
    if len(mine) < MIN_COPIED:
        return []
    before = set()
    for e in earlier or []:
        before.update(n for _, n in sentences(e))
    copied = [raw for raw, n in mine if n in before]
    if len(copied) >= MIN_COPIED and len(copied) / len(mine) >= MIN_SHARE:
        return copied
    return []
