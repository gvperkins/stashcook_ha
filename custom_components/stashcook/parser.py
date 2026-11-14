"""Parse Diane's meal-plan calendar events into structured recipe data.

Pure Python (no Home Assistant imports) so it can be unit tested on its own.

Event titles:
    "Family Dinner - X"   -> slot "dinner"
    "Lunch - X"           -> slot "lunch"
    "Lunch Prep - X"      -> slot "lunch_prep"
    "Breakfast - X"       -> slot "breakfast"

Descriptions are plain text with simple <b> tags and newlines:
    <b>Quick - oven while Harrison's at swimming (5:30-6:30)</b>   <- headline
    - 4 garlic chicken Kievs                                         <- ingredient
    Roasties: peel and chop potatoes, ...                            <- method paragraph
    <b>Tonight:</b> make the Shepherd's Pie for tomorrow ...         <- labelled extra
"""
from __future__ import annotations

import html
import re
from typing import Any

SLOT_PREFIXES: list[tuple[str, str]] = [
    ("family dinner - ", "dinner"),
    ("dinner - ", "dinner"),
    ("lunch prep - ", "lunch_prep"),
    ("lunch - ", "lunch"),
    ("breakfast - ", "breakfast"),
]

BADGES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*quick\b", re.I), "Quick"),
    (re.compile(r"^\s*make[ -]ahead\b", re.I), "Make ahead"),
    (re.compile(r"\b(sunday )?roast\b", re.I), "Roast"),
    (re.compile(r"\bleftovers?\b", re.I), "Leftovers"),
]

_TAG_RE = re.compile(r"<[^>]+>")
_BOLD_LINE_RE = re.compile(r"^\s*<b>(.*?)</b>\s*(.*)$", re.I)
_LABEL_RE = re.compile(r"^(.{1,40}?):$")
_MINS_RE = re.compile(r"(?:about\s+)?(\d+)\s*(?:-\s*\d+\s*)?mins?\b", re.I)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9~(])")
_OFFICE_RE = re.compile(r"office", re.I)
_NIGHT_BEFORE_RE = re.compile(r"night before", re.I)


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def slot_for_title(summary: str) -> tuple[str, str] | None:
    """Return (slot, dish title) for a meal event title, or None."""
    low = (summary or "").strip().lower()
    for prefix, slot in SLOT_PREFIXES:
        if low.startswith(prefix):
            return slot, summary.strip()[len(prefix):].strip()
    return None


def badge_for(headline: str | None, title: str = "") -> str | None:
    for text in (headline or "", title or ""):
        for pattern, name in BADGES:
            if pattern.search(text):
                return name
    return None


def split_steps(paragraph: str) -> list[str]:
    """Split a method paragraph into steps on sentence boundaries.

    Very short sentences ("Fridge.", "Season.") are merged into the previous step.
    """
    steps: list[str] = []
    for sentence in _SENTENCE_RE.split(paragraph.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        if steps and len(sentence) < 22:
            steps[-1] = f"{steps[-1]} {sentence}"
        else:
            steps.append(sentence)
    return steps


def parse_description(description: str | None) -> dict[str, Any]:
    """Parse an event description into headline, ingredients, method and extras."""
    result: dict[str, Any] = {
        "headline": None,
        "intro": [],
        "ingredients": [],
        "method": [],
        "extras": [],
    }
    if not description:
        return result

    text = description.replace("\r\n", "\n").replace("<br>", "\n").replace("<br/>", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]

    section: str | None = None
    section_has_step = False
    seen_ingredient = False
    first_content = True

    for raw in lines:
        if not raw.strip():
            continue
        bold = _BOLD_LINE_RE.match(raw)
        if bold:
            inner, rest = _clean(bold.group(1)), _clean(bold.group(2))
            if first_content and not rest:
                result["headline"] = inner
                first_content = False
                continue
            first_content = False
            label = _LABEL_RE.match(inner)
            if label or rest:
                # "<b>Tonight:</b> make the pie" / "<b>Emma (home):</b> soup ..."
                result["extras"].append(
                    {"label": (label.group(1) if label else inner).strip(), "text": rest}
                )
                continue
            # Bold line on its own after the headline is a section header.
            section = inner
            section_has_step = False
            result["ingredients"].append({"text": inner, "header": True})
            continue

        first_content = False
        line = _clean(raw)
        if line.startswith(("- ", "• ", "* ")):
            result["ingredients"].append({"text": line[2:].strip(), "header": False})
            seen_ingredient = True
            continue

        if not seen_ingredient and not result["method"]:
            result["intro"].append(line)
            continue

        steps = split_steps(line)
        if section and not section_has_step and steps:
            steps[0] = f"{section}: {steps[0]}"
            section_has_step = True
        result["method"].extend(steps)

    return result


def minutes_from(headline: str | None) -> int | None:
    if not headline:
        return None
    match = _MINS_RE.search(headline)
    return int(match.group(1)) if match else None


def lunch_split(title: str, extras: list[dict[str, str]]) -> list[dict[str, Any]] | None:
    """Office-day lunches: "<b>Emma (home):</b> ..." and "<b>Geraint (office day):</b> ..."."""
    people = [
        e for e in extras
        if re.match(r"^[A-Z][a-z]+\s*\(", e["label"]) and not e["label"].lower().startswith("tonight")
    ]
    if len(people) < 2:
        return None
    titles = [t.strip() for t in title.split(" / ")]
    out = []
    for idx, extra in enumerate(people):
        who = extra["label"].split("(")[0].strip()
        out.append({
            "who": who,
            "office": bool(_OFFICE_RE.search(extra["label"])),
            "title": titles[idx] if idx < len(titles) else title,
            "text": extra["text"],
        })
    return out


def prep_lines_for(parsed: dict[str, Any], *, tomorrow: bool) -> list[str]:
    """Reminder lines for the prep banner.

    Today's events contribute their "Tonight:" lines. Tomorrow's events contribute
    anything that has to happen "the night before".
    """
    lines: list[str] = []
    for extra in parsed.get("extras", []):
        label, text = extra["label"], extra["text"]
        if not tomorrow and label.lower().startswith("tonight"):
            lines.append(_sentence_case(text))
        elif tomorrow and _NIGHT_BEFORE_RE.search(text):
            clause = text.split(" - ")[0].strip()
            who = label.split("(")[0].strip()
            note = " (office day)" if _OFFICE_RE.search(label) else ""
            lines.append(f"{who}: {clause}{note}")
    return lines


def _sentence_case(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text
