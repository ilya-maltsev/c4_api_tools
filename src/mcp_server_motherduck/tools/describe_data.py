"""
Describe Data tool - Get summary statistics for a table without writing SQL.
"""

from typing import Any

from ..database import DatabaseClient, quote_sql_identifier

DESCRIPTION = (
    "Get summary statistics for a table: row count, column types, sample values, "
    "null counts, and unique value counts. No SQL required."
)


def describe_data(
    table: str,
    db_client: DatabaseClient,
) -> dict[str, Any]:
    """
    Get comprehensive summary statistics for a table.

    Args:
        table: Table name to describe
        db_client: DatabaseClient instance

    Returns:
        JSON-serializable dict with table statistics
    """
    try:
        quoted = quote_sql_identifier(table)

        # Row count
        count_result = db_client.query(f"SELECT count(*) as cnt FROM {quoted}")
        row_count = 0
        if count_result.get("success") and count_result.get("rows"):
            row_count = count_result["rows"][0][0]

        # Column info via DESCRIBE
        desc_result = db_client.query(f"DESCRIBE {quoted}")
        if not desc_result.get("success"):
            return desc_result

        columns = []
        for row in desc_result.get("rows", []):
            col_name = row[0]
            col_type = row[1]
            col_quoted = quote_sql_identifier(col_name)

            col_info = {
                "name": col_name,
                "type": col_type,
            }

            # Get null count and unique count per column
            try:
                stats_sql = (
                    f"SELECT "
                    f"count(*) FILTER (WHERE {col_quoted} IS NULL) as nulls, "
                    f"count(DISTINCT {col_quoted}) as uniques "
                    f"FROM {quoted}"
                )
                stats = db_client.query(stats_sql)
                if stats.get("success") and stats.get("rows"):
                    col_info["nullCount"] = stats["rows"][0][0]
                    col_info["uniqueCount"] = stats["rows"][0][1]
            except Exception:
                pass

            # Get sample values (up to 5 distinct)
            try:
                sample_sql = (
                    f"SELECT DISTINCT {col_quoted} "
                    f"FROM {quoted} "
                    f"WHERE {col_quoted} IS NOT NULL "
                    f"LIMIT 5"
                )
                sample = db_client.query(sample_sql)
                if sample.get("success") and sample.get("rows"):
                    col_info["sampleValues"] = [row[0] for row in sample["rows"]]
            except Exception:
                pass

            columns.append(col_info)

        return {
            "success": True,
            "table": table,
            "rowCount": row_count,
            "columnCount": len(columns),
            "columns": columns,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }
