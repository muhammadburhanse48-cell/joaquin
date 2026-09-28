"""Markdown tables and CSV for the brand files the orchestrator itself writes and reads back.

Seat output is not parsed here: structured tasks come back as schema-constrained JSON
(agents/schemas.py, SeatResult.data).
"""

from __future__ import annotations

import csv
import io
import re


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_tables(text: str) -> list[list[dict]]:
    """All markdown tables in `text`; each a list of {header: cell} rows."""
    tables, lines, i = [], text.splitlines(), 0
    while i < len(lines) - 1:
        head, sep = lines[i], lines[i + 1]
        if "|" in head and re.fullmatch(r"\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*", sep):
            header = _cells(head)
            rows, i = [], i + 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = _cells(lines[i])
                if len(cells) == len(header):
                    rows.append(dict(zip(header, cells)))
                i += 1
            tables.append(rows)
        else:
            i += 1
    return tables


def col(row: dict, prefix: str, default: str = "") -> str:
    """Cell whose header starts with `prefix` (case-insensitive)."""
    for key, value in row.items():
        if key.lower().lstrip("# ").startswith(prefix.lower()):
            return value
    return default


def render_table(rows: list[dict], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(c, "")).replace("\n", " ") for c in columns) + " |")
    return "\n".join(out)


def rows_to_csv(rows: list[dict], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: str(row.get(c, "")).replace("<br>", "\n") for c in columns})
    return buf.getvalue()


_QUOTE = re.compile(r'["“]([^"”\n]{12,300})["”]')


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def unverified_quotes(output: str, source: str) -> tuple[list[str], int]:
    """Quoted strings in `output` that do not appear verbatim in `source` (Law 1)."""
    haystack = _norm(source)
    quotes = list(dict.fromkeys(_QUOTE.findall(output)))
    bad = [q for q in quotes if _norm(q) not in haystack]
    return bad, len(quotes)
