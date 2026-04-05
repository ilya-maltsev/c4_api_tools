"""
List Files tool - List structured data files available for import.

Handles Open WebUI upload filenames with UUID prefixes:
  9b7c206e-ab7d-4c36-953d-404e89291fcf_acl_users.json → acl_users.json
"""

import os
import re
from typing import Any

# Matches UUID prefix: 8-4-4-4-12 hex chars followed by underscore
_UUID_PREFIX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_",
    re.IGNORECASE,
)

def detect_format(file_path: str) -> str | None:
    """Detect file format using libmagic (content-based, not extension)."""
    try:
        import magic
        mime = magic.from_file(file_path, mime=True)
    except Exception:
        return _detect_format_fallback(file_path)

    MIME_MAP = {
        "application/json": "json",
        "text/json": "json",
        "text/csv": "csv",
        "text/tab-separated-values": "csv",
        "application/csv": "csv",
        "application/x-parquet": "parquet",
        "application/parquet": "parquet",
    }

    fmt = MIME_MAP.get(mime)
    if fmt:
        return fmt

    # libmagic often returns "text/plain" for JSON/CSV — sniff content
    if mime and mime.startswith("text/"):
        return _detect_format_fallback(file_path)

    return None


def _detect_format_fallback(file_path: str) -> str | None:
    """Fallback format detection by reading first bytes."""
    try:
        with open(file_path, "rb") as f:
            head = f.read(4096)
    except Exception:
        return None

    if not head:
        return None

    if head[:4] == b"PAR1":
        return "parquet"

    try:
        text = head.decode("utf-8").lstrip()
    except UnicodeDecodeError:
        return None

    if text.startswith("{") or text.startswith("["):
        return "json"

    lines = text.split("\n")
    if len(lines) >= 2 and ("," in lines[0] or "\t" in lines[0]):
        return "csv"

    return None


DESCRIPTION = (
    "List structured data files (JSON, JSONL, CSV, Parquet) available for import. "
    "These files can be imported as tables using import_file."
)


def strip_uuid_prefix(filename: str) -> str:
    """Strip Open WebUI UUID prefix from filename."""
    return _UUID_PREFIX.sub("", filename)


def list_files(data_dir: str, filter: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """
    List structured data files in the data directory.
    When used with shared uploads, pass the file ID or name from chat context as filter.

    Args:
        data_dir: Base directory to scan for files
        filter: Only show files matching this string (UUID or filename substring)
        limit: Max files to return
        offset: Skip first N files

    Returns:
        JSON-serializable dict with file list
    """
    try:
        if not filter:
            return {
                "success": False,
                "error": "Filter is required. Pass the file name or ID from the chat context.",
            }

        if not os.path.isdir(data_dir):
            return {
                "success": False,
                "error": f"Data directory not found: {data_dir}",
            }

        filter_lower = filter.lower()

        files = []
        for entry in sorted(os.listdir(data_dir)):
            filepath = os.path.join(data_dir, entry)
            if not os.path.isfile(filepath):
                continue

            # Apply filter — match against UUID prefix, clean name, or full disk name
            if filter_lower:
                entry_lower = entry.lower()
                clean_lower = strip_uuid_prefix(entry).lower()
                if (filter_lower not in entry_lower
                        and filter_lower not in clean_lower):
                    continue

            clean_name = strip_uuid_prefix(entry)
            fmt = detect_format(filepath)
            if not fmt:
                continue

            stat = os.stat(filepath)
            files.append({
                "name": clean_name,
                "disk_name": entry,
                "path": filepath,
                "format": fmt,
                "size_bytes": stat.st_size,
                "size_human": _human_size(stat.st_size),
            })

        total = len(files)
        paginated = files[offset:offset + limit]

        result = {
            "success": True,
            "directory": data_dir,
            "files": paginated,
            "fileCount": len(paginated),
            "total": total,
        }
        if offset + limit < total:
            result["has_more"] = True
            result["next_offset"] = offset + limit

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "errorType": type(e).__name__,
        }


def _human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
