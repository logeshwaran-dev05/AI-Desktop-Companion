"""
TaskRepository – lightweight SQLite persistence for FastAPI tasks.
Uses the built‑in sqlite3 module (no external dependencies).
Provides simple CRUD operations matching the in‑memory dict API used by the
orchestrator.
"""
import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Database file located at repo root
DB_PATH = Path(__file__).resolve().parent.parent / "backend.db"

# Ensure the database and table exist
def _init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

_init_db()

class TaskRepository:
    """Simple repository storing task dictionaries as JSON blobs.

    The orchestrator works with a mutable dict per task. We store the whole
    dict serialized as JSON. ``updated_at`` is refreshed on every write.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        # Ensure DB exists (handled by module import)

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def create_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        now = task_data.get("created_at", "")
        payload = json.dumps(task_data)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tasks (task_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (task_id, payload, now, now),
        )
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT data FROM tasks WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None

    def update_task(self, task_id: str, task_data: Dict[str, Any]) -> None:
        now = task_data.get("updated_at", "")
        payload = json.dumps(task_data)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            "UPDATE tasks SET data = ?, updated_at = ? WHERE task_id = ?",
            (payload, now, task_id),
        )
        conn.commit()
        conn.close()

    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT data FROM tasks")
        rows = cur.fetchall()
        conn.close()
        tasks = [json.loads(r[0]) for r in rows]
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def delete_task(self, task_id: str) -> None:
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        conn.close()
