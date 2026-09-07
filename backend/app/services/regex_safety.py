"""Guardrails against catastrophic backtracking in user-supplied regex patterns.

Two layers of defense:

1. ``validate_safe_regex`` — static structural analysis that rejects the known
   catastrophic-backtracking shapes *before* the pattern is ever run:
     * nested quantifiers — a quantified group whose body also contains an
       unbounded quantifier, e.g. ``(a+)+`` / ``(a*)*`` / ``(a+)*``;
     * quantified alternation with overlapping branches, e.g. ``(a|a)*`` /
       ``(a|ab)*`` / ``(.|a)*`` / ``(a|)*`` — the class the old nested-only
       guard missed (audit P2-12);
     * stacked quantifiers such as ``a**`` / ``a+*``.

2. ``safe_search`` — a runtime wall-clock timeout around the actual match, so
   any pattern that slips past the static analysis still cannot hang the
   process on a hostile input. Input is length-capped first.
"""

from __future__ import annotations

import re
import threading
from typing import Optional

MAX_REGEX_LENGTH = 200
# Cap the haystack a guardrail pattern runs against — bounds worst-case
# backtracking work even for a pattern that passes static analysis.
MAX_MATCH_INPUT_CHARS = 100_000
# Best-effort wall-clock budget for a single match.
REGEX_MATCH_TIMEOUT_SECONDS = 1.0

_UNBOUNDED_QUANTIFIER = ("*", "+")


class UnsafeRegexError(ValueError):
    """Raised when a pattern is structurally prone to catastrophic backtracking."""


