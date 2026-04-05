"""
Import Data tool - Accept raw file content and load into DuckDB table.

Writes content to a temp file, then delegates to import_file for
consistent handling (format detection, detail table, field summary).
"""

import os
import tempfile
from typing import Any

from .import_file import import_file


DESCRIPTION = (
    "Import raw data content (JSON, CSV) directly into a DuckDB table. "
    "Pass file content as a string. Auto-detects format and schema."
)


def import_data(
    content: str,
    db_client,
    format: str = "auto",
    table_name: str = "uploaded_data",
) -> dict[str, Any]:
    """
    Import raw data content as a DuckDB table.

    Writes to temp file, delegates to import_file for full processing
    (format detection, detail table creation, field summary).

    Args:
        content: Raw file content (JSON string, CSV text)
        db_client: DatabaseClient or SessionClient instance
        format: Data format - "json", "csv", or "auto"
        table_name: Table name to create

    Returns:
        JSON-serializable dict with import results
    """
    try:
        if not content or not content.strip():
            return {"success": False, "error": "Empty content provided."}

        MAX_CONTENT_SIZE = 50 * 1024 * 1024  # 50 MB
        if len(content) > MAX_CONTENT_SIZE:
            return {
                "success": False,
                "error": f"Content too large ({len(content)} bytes). Max {MAX_CONTENT_SIZE} bytes.",
                "hint": "Use import_file with a file on disk instead.",
            }

        # Detect suffix for temp file
        if format == "auto":
            stripped = content.strip()
            suffix = ".json" if stripped.startswith("{") or stripped.startswith("[") else ".csv"
        elif format == "json":
            suffix = ".json"
        else:
            suffix = ".csv"

        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, dir="/tmp"
        ) as f:
            f.write(content)
            tmp_path = f.name

        try:
            # Delegate to import_file — gets full processing:
            # format detection, detail table, field summary, sql examples
            result = import_file(tmp_path, db_client, table_name, data_dir=None)
        finally:
            os.unlink(tmp_path)

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }
