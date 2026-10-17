"""Local SQLite history of analyzed applications.

Failures here must never break the main workflow, so callers use the *_safe
wrappers. The same job text always maps to one row (by content hash), which
prevents duplicate entries and lets later steps find the application again
without any extra form state.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import DATA_DIR
from app.models.schemas import JobAnalysis, MatchAnalysis

LOGGER = logging.getLogger(__name__)
DB_PATH = DATA_DIR / "tracker.db"
STATUSES = ("Draft", "Applied", "Interview", "Offer", "Rejected", "Withdrawn")

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    position TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Draft',
    score INTEGER NOT NULL DEFAULT 0,
    job_text TEXT NOT NULL,
    job_json TEXT NOT NULL,
    match_json TEXT NOT NULL,
    selected_json TEXT NOT NULL DEFAULT '[]',
    cover_letter TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    documents_json TEXT NOT NULL DEFAULT '[]'
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def job_hash(job_text: str) -> str:
    normalized = " ".join(job_text.split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def save_analysis(job_text: str, job: JobAnalysis, match: MatchAnalysis, selected: list[str] | None = None) -> int:
    """Insert a new application, or refresh the analysis of an existing one."""
    digest, now = job_hash(job_text), _now()
    with _connect() as db:
        row = db.execute("SELECT id FROM applications WHERE job_hash = ?", (digest,)).fetchone()
        values = (
            job.company, job.position, match.score, job_text, job.model_dump_json(), match.model_dump_json(),
            json.dumps(selected or [], ensure_ascii=False), now,
        )
        if row:
            db.execute(
                "UPDATE applications SET company=?, position=?, score=?, job_text=?, job_json=?, match_json=?, "
                "selected_json=?, updated_at=? WHERE id=?",
                (*values, row["id"]),
            )
            return int(row["id"])
        cursor = db.execute(
            "INSERT INTO applications (job_hash, created_at, company, position, score, job_text, job_json, "
            "match_json, selected_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (digest, now, *values),
        )
        return int(cursor.lastrowid)


def update_for_job(job_text: str, **fields: str) -> None:
    """Update letter text or selections on the application matching this job text."""
    allowed = {"cover_letter": "cover_letter", "selected_json": "selected_json"}
    sets = [(allowed[key], value) for key, value in fields.items() if key in allowed]
    if not sets:
        return
    with _connect() as db:
        db.execute(
            f"UPDATE applications SET {', '.join(f'{col}=?' for col, _ in sets)}, updated_at=? WHERE job_hash=?",
            (*[value for _, value in sets], _now(), job_hash(job_text)),
        )


def record_document(job_text: str, label: str) -> None:
    with _connect() as db:
        row = db.execute("SELECT documents_json FROM applications WHERE job_hash=?", (job_hash(job_text),)).fetchone()
        if not row:
            return
        documents = json.loads(row["documents_json"])
        documents.append({"label": label, "at": _now()})
        db.execute(
            "UPDATE applications SET documents_json=?, updated_at=? WHERE job_hash=?",
            (json.dumps(documents[-50:]), _now(), job_hash(job_text)),
        )


def set_status(application_id: int, status: str) -> bool:
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")
    with _connect() as db:
        return db.execute(
            "UPDATE applications SET status=?, updated_at=? WHERE id=?", (status, _now(), application_id)
        ).rowcount > 0


def set_notes(application_id: int, notes: str) -> bool:
    with _connect() as db:
        return db.execute(
            "UPDATE applications SET notes=?, updated_at=? WHERE id=?", (notes[:5000], _now(), application_id)
        ).rowcount > 0


def list_applications(status: str = "", query: str = "") -> list[dict]:
    clauses, params = [], []
    if status in STATUSES:
        clauses.append("status = ?")
        params.append(status)
    if query.strip():
        clauses.append("(company LIKE ? OR position LIKE ?)")
        params.extend([f"%{query.strip()}%"] * 2)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as db:
        rows = db.execute(
            "SELECT id, created_at, updated_at, company, position, status, score, notes, "
            "(cover_letter != '') AS has_letter, documents_json "
            f"FROM applications {where} ORDER BY updated_at DESC",
            params,
        ).fetchall()
    return [dict(row) | {"documents": json.loads(row["documents_json"])} for row in rows]


def get_application(application_id: int) -> dict | None:
    with _connect() as db:
        row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["selected"] = json.loads(data["selected_json"])
    data["documents"] = json.loads(data["documents_json"])
    return data


def delete_application(application_id: int) -> bool:
    with _connect() as db:
        return db.execute("DELETE FROM applications WHERE id=?", (application_id,)).rowcount > 0


def safe(function, *args, **kwargs):
    """Run a tracker operation without ever raising into the main workflow."""
    try:
        return function(*args, **kwargs)
    except Exception:
        LOGGER.warning("Application tracker operation failed", exc_info=True)
        return None