def _split_top_level_alternation(body: str) -> list[str]:
    """Split ``body`` on ``|`` that sit at the group's top level (depth 0)."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            current.append(body[i : i + 2])
            i += 2
            continue
        if ch == "[":
            # Consume a character class verbatim (| inside it is a literal).
            j = i + 1
            if j < len(body) and body[j] == "^":
                j += 1
            if j < len(body) and body[j] == "]":
                j += 1
            while j < len(body) and body[j] != "]":
                if body[j] == "\\":
                    j += 1
                j += 1
            current.append(body[i : j + 1])
            i = j + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current))
    return parts


# Analysis of an alternation branch's guaranteed leading tokens.
_QUANTIFIER_CHARS = "*+?{"


def _branch_profile(alt: str) -> tuple[str, bool, bool]:
    """Summarise an alternation branch for overlap analysis.

    Returns ``(literal_prefix, is_epsilon, starts_wildcard)``:
      * ``literal_prefix`` — the run of *guaranteed* leading literal characters
        (a literal followed by ``?``/``*`` is not guaranteed, so it is dropped);
      * ``is_epsilon`` — the branch can match the empty string;
      * ``starts_wildcard`` — the branch begins with ``.``/class/group/metaclass,
        so it can overlap essentially any other branch.
    """
    s = alt.strip()
    i = 0
    n = len(s)
    literal: list[str] = []
    # Skip a leading zero-width anchor.
    while i < n and (s[i] in "^$" or (s[i] == "\\" and i + 1 < n and s[i + 1] in "bBAZ")):
        i += 2 if s[i] == "\\" else 1
    if i >= n:
        return "", True, False
    while i < n:
        ch = s[i]
        if ch in ".[(":
            # Wildcard / class / group start.
            return "".join(literal), False, not literal
        if ch == "\\":
            if i + 1 < n and s[i + 1].isalpha():
                # Metaclass like \d, \w — wildcard-ish start.
                return "".join(literal), False, not literal
            # Escaped literal.
            lit = s[i + 1] if i + 1 < n else "\\"
            nxt = s[i + 2] if i + 2 < n else ""
            if nxt and nxt in _QUANTIFIER_CHARS:
                break
            literal.append(lit)
            i += 2
            continue
        if ch in _QUANTIFIER_CHARS:
            break
        nxt = s[i + 1] if i + 1 < n else ""
        if nxt in ("?", "*"):
            # This literal is optional/repeatable — not guaranteed; stop before it.
            break
        literal.append(ch)
        i += 1
    return "".join(literal), False, False


def _alternation_branches_overlap(branches: list[str]) -> bool:
    profiles = [_branch_profile(b) for b in branches]
    wildcard_branches = 0
    prefixes: list[str] = []
    for literal, is_epsilon, starts_wildcard in profiles:
        if is_epsilon:
            # An epsilon branch under a quantifier is always dangerous.
            return True
        if starts_wildcard:
            wildcard_branches += 1
        prefixes.append(literal)
    # A wildcard-starting branch can overlap any sibling branch.
    if wildcard_branches and len(branches) > 1:
        return True
    # Two literal branches where one is a prefix of the other (incl. equal) are
    # ambiguous under a quantifier → catastrophic, e.g. (a|ab)* or (a|a)*.
    for idx, a in enumerate(prefixes):
        for b in prefixes[idx + 1 :]:
            if not a or not b:
                continue
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if longer.startswith(shorter):
                return True
    return False


def _body_has_unbounded_quantifier(body: str) -> bool:
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\\":
            i += 2
            continue
        if ch in _UNBOUNDED_QUANTIFIER:
            return True
        if ch == "{":
            close = body.find("}", i)
            if close != -1 and "," in body[i:close] and body[i + 1 : close].endswith(","):
                # {n,} — unbounded upper limit.
                return True
        i += 1
    return False


def _iter_quantified_groups(pattern: str):
    """Yield the inner body of every group immediately followed by an unbounded
    quantifier (``*``, ``+``, or ``{n,}``)."""
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "(":
            depth = 1
            j = i + 1
            while j < n and depth:
                cj = pattern[j]
                if cj == "\\":
                    j += 2
                    continue
                if cj == "(":
                    depth += 1
                elif cj == ")":
                    depth -= 1
                j += 1
            # pattern[i+1 : j-1] is the group body; pattern[j:] is what follows.
            body = pattern[i + 1 : j - 1]
            follow = pattern[j] if j < n else ""
            quantified = follow in _UNBOUNDED_QUANTIFIER
            if follow == "{":
                close = pattern.find("}", j)
                if close != -1 and pattern[j + 1 : close].rstrip().endswith(","):
                    quantified = True
            yield body, quantified
            i = j
            continue
        i += 1


def _has_catastrophic_structure(pattern: str) -> bool:
    # Stacked quantifiers: a*, a+ immediately followed by another quantifier.
    if re.search(r"[*+?}][*+]", pattern):
        return True
    for body, quantified in _iter_quantified_groups(pattern):
        if not quantified:
            continue
        # Nested quantifier: (…+…)+ / (…*…)*
        if _body_has_unbounded_quantifier(body):
            return True
        # Quantified alternation with overlapping / epsilon branches: (a|a)*
        branches = _split_top_level_alternation(body)
        if len(branches) > 1 and _alternation_branches_overlap(branches):
            return True
    return False


def validate_safe_regex(pattern: str) -> None:
    stripped = (pattern or "").strip()
    if not stripped:
        raise ValueError("Regex pattern is empty")
    if len(stripped) > MAX_REGEX_LENGTH:
        raise ValueError(f"Regex pattern exceeds {MAX_REGEX_LENGTH} characters")
    if _has_catastrophic_structure(stripped):
        raise UnsafeRegexError(
            "Regex pattern is prone to catastrophic backtracking "
            "(nested or overlapping quantifiers are not allowed)"
        )
    re.compile(stripped)


def safe_search(pattern: str, text: str) -> Optional[re.Match]:
    """Run ``re.search`` under a length cap and a wall-clock timeout.

    Assumes ``validate_safe_regex(pattern)`` already passed. The timeout is a
    defense-in-depth backstop for any shape static analysis fails to reject; on
    a bounded-length haystack the match terminates, so the watchdog thread does
    not leak in practice.
    """
    haystack = text if len(text) <= MAX_MATCH_INPUT_CHARS else text[:MAX_MATCH_INPUT_CHARS]
    result: list[Optional[re.Match]] = [None]
    error: list[BaseException] = []

    def _run() -> None:
        try:
            result[0] = re.search(pattern, haystack)
        except BaseException as exc:  # noqa: BLE001 — surfaced to the caller below
            error.append(exc)

    worker = threading.Thread(target=_run, daemon=True)
    worker.start()
    worker.join(REGEX_MATCH_TIMEOUT_SECONDS)
    if worker.is_alive():
        raise UnsafeRegexError(
            "Regex match exceeded the time budget (possible catastrophic backtracking)"
        )
    if error:
        raise error[0]
    return result[0]
