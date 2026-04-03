"""
Import Data tool - Accept raw file content from chat and load into DuckDB table.

This tool receives the file content as a string (passed by the LLM from a chat
upload) and creates a queryable table without needing shared filesystem access.
"""

import json
import os
import tempfile
from typing import Any

from ..database import DatabaseClient, quote_sql_identifier

DESCRIPTION = (
    "Import raw data content (JSON, CSV) directly into a DuckDB table. "
    "Use this when a user uploads a file in chat. The LLM should pass the "
    "file content as the 'content' argument. Auto-detects format and schema."
)


def import_data(
    content: str,
    db_client: DatabaseClient,
    format: str = "auto",
    table_name: str = "uploaded_data",
) -> dict[str, Any]:
    """
    Import raw data content as a DuckDB table.

    Args:
        content: Raw file content (JSON string, CSV text, etc.)
        db_client: DatabaseClient instance
        format: Data format - "json", "csv", or "auto" (detect from content)
        table_name: Table name to create

    Returns:
        JSON-serializable dict with import results
    """
    try:
        if not content or not content.strip():
            return {"success": False, "error": "Empty content provided."}

        # Auto-detect format
        if format == "auto":
            stripped = content.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                format = "json"
            else:
                format = "csv"

        quoted_table = quote_sql_identifier(table_name)

        # Write content to temp file so DuckDB can read it
        suffix = ".json" if format == "json" else ".csv"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, dir="/tmp"
        ) as f:
            f.write(content)
            tmp_path = f.name

        try:
            escaped_path = tmp_path.replace("'", "''")

            if format == "json":
                result = _import_json_content(escaped_path, quoted_table, table_name, db_client)
            else:
                sql = f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_csv_auto('{escaped_path}')"
                db_client.query(sql)
                result = _get_result(quoted_table, table_name, db_client)
        finally:
            os.unlink(tmp_path)

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }


def _import_json_content(
    escaped_path: str,
    quoted_table: str,
    table_name: str,
    db_client: DatabaseClient,
) -> dict[str, Any]:
    """Import JSON, handling both array and key-value object formats."""
    # Try array of objects first
    try:
        sql = f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_json_auto('{escaped_path}')"
        result = db_client.query(sql)
        if result.get("success", True):
            info = _get_result(quoted_table, table_name, db_client)
            if info.get("rowCount", 0) > 1:
                return info
    except Exception:
        pass

    # Fall back to key-value object (like ACL files)
    try:
        sql = f"""
            CREATE OR REPLACE TABLE {quoted_table} AS
            SELECT
                j.key as entity_key,
                j.value as entity_value
            FROM read_text('{escaped_path}') t,
            LATERAL json_each(t.content::JSON) j
        """
        result = db_client.query(sql)
        if result.get("success", True):
            info = _get_result(quoted_table, table_name, db_client)
            if info.get("rowCount", 0) > 0:
                info["note"] = (
                    "JSON key-value object imported as rows (entity_key, entity_value). "
                    f"Use json_extract on entity_value to query nested fields. "
                    f"Example: SELECT entity_key, entity_value->>'type' FROM {table_name}"
                )
                return info
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not parse JSON: {e}",
        }


def _get_result(
    quoted_table: str,
    table_name: str,
    db_client: DatabaseClient,
) -> dict[str, Any]:
    """Get table info after import."""
    count_result = db_client.query(f"SELECT count(*) as cnt FROM {quoted_table}")
    row_count = 0
    if count_result.get("success") and count_result.get("rows"):
        row_count = count_result["rows"][0][0]

    cols_result = db_client.query(f"DESCRIBE {quoted_table}")
    columns = []
    if cols_result.get("success") and cols_result.get("rows"):
        for row in cols_result["rows"]:
            columns.append({"name": row[0], "type": row[1]})

    return {
        "success": True,
        "table": table_name,
        "rowCount": row_count,
        "columnCount": len(columns),
        "columns": columns,
        "hint": f"Table '{table_name}' is ready. Use execute_query to analyze it.",
    }
