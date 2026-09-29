import csv
import io

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from skillgap.models import CandidateResult

HEADER = ["tipo", "nome", "trilha", "nivel_atual", "nivel_esperado",
          "severidade", "horas", "link", "evidencia"]

_FORMULA_PREFIXES = ("=", "+", "-", "@")
_WHITESPACE_TO_STRIP = " \t\r\n﻿\xa0​"  # space, tab, CR, LF, ZWNBSP, NBSP, ZWSP


def _safe(value):
    if not isinstance(value, str):
        return value

    # Step 1: Remove illegal control characters that openpyxl rejects
    cleaned = ILLEGAL_CHARACTERS_RE.sub("", value)

    # Step 2: Check for formula injection by looking at first meaningful character
    # Strip leading whitespace/invisible chars to find the first significant char
    stripped_for_check = cleaned.lstrip(_WHITESPACE_TO_STRIP)

    # Step 3: Prefix with ' if starts with formula prefix or if original starts with \t or \r
    if stripped_for_check and stripped_for_check[0] in _FORMULA_PREFIXES:
        return "'" + cleaned  # Prefix the ORIGINAL cleaned value, not the stripped one
    if cleaned.startswith(("\t", "\r")):
        return "'" + cleaned

    return cleaned


def _skill_rows(result: CandidateResult):
    for s in result.skills:
        yield ["skill", s.name, s.track, s.level, "", "", "", "", s.evidence]
    for o in result.other_skills:
        yield ["outra_skill", o.name, "", o.level, "", "", "", "", o.evidence]


def _gap_rows(result: CandidateResult):
    for g in result.gaps:
        yield ["gap", g.name, g.track, g.current, g.expected, g.severity, "", "", ""]


def _course_rows(result: CandidateResult):
    for r in result.recommendations:
        yield ["treinamento", r.title, "", "", "", "", r.hours, r.link, ""]


def to_csv(result: CandidateResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for rows in (_skill_rows(result), _gap_rows(result), _course_rows(result)):
        for row in rows:
            writer.writerow([_safe(v) for v in row])
    return buffer.getvalue()


def to_xlsx(result: CandidateResult) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in (
        ("Skills", _skill_rows(result)),
        ("Gaps", _gap_rows(result)),
        ("Treinamentos", _course_rows(result)),
    ):
        sheet = workbook.create_sheet(title)
        sheet.append(HEADER)
        for row in rows:
            sheet.append([_safe(v) for v in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
