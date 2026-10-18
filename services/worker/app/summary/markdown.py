"""Render a stored summary as markdown. Built from the validated JSON, never from the model directly.

Anything the leak check accepted is safe to show here, because this only rearranges that JSON.
"""

from __future__ import annotations

import re
from typing import Any

_LABELS = {
    "experienceSummary": "Experience",
    "yearsExperience": "Years of experience",
    "startDate": "Start date",
    "visitSummary": "Visit",
    "whatToShare": "Safe to share",
    "importantDates": "Important dates",
    "riskyClauses": "Risky clauses",
    "dataCollected": "Data collected",
    "dataSharing": "Data sharing",
    "autoRenewal": "Auto-renewal",
    "dataUse": "Data use",
    "quoteSnippet": "Quote",
}


def _label(key: str) -> str:
    if key in _LABELS:
        return _LABELS[key]
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
    return spaced[:1].upper() + spaced[1:]


def _cite(citations: list[dict[str, Any]]) -> str:
    pages = sorted({int(item["page"]) for item in citations if item.get("page")})
    if not pages:
        return ""
    shown = ", ".join(f"p. {page}" for page in pages)
    return f" ({shown})"


def _render_value(value: Any, lines: list[str]) -> None:
    if value is None or value == "" or value == []:
        lines.append("- None found.")
        return
    if isinstance(value, str):
        lines.append(value)
        return
    if isinstance(value, (int, float)):
        lines.append(str(value))
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                lines.append(f"- {item}")
            elif isinstance(item, dict) and "text" in item:
                lines.append(f"- {item.get('text') or '—'}{_cite(item.get('citations') or [])}")
            elif isinstance(item, dict) and "page" in item:
                quote = item.get("quoteSnippet") or ""
                lines.append(f"- p. {item['page']}" + (f": {quote}" if quote else ""))
            else:
                lines.append(f"- {item}")
        return
    lines.append(str(value))


def render_markdown(mode_label: str, summary: dict[str, Any], *, safe_mode: bool, truncated: bool) -> str:
    lines = [f"# {mode_label}", ""]
    lines.append("Generated from redacted text." if safe_mode else "Generated from the full document text.")
    if truncated:
        lines.append("The document was longer than the page limit, so later pages were not included.")
    lines.append("")
    for key, value in summary.items():
        if key == "confidence":
            continue
        lines.append(f"## {_label(key)}")
        lines.append("")
        _render_value(value, lines)
        lines.append("")
    confidence = summary.get("confidence")
    if isinstance(confidence, (int, float)):
        lines.append(f"Confidence: {round(float(confidence) * 100)}%.")
    return "\n".join(lines).strip() + "\n"
