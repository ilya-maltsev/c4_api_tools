"""
Import File tool - Auto-detect file format and create a queryable table from it.

Supports JSON, JSONL, CSV, TSV, and Parquet files.
Uses DuckDB's native file readers (read_json_auto, read_csv_auto, read_parquet).

Handles Open WebUI upload filenames: <uuid>_<original_name>
Accepts: UUID, original filename, UUID_filename, or full path.
"""

import json
import os
import re
from typing import Any

from ..database import quote_sql_identifier
from .list_files import detect_format, strip_uuid_prefix


CONFIG_PATH = os.environ.get(
    "MCP_IMPORT_CONFIG", "/config/import_config.json"
)
_DEFAULTS = {
    "sql_examples": {
        "base_table": [
            "SELECT entity_key, entity_value->>'field' FROM {table}"
        ],
        "detail_table": [
            "SELECT DISTINCT field_name FROM {detail_table} ORDER BY field_name",
            "SELECT entity_key, field_value FROM {detail_table} WHERE field_name = 'some_field'",
            "SELECT field_value, count(*) as cnt FROM {detail_table} GROUP BY field_value ORDER BY cnt DESC",
            "SELECT entity_key, count(*) as field_count FROM {detail_table} GROUP BY entity_key ORDER BY field_count DESC",
        ],
    },
    "queries": {
        "json_flatten": "SELECT j.key as entity_key, j.value as entity_value FROM read_text('{path}') t, LATERAL json_each(t.content::JSON) j",
        "detail_flatten": "SELECT entity_key, d.key as field_name, d.value::VARCHAR as field_value FROM {table}, LATERAL json_each(entity_value) d",
        "field_summary": "SELECT field_name, count(*) as total_rows, count(DISTINCT entity_key) as entity_count, count(DISTINCT field_value) as distinct_values, min(field_value) as sample_value FROM {detail_table} GROUP BY field_name ORDER BY field_name",
    },
}


def _load_config() -> dict:
    """Load import config. Mounted file overrides defaults."""
    cfg = dict(_DEFAULTS)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH) as f:
                custom = json.load(f)
            # Merge: custom keys override defaults
            for key in custom:
                if isinstance(custom[key], dict) and isinstance(cfg.get(key), dict):
                    cfg[key].update(custom[key])
                else:
                    cfg[key] = custom[key]
        except Exception:
            pass
    return cfg

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
    db_client,
    table_name: str | None = None,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """
    Import a structured data file as a DuckDB table.

    Args:
        file_path: Path to the file (absolute or relative to data_dir)
        db_client instance
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
    db_client,
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

    # Second try: key-value JSON objects
    # Import as entity_key + entity_value, then also create a flattened table
    try:
        cfg = _load_config()
        queries = cfg["queries"]

        # Base table: one row per top-level key
        flatten_sql = queries["json_flatten"].format(path=escaped_path)
        sql = f"CREATE OR REPLACE TABLE {quoted_table} AS {flatten_sql}"
        result = db_client.query(sql)
        if not result.get("success", True):
            raise Exception(result.get("error", "unknown"))

        import_result = _get_import_result(quoted_table, table_name, escaped_path, db_client)
        if import_result.get("rowCount", 0) == 0:
            raise Exception("No rows imported")

        # Try to create a flattened detail table
        detail_table = f"{table_name}_detail"
        detail_quoted = quote_sql_identifier(detail_table)
        try:
            detail_sql = queries["detail_flatten"].format(table=quoted_table)
            db_client.query(f"CREATE OR REPLACE TABLE {detail_quoted} AS {detail_sql}")

            detail_count = db_client.query(f"SELECT count(*) FROM {detail_quoted}")
            detail_rows = 0
            if detail_count.get("success") and detail_count.get("rows"):
                detail_rows = detail_count["rows"][0][0]
        except Exception:
            detail_table = None
            detail_rows = 0

        examples = cfg["sql_examples"]

        import_result["note"] = (
            f"JSON key-value object imported into table '{table_name}' "
            f"(entity_key, entity_value as JSON)."
        )
        import_result["sql_examples"] = [
            e.format(table=table_name) for e in examples.get("base_table", [])
        ]

        if detail_table and detail_rows > 0:
            import_result["note"] += (
                f" Also created '{detail_table}' — flattened: one row per field "
                f"(entity_key, field_name, field_value). {detail_rows} rows. "
                f"USE THIS TABLE for analysis — it is easier to query."
            )
            import_result["detail_table"] = detail_table
            import_result["detail_rows"] = detail_rows
            import_result["sql_examples"] = [
                e.format(table=table_name, detail_table=detail_table)
                for e in examples.get("detail_table", [])
            ]

            # Field summary using configurable query
            field_summary = _get_field_summary(detail_quoted, db_client, queries)
            if field_summary:
                import_result["field_summary"] = field_summary

                data_fields = field_summary.get("data_fields", [])
                metadata_fields = field_summary.get("metadata_fields", [])

                if data_fields and metadata_fields:
                    data_names = ", ".join(f["prefix"] for f in data_fields)
                    meta_names = ", ".join(f["field_name"] for f in metadata_fields)
                    import_result["action_required"] = (
                        f"Data fields detected: {data_names}. "
                        f"Metadata fields (likely noise): {meta_names}. "
                        f"Ask the user which fields to analyze. "
                        f"To get clean data, query only data fields from '{detail_table}' "
                        f"and strip any prefixes from field_value if needed."
                    )

        return import_result

    except Exception as e:
        return {
            "success": False,
            "error": f"Could not parse JSON file: {e}",
            "hint": "The JSON structure may not be supported. Try execute_query with read_json_auto() directly.",
        }


def _get_field_summary(detail_quoted: str, db_client, queries: dict) -> dict | None:
    """
    Analyze field names and auto-classify into data fields vs metadata.

    Heuristic: fields sharing a common prefix with numeric suffixes
    (e.g. access_to.0, access_to.1, item_3) are repeated data fields.
    Fields appearing once per entity with few distinct values are metadata.
    """
    try:
        sql = queries["field_summary"].format(detail_table=detail_quoted)
        result = db_client.query(sql)
        if not result.get("success") or not result.get("rows"):
            return None

        fields = []
        for row in result["rows"]:
            fields.append({
                "field_name": row[0],
                "total_rows": row[1],
                "entity_count": row[2],
                "distinct_values": row[3],
                "sample_value": str(row[4])[:100] if row[4] else None,
            })

        # Auto-classify: group by prefix (strip trailing .N or _N)
        from collections import defaultdict
        prefix_groups = defaultdict(list)
        for f in fields:
            name = f["field_name"]
            # Strip trailing separator + digits: "access_to.0" → "access_to"
            base = re.sub(r'[._]\d+$', '', name)
            prefix_groups[base].append(f)

        data_fields = []
        metadata_fields = []
        for prefix, group in prefix_groups.items():
            if len(group) > 1:
                # Multiple fields with same prefix = repeated data
                data_fields.append({
                    "prefix": prefix,
                    "count": len(group),
                    "total_rows": sum(f["total_rows"] for f in group),
                    "sample_value": group[0]["sample_value"],
                })
            else:
                f = group[0]
                metadata_fields.append({
                    "field_name": f["field_name"],
                    "distinct_values": f["distinct_values"],
                    "sample_value": f["sample_value"],
                })

        return {
            "data_fields": data_fields,
            "metadata_fields": metadata_fields,
            "all_fields": fields,
        }

    except Exception:
        return None


def _get_import_result(
    quoted_table: str,
    table_name: str,
    file_path: str,
    db_client,
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
