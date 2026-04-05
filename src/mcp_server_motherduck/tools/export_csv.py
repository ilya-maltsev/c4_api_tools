"""
Export CSV tool - Execute a query and save results as a downloadable CSV file.

Files are written to EXPORT_DIR and served via the file server.
Each export gets a UUID prefix to avoid collisions.
"""

import os
import time
import uuid
from typing import Any

from typing import Protocol


class _DBClient(Protocol):
    def query(self, sql: str) -> dict: ...

DESCRIPTION = (
    "Execute a SQL query and export the results as a CSV file. "
    "Returns a download URL. Use this when the user wants "
    "to save or download query results."
)

EXPORT_DIR = os.environ.get("MCP_EXPORT_DIR", "/exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


def export_csv(
    sql: str,
    db_client: _DBClient,
    base_url: str,
    filename: str | None = None,
) -> dict[str, Any]:
    """
    Execute a query and save results as CSV.

    Args:
        sql: SQL query to execute
        db_client: DatabaseClient instance
        base_url: Base URL of the file server for download links
        filename: Optional output filename (auto-generated if omitted)

    Returns:
        JSON-serializable dict with download URL and row count
    """
    try:
        if not filename:
            filename = f"export_{int(time.time())}.csv"

        if not filename.endswith(".csv"):
            filename += ".csv"

        # Sanitize base name, add UUID prefix for uniqueness
        clean = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
        disk_name = f"{uuid.uuid4()}_{clean}"

        out_path = os.path.realpath(os.path.join(EXPORT_DIR, disk_name))
        if not out_path.startswith(os.path.realpath(EXPORT_DIR)):
            return {"success": False, "error": "Invalid filename."}

        escaped_path = out_path.replace("'", "''")
        export_sql = f"COPY ({sql}) TO '{escaped_path}' (HEADER, DELIMITER ',')"
        result = db_client.query(export_sql)

        if not result.get("success", True):
            return {
                "success": False,
                "error": result.get("error", "Export failed"),
            }

        stat = os.stat(out_path)
        count_result = db_client.query(f"SELECT count(*) FROM read_csv_auto('{escaped_path}')")
        row_count = 0
        if count_result.get("success") and count_result.get("rows"):
            row_count = count_result["rows"][0][0]

        download_url = f"{base_url}/exports/{disk_name}"

        return {
            "success": True,
            "filename": clean,
            "download_url": download_url,
            "rowCount": row_count,
            "size_bytes": stat.st_size,
            "hint": f"CSV exported ({row_count} rows). [Download {clean}]({download_url})",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }
