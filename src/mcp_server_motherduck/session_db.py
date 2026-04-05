"""
Session-aware database manager.

Each MCP session (chat) gets its own in-memory DuckDB database.
Tables created by one session are not visible to others.
"""

import logging
import os
import threading
import time
from typing import Any

import duckdb

logger = logging.getLogger("mcp_server_motherduck.session_db")

SESSION_TTL = int(os.environ.get("MCP_SESSION_TTL", "3600"))


class SessionDatabaseManager:
    """Manages per-session DuckDB connections."""

    def __init__(self, max_rows: int = 1024, max_chars: int = 50000):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_rows = max_rows
        self._max_chars = max_chars
        self._start_cleanup_thread()

    def get_connection(self, session_id: str) -> duckdb.DuckDBPyConnection:
        """Get or create an in-memory DuckDB connection for this session."""
        with self._lock:
            if session_id not in self._sessions:
                conn = duckdb.connect(":memory:")
                self._sessions[session_id] = {
                    "conn": conn,
                    "created": time.time(),
                    "last_used": time.time(),
                }
                logger.info(f"New session DB: {session_id[:12]}...")
            else:
                self._sessions[session_id]["last_used"] = time.time()

            return self._sessions[session_id]["conn"]

    def close_session(self, session_id: str):
        """Close and remove a session's database."""
        with self._lock:
            if session_id in self._sessions:
                try:
                    self._sessions[session_id]["conn"].close()
                except Exception:
                    pass
                del self._sessions[session_id]
                logger.info(f"Closed session DB: {session_id[:12]}...")

    def _cleanup_expired(self):
        """Remove sessions that haven't been used recently."""
        with self._lock:
            now = time.time()
            expired = [
                sid for sid, info in self._sessions.items()
                if now - info["last_used"] > SESSION_TTL
            ]
            for sid in expired:
                try:
                    self._sessions[sid]["conn"].close()
                except Exception:
                    pass
                del self._sessions[sid]
                logger.info(f"Expired session DB: {sid[:12]}...")

    def _start_cleanup_thread(self):
        def _run():
            while True:
                time.sleep(300)  # Check every 5 minutes
                self._cleanup_expired()

        thread = threading.Thread(target=_run, daemon=True, name="session-cleanup")
        thread.start()

    def get_client(self, session_id: str) -> "SessionClient":
        """Get a DatabaseClient-compatible wrapper for this session."""
        return SessionClient(self, session_id, self._max_rows, self._max_chars)

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)


class SessionClient:
    """DatabaseClient-compatible wrapper around a session's DuckDB connection."""

    def __init__(self, mgr: SessionDatabaseManager, session_id: str,
                 max_rows: int, max_chars: int):
        self._mgr = mgr
        self._session_id = session_id
        self._max_rows = max_rows
        self._max_chars = max_chars

    def query(self, sql: str) -> dict[str, Any]:
        """Execute query and return JSON-serializable result."""
        conn = self._mgr.get_connection(self._session_id)
        try:
            q = conn.execute(sql)
            if not q.description:
                return {"success": True, "rowCount": 0}

            columns = [d[0] for d in q.description]
            column_types = [str(d[1]) for d in q.description]
            raw_rows = q.fetchmany(self._max_rows + 1)
            has_more = len(raw_rows) > self._max_rows
            if has_more:
                raw_rows = raw_rows[:self._max_rows]
            rows = [list(row) for row in raw_rows]

            result: dict[str, Any] = {
                "success": True,
                "columns": columns,
                "columnTypes": column_types,
                "rows": rows,
                "rowCount": len(rows),
            }
            if has_more:
                result["truncated"] = True
                result["warning"] = f"Results limited to {self._max_rows} rows."
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "errorType": type(e).__name__}

    def execute_raw(self, sql: str) -> tuple[list[str], list[str], list[list[Any]]]:
        """Execute and return raw results for catalog tools."""
        conn = self._mgr.get_connection(self._session_id)
        q = conn.execute(sql)
        columns = [d[0] for d in q.description] if q.description else []
        column_types = [str(d[1]) for d in q.description] if q.description else []
        rows = [list(row) for row in q.fetchall()]
        return columns, column_types, rows
