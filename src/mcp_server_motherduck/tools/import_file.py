"""
Import File tool - Auto-detect file format and create a queryable table from it.

Supports JSON, JSONL, CSV, TSV, and Parquet files.
Uses DuckDB's native file readers (read_json_auto, read_csv_auto, read_parquet).

Handles Open WebUI upload filenames: <uuid>_<original_name>
Accepts: UUID, original filename, UUID_filename, or full path.
"""

import os
import re
from typing import Any

from ..database import DatabaseClient, quote_sql_identifier
from .list_files import detect_format, strip_uuid_prefix

# Matches a bare UUID (no extension, no underscore suffix)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

DESCRIPTION = (
    "Import a structured data file (JSON, JSONL, CSV, Parquet) as a table in the database. "
    "Auto-detects file format and schema. The table can then be queried with execute_query. "
    "For JSON files with nested objects (e.g. key-value maps), the file is automatically "
    "flattened into rows with a 'key' column and value columns."
)

# Map file extensions to DuckDB reader functions
FORMAT_READERS = {
    ".json": "read_json_auto",
    ".jsonl": "read_json_auto",
    ".ndjson": "read_json_auto",
    ".csv": "read_csv_auto",
    ".tsv": "read_csv_auto",
    ".parquet": "read_parquet",
    ".pq": "read_parquet",
}


def import_file(
    file_path: str,
    db_client: DatabaseClient,
    table_name: str | None = None,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """
    Import a structured data file as a DuckDB table.

    Args:
        file_path: Path to the file (absolute or relative to data_dir)
        db_client: DatabaseClient instance
        table_name: Optional table name (auto-generated from filename if not provided)
        data_dir: Base directory for resolving relative paths

    Returns:
        JSON-serializable dict with import results
    """
    try:
        # Resolve file path — handles:
        #   "acl_users.json"                        → search by original name
        #   "7296aa8f-cfd2-48a2-b5d6-4d7ed92da802"  → search by UUID prefix
        #   "7296aa8f-..._acl_users.json"            → exact disk name
        #   "/uploads/7296aa8f-..._acl_users.json"   → absolute path
        resolved = _resolve_file(file_path, data_dir)
        if resolved is None:
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "hint": "Use list_files to see available files.",
            }
        file_path = resolved

        # Detect format from file content, not extension
        clean_name = strip_uuid_prefix(os.path.basename(file_path))
        fmt = detect_format(file_path)
        if not fmt:
            return {
                "success": False,
                "error": f"Could not detect file format for: {clean_name}",
                "hint": "File must be JSON, CSV, or Parquet.",
            }

        ext = {"json": ".json", "csv": ".csv", "parquet": ".parquet"}[fmt]
        reader_fn = FORMAT_READERS[ext]

        # Generate table name from clean filename
        if not table_name:
            basename = os.path.splitext(clean_name)[0]
            table_name = "".join(c if c.isalnum() or c == "_" else "_" for c in basename)
            if table_name and table_name[0].isdigit():
                table_name = "t_" + table_name

        quoted_table = quote_sql_identifier(table_name)
        escaped_path = file_path.replace("'", "''")

        # For JSON files: detect if it's a key-value object (like ACL files)
        # and flatten it into rows automatically
        if ext == ".json":
            return _import_json(escaped_path, quoted_table, table_name, db_client)

        # For CSV/Parquet: straightforward import
        sql = f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM {reader_fn}('{escaped_path}')"
        db_client.query(sql)

        # Get row count and schema
        return _get_import_result(quoted_table, table_name, file_path, db_client)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }


def _resolve_file(file_path: str, data_dir: str | None) -> str | None:
    """
    Resolve a file reference to an actual path on disk.

    Accepts:
      - Absolute path: /uploads/uuid_file.json
      - Exact disk name: uuid_file.json
      - Original filename: file.json (searches for *_file.json)
      - Bare UUID: 7296aa8f-... (searches for uuid_*)
    """
    # Absolute path — use as-is
    if os.path.isabs(file_path) and os.path.isfile(file_path):
        return file_path

    if not data_dir or not os.path.isdir(data_dir):
        return None

    # Try exact match in data_dir
    candidate = os.path.join(data_dir, file_path)
    if os.path.isfile(candidate):
        return candidate

    # Scan directory for match by UUID prefix or original filename
    query = file_path.lower()
    is_uuid = bool(_UUID_RE.match(query))

    for entry in os.listdir(data_dir):
        entry_lower = entry.lower()
        entry_path = os.path.join(data_dir, entry)
        if not os.path.isfile(entry_path):
            continue

        if is_uuid:
            # Match: entry starts with the UUID
            if entry_lower.startswith(query):
                return entry_path
        else:
            # Match: entry ends with _<original_name> (after UUID prefix)
            clean = strip_uuid_prefix(entry)
            if clean.lower() == query:
                return entry_path

    return None


def _import_json(
    escaped_path: str,
    quoted_table: str,
    table_name: str,
    db_client: DatabaseClient,
) -> dict[str, Any]:
    """
    Import JSON file, handling both array-of-objects and key-value-map formats.

    Array format [{...}, {...}] → imported directly as rows.
    Object format {"key1": {...}, "key2": {...}} → flattened to rows via json_each.
    """
    # First try: direct read_json_auto (works for arrays of objects)
    try:
        sql = f"CREATE OR REPLACE TABLE {quoted_table} AS SELECT * FROM read_json_auto('{escaped_path}')"
        result = db_client.query(sql)
        if result.get("success", True):
            import_result = _get_import_result(quoted_table, table_name, escaped_path, db_client)
            row_count = import_result.get("rowCount", 0)
            # Multiple rows = array of objects, good shape
            # 1 row = key-value object read as columns, fall through
            if row_count > 1:
                return import_result
    except Exception:
        pass

    # Second try: key-value JSON objects (like ACL files)
    # Read as raw text, use json_each to flatten keys into rows
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
            import_result = _get_import_result(quoted_table, table_name, escaped_path, db_client)
            if import_result.get("rowCount", 0) > 0:
                import_result["note"] = (
                    "JSON key-value object imported as rows (entity_key, entity_value). "
                    "Use json_extract on entity_value to access nested fields. "
                    f"Example: SELECT entity_key, entity_value->>'type' FROM {table_name}"
                )
                return import_result
    except Exception as e:
        return {
            "success": False,
            "error": f"Could not parse JSON file: {e}",
            "hint": "The JSON structure may not be supported. Try execute_query with read_json_auto() directly.",
        }


def _get_import_result(
    quoted_table: str,
    table_name: str,
    file_path: str,
    db_client: DatabaseClient,
) -> dict[str, Any]:
    """Get table info after import."""
    # Row count
    count_result = db_client.query(f"SELECT count(*) as cnt FROM {quoted_table}")
    row_count = 0
    if count_result.get("success") and count_result.get("rows"):
        row_count = count_result["rows"][0][0]

    # Column info
    cols_result = db_client.query(f"DESCRIBE {quoted_table}")
    columns = []
    if cols_result.get("success") and cols_result.get("rows"):
        for row in cols_result["rows"]:
            columns.append({"name": row[0], "type": row[1]})

    return {
        "success": True,
        "table": table_name,
        "file": file_path,
        "rowCount": row_count,
        "columnCount": len(columns),
        "columns": columns,
        "hint": f"Table '{table_name}' is ready. Use execute_query to analyze it.",
    }
