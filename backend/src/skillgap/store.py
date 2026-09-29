from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from skillgap.models import CandidateResult


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS candidates ("
                "id TEXT PRIMARY KEY, sha256 TEXT, status TEXT NOT NULL, "
                "created_at REAL NOT NULL, json TEXT NOT NULL)")
            self._db.commit()

    def save(self, result: CandidateResult, sha256: str | None = None) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO candidates (id, sha256, status, created_at, json) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status = excluded.status, json = excluded.json",
                (result.id, sha256, result.status, time.time(), result.model_dump_json()))
            self._db.commit()

    def get(self, id: str) -> CandidateResult | None:
        with self._lock:
            row = self._db.execute("SELECT json FROM candidates WHERE id = ?", (id,)).fetchone()
        return CandidateResult.model_validate_json(row[0]) if row else None

    def list(self) -> list[CandidateResult]:
        with self._lock:
            rows = self._db.execute(
                "SELECT json FROM candidates ORDER BY created_at DESC, rowid DESC").fetchall()
        return [CandidateResult.model_validate_json(r[0]) for r in rows]

    def find_reusable_by_hash(self, sha256: str) -> CandidateResult | None:
        with self._lock:
            row = self._db.execute(
                "SELECT json FROM candidates WHERE sha256 = ? AND status IN ('processing', 'done') "
                "ORDER BY created_at DESC LIMIT 1", (sha256,)).fetchone()
        return CandidateResult.model_validate_json(row[0]) if row else None

    def fail_stale_processing(self, message: str) -> int:
        """Marca como erro todo registro ainda em 'processing' (mantém created_at)."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, json FROM candidates WHERE status = 'processing'").fetchall()
            for id_, payload in rows:
                failed = CandidateResult.model_validate_json(payload).model_copy(update={
                    "status": "error", "stage": "error",
                    "error": "INTERNAL", "error_message": message})
                self._db.execute(
                    "UPDATE candidates SET status = 'error', json = ? WHERE id = ?",
                    (failed.model_dump_json(), id_))
            self._db.commit()
        return len(rows)

    def close(self) -> None:
        with self._lock:
            self._db.close()
