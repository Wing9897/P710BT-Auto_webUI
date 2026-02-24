"""Multi-format data parser — JSON / CSV / delimited / Excel → List[Dict]."""
import csv
import io
import json
from typing import Any


def parse_json(text: str) -> list[dict[str, str]]:
    data = json.loads(text)
    if isinstance(data, list):
        return [_stringify(row) for row in data]
    raise ValueError("JSON input must be an array of objects")


def detect_delimiter(text: str) -> str:
    """Guess delimiter from first line."""
    first_line = text.strip().split("\n")[0]
    for delim in ["\t", "|", ";", ","]:
        if delim in first_line:
            return delim
    return ","


def parse_csv(text: str, delimiter: str | None = None) -> list[dict[str, str]]:
    if delimiter is None:
        delimiter = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(row) for row in reader]


def parse_delimited(text: str, delimiter: str) -> list[dict[str, str]]:
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return []
    # Single line: each delimited value = one label row
    if len(lines) == 1:
        values = lines[0].split(delimiter)
        return [{"value": v.strip()} for v in values if v.strip()]
    # Multiple lines: first line = header, rest = data rows
    return parse_csv(text, delimiter=delimiter)


def parse_excel(file_bytes: bytes) -> list[dict[str, str]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        record = {}
        for i, val in enumerate(row):
            key = headers[i] if i < len(headers) else f"col_{i}"
            record[key] = str(val) if val is not None else ""
        result.append(record)
    wb.close()
    return result


def parse_auto(text: str | None = None, file_bytes: bytes | None = None,
               format: str = "auto", delimiter: str | None = None) -> list[dict[str, str]]:
    """
    Unified entry point.
    format: "json" | "csv" | "delimited" | "excel" | "auto"
    """
    if format == "excel" and file_bytes:
        return parse_excel(file_bytes)

    if text is None:
        raise ValueError("text is required for non-excel formats")

    if format == "json":
        return parse_json(text)
    elif format == "csv":
        return parse_csv(text, delimiter)
    elif format == "delimited":
        if delimiter is None:
            raise ValueError("delimiter required for delimited format")
        return parse_delimited(text, delimiter)
    elif format == "auto":
        text_stripped = text.strip()
        if text_stripped.startswith("["):
            try:
                return parse_json(text_stripped)
            except (json.JSONDecodeError, ValueError):
                pass
        return parse_csv(text_stripped, delimiter)
    else:
        raise ValueError(f"Unknown format: {format}")


def _stringify(obj: Any) -> dict[str, str]:
    if isinstance(obj, dict):
        return {str(k): str(v) for k, v in obj.items()}
    raise ValueError("Each item must be an object/dict")
