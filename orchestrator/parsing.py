"""Turn seat output (markdown, CSV-ish tables, fenced JSON) into data, and back."""

from __future__ import annotations

import csv
import io
import json
import re

from .errors import StageError

_FENCE = re.compile(r"```json\s*(.*?)```", re.S | re.I)


def extract_json(text: str):
    """Return (parsed JSON from the LAST ```json block, the prose before it)."""
    blocks = list(_FENCE.finditer(text))
    if not blocks:
        raise StageError("seat output has no machine-readable ```json block")
    last = blocks[-1]
    try:
        data = json.loads(last.group(1))
    except json.JSONDecodeError as exc:
        raise StageError(f"machine-readable block is not valid JSON: {exc}") from exc
    return data, text[: last.start()].rstrip()


def json_objects(text: str) -> list[dict]:
    """Every top-level {...} JSON object embedded in free text (manifest entries)."""
    decoder, out, i = json.JSONDecoder(), [], 0
    while (i := text.find("{", i)) != -1:
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        i = end
    return out


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


def split_named_files(text: str, names: list[str]) -> dict[str, str]:
    """Split "file A followed by file B" output on lines that name each file."""
    marks = []
    for name in names:
        stem = re.escape(name.removesuffix(".md"))
        m = re.search(rf"^[#>*` \t-]*{stem}(?:\.md)?[`*: \t]*$", text, re.M | re.I)
        if not m:
            raise StageError(f"could not find {name!r} in the seat output")
        marks.append((m.start(), m.end(), name))
    marks.sort()
    out = {}
    for i, (_, end, name) in enumerate(marks):
        stop = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        out[name] = text[end:stop].strip()
    return out


_QUOTE = re.compile(r'["“]([^"”\n]{12,300})["”]')


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def unverified_quotes(output: str, source: str) -> tuple[list[str], int]:
    """Quoted strings in `output` that do not appear verbatim in `source` (Law 1)."""
    haystack = _norm(source)
    quotes = list(dict.fromkeys(_QUOTE.findall(output)))
    bad = [q for q in quotes if _norm(q) not in haystack]
    return bad, len(quotes)


def section(text: str, heading_prefix: str) -> str:
    """Body of the '## <heading_prefix>…' section, up to the next same-level heading."""
    m = re.search(rf"^##\s+{re.escape(heading_prefix)}[^\n]*\n", text, re.M | re.I)
    if not m:
        return ""
    nxt = re.search(r"^##\s+", text[m.end():], re.M)
    return text[m.end(): m.end() + nxt.start() if nxt else len(text)].strip()
