"""CSV parsing that keeps character offsets, so every value extracted from a
spreadsheet can point back to the exact characters it came from."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cell:
    value: str
    start: int  # span of the value inside the file text (inside quotes when quoted)
    end: int


@dataclass
class Row:
    index: int  # 0 = header
    start: int
    end: int  # excludes the line break
    cells: list[Cell] = field(default_factory=list)


def parse(text: str) -> list[Row]:
    rows: list[Row] = []
    i, n = 0, len(text)
    while i < n:
        row = Row(index=len(rows), start=i, end=i)
        while True:
            if i < n and text[i] == '"':
                i += 1
                start = i
                buf = []
                while i < n:
                    if text[i] == '"' and i + 1 < n and text[i + 1] == '"':
                        buf.append('"')
                        i += 2
                    elif text[i] == '"':
                        break
                    else:
                        buf.append(text[i])
                        i += 1
                end = i
                i += 1  # closing quote
                row.cells.append(Cell("".join(buf), start, end))
            else:
                start = i
                while i < n and text[i] not in ',\r\n':
                    i += 1
                row.cells.append(Cell(text[start:i], start, i))
            if i < n and text[i] == ',':
                i += 1
                continue
            break
        row.end = i
        if i < n and text[i] == '\r':
            i += 1
        if i < n and text[i] == '\n':
            i += 1
        if any(c.value for c in row.cells):
            rows.append(row)
    return rows


def as_dicts(rows: list[Row]) -> tuple[list[str], list[tuple[Row, dict[str, Cell]]]]:
    if not rows:
        return [], []
    header = [c.value.strip().lower() for c in rows[0].cells]
    out = []
    for r in rows[1:]:
        cells = {h: r.cells[k] for k, h in enumerate(header) if k < len(r.cells)}
        out.append((r, cells))
    return header, out
