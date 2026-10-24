"""Shared integrity helpers for the evidence lints and the harness: hashing, tolerant JSON
load, finite-number test, and the record-header check common to every append-only record."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

RECORD_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{7,40}$")
FIELD_RE = re.compile(r"^- \*\*(?P<k>[^*]+)\*\*:\s*(?P<v>.*)$")
NO_SUPERSESSION_RE = re.compile(r"^\(?\s*(none|n/?a)\b", re.IGNORECASE)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_json(path: Path, problems: list[str], what: str):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        problems.append(f"{what}: unreadable JSON {path.name} ({exc})")
        return None


def parse_fields(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = FIELD_RE.match(line)
        if m:
            out[m.group("k").strip()] = m.group("v").strip()
    return out


def check_record_header(rec: Path, records_dir: Path, required_fields: tuple[str, ...]):
    """Validate a record's id, required fields, Record ID == filename, Status and Supersedes.

    Returns `(fields, problems)`; `fields` is None when the filename is not a record id
    (nothing further can be checked)."""
    rid = rec.stem
    if not RECORD_ID_RE.match(rid):
        return None, [f"{rec.name}: not a <YYYYMMDD>-<HHMMSS>-<sha> record id"]
    problems: list[str] = []
    fields = parse_fields(rec.read_text())
    for f in required_fields:
        if not fields.get(f):
            problems.append(f"{rid}: required field {f!r} missing or empty")
    if fields.get("Record ID") != rid:
        problems.append(f"{rid}: Record ID field {fields.get('Record ID')!r} != filename")
    if fields.get("Status") not in ("PASS", "FAIL"):
        problems.append(f"{rid}: Status must be PASS or FAIL")
    sup = fields.get("Supersedes", "")
    if sup and not NO_SUPERSESSION_RE.match(sup):
        ref = re.search(r"\d{8}-\d{6}-[0-9a-f]{7,40}", sup)
        if not ref or not (records_dir / f"{ref.group(0)}.md").is_file():
            problems.append(f"{rid}: Supersedes names a record that does not exist")
    return fields, problems
