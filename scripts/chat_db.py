"""SQLite chat history for SuperBot (stdlib only)."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "chat_history.db"

_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id);
        CREATE INDEX IF NOT EXISTS idx_conversations_updated
            ON conversations(updated_at DESC);
        """
    )
    conn.commit()


class ChatStore:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self.open()

    def close(self) -> None:
        with _lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None

    def open(self) -> None:
        with _lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None
            try:
                conn = _connect(self.db_path)
                conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
                _init_schema(conn)
                # Verify writable schema round-trip
                conn.execute("SELECT id FROM conversations LIMIT 1")
                self._conn = conn
            except sqlite3.Error:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = None
                if self.db_path.exists():
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup = self.db_path.with_name(f"chat_history.corrupt_{stamp}.db")
                    import shutil
                    import time

                    last_err: Exception | None = None
                    for _ in range(8):
                        try:
                            # Prefer rename; fall back to copy+delete
                            try:
                                self.db_path.replace(backup)
                            except OSError:
                                shutil.copy2(self.db_path, backup)
                                self.db_path.unlink()
                            last_err = None
                            break
                        except OSError as err:
                            last_err = err
                            time.sleep(0.05)
                    if last_err is not None and self.db_path.exists():
                        # Last resort: recreate beside the locked file
                        self.db_path = self.db_path.with_name(
                            f"chat_history_recovered_{stamp}.db"
                        )
                conn = _connect(self.db_path)
                _init_schema(conn)
                self._conn = conn

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.open()
        assert self._conn is not None
        return self._conn

    def create_conversation(self, title: str = "New chat") -> dict[str, Any]:
        now = _utc_now()
        title = (title or "New chat").strip() or "New chat"
        with _lock:
            cur = self.conn.execute(
                "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
                (title, now, now),
            )
            self.conn.commit()
            cid = int(cur.lastrowid)
        return self.get_conversation(cid)

    def list_conversations(self, q: str = "") -> list[dict[str, Any]]:
        q = (q or "").strip()
        with _lock:
            if q:
                like = f"%{q}%"
                rows = self.conn.execute(
                    """
                    SELECT DISTINCT c.id, c.title, c.created_at, c.updated_at
                    FROM conversations c
                    LEFT JOIN messages m ON m.conversation_id = c.id
                    WHERE c.title LIKE ? OR m.content LIKE ?
                    ORDER BY c.updated_at DESC, c.id DESC
                    """,
                    (like, like),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    """
                    SELECT id, title, created_at, updated_at
                    FROM conversations
                    ORDER BY updated_at DESC, id DESC
                    """
                ).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(self, conversation_id: int) -> dict[str, Any]:
        with _lock:
            row = self.conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"conversation {conversation_id} not found")
            msgs = self.conn.execute(
                """
                SELECT id, role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        data = dict(row)
        data["messages"] = [dict(m) for m in msgs]
        return data

    def rename_conversation(self, conversation_id: int, title: str) -> dict[str, Any]:
        title = (title or "").strip()
        if not title:
            raise ValueError("title required")
        now = _utc_now()
        with _lock:
            cur = self.conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id),
            )
            if cur.rowcount == 0:
                raise KeyError(f"conversation {conversation_id} not found")
            self.conn.commit()
        return self.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: int) -> None:
        with _lock:
            cur = self.conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,),
            )
            if cur.rowcount == 0:
                raise KeyError(f"conversation {conversation_id} not found")
            self.conn.commit()

    def add_message(self, conversation_id: int, role: str, content: str) -> dict[str, Any]:
        if role not in ("user", "assistant", "system"):
            raise ValueError("invalid role")
        content = content if content is not None else ""
        now = _utc_now()
        with _lock:
            exists = self.conn.execute(
                "SELECT id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(f"conversation {conversation_id} not found")
            cur = self.conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, role, content, now),
            )
            self.conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            # Auto-title from first user message if still default
            if role == "user":
                conv = self.conn.execute(
                    "SELECT title FROM conversations WHERE id = ?",
                    (conversation_id,),
                ).fetchone()
                if conv and conv["title"] in ("New chat", "New Chat", ""):
                    auto = " ".join(content.strip().split())[:60] or "New chat"
                    self.conn.execute(
                        "UPDATE conversations SET title = ? WHERE id = ?",
                        (auto, conversation_id),
                    )
            self.conn.commit()
            mid = int(cur.lastrowid)
            row = self.conn.execute(
                "SELECT id, conversation_id, role, content, created_at FROM messages WHERE id = ?",
                (mid,),
            ).fetchone()
        return dict(row)


_store: Optional[ChatStore] = None


def get_store() -> ChatStore:
    global _store
    if _store is None:
        _store = ChatStore()
    return _store
