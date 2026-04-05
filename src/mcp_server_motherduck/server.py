"""
FastMCP Server for MotherDuck and DuckDB.

This module creates and configures the FastMCP server with all tools.
"""

import json
import logging
import os
from pathlib import Path

from fastmcp import FastMCP, Context
from fastmcp.utilities.types import Image
from mcp.types import Icon

from .configs import SERVER_VERSION
from .database import DatabaseClient
from .session_db import SessionDatabaseManager
from .instructions import get_instructions
from .tools.describe_data import describe_data as describe_data_fn
from .tools.execute_query import execute_query as execute_query_fn
from .tools.export_csv import export_csv as export_csv_fn
from .tools.import_data import import_data as import_data_fn
from .tools.import_file import import_file as import_file_fn
from .tools.list_columns import list_columns as list_columns_fn
from .tools.list_databases import list_databases as list_databases_fn
from .tools.list_files import list_files as list_files_fn
from .tools.list_tables import list_tables as list_tables_fn
from .tools.switch_database_connection import (
    switch_database_connection as switch_database_connection_fn,
)

logger = logging.getLogger("mcp_server_motherduck")

# Server icon - embedded as data URI from local file
ASSETS_DIR = Path(__file__).parent / "assets"
ICON_PATH = ASSETS_DIR / "duck_feet_square.png"


def create_mcp_server(
    db_path: str,
    motherduck_token: str | None = None,
    home_dir: str | None = None,
    saas_mode: bool = False,
    read_only: bool = False,
    ephemeral_connections: bool = True,
    max_rows: int = 1024,
    max_chars: int = 50000,
    query_timeout: int = -1,
    init_sql: str | None = None,
    allow_switch_databases: bool = False,
    motherduck_connection_parameters: str | None = None,
    data_dir: str | None = None,
    base_url: str = "http://localhost:8000",
) -> FastMCP:
    """
    Create and configure the FastMCP server.

    Args:
        db_path: Path to database (local file, :memory:, md:, or s3://)
        motherduck_token: MotherDuck authentication token
        home_dir: Home directory for DuckDB
        saas_mode: Enable MotherDuck SaaS mode
        read_only: Enable read-only mode
        ephemeral_connections: Use temporary connections for read-only local files
        max_rows: Maximum rows to return from queries
        max_chars: Maximum characters in query results
        query_timeout: Query timeout in seconds (-1 to disable)
        init_sql: SQL file path or string to execute on startup
        allow_switch_databases: Enable the switch_database_connection tool
        motherduck_connection_parameters: Additional MotherDuck connection string parameters (e.g. "session_hint=mcp&dbinstance_inactivity_ttl=0s")
        data_dir: Directory for structured data files (JSON, CSV, Parquet). Enables list_files and import_file tools.

    Returns:
        Configured FastMCP server instance
    """
    # Create database client
    db_client = DatabaseClient(
        db_path=db_path,
        motherduck_token=motherduck_token,
        home_dir=home_dir,
        saas_mode=saas_mode,
        read_only=read_only,
        ephemeral_connections=ephemeral_connections,
        max_rows=max_rows,
        max_chars=max_chars,
        query_timeout=query_timeout,
        init_sql=init_sql,
        motherduck_connection_parameters=motherduck_connection_parameters,
    )

    # Session-aware database manager for per-chat isolation
    session_mgr = SessionDatabaseManager(max_rows=max_rows, max_chars=max_chars)

    def _get_session_id(ctx: Context) -> str:
        """Extract session ID from FastMCP context, fallback to 'default'."""
        sid = getattr(ctx, "session_id", None)
        if not sid:
            sid = getattr(ctx, "request_id", None)
        return str(sid) if sid else "default"

    # Get instructions with connection context
    instructions = get_instructions(
        read_only=read_only,
        saas_mode=saas_mode,
        db_path=db_path,
        allow_switch_databases=allow_switch_databases,
    )

    # Create server icon from local file
    icons = []
    if ICON_PATH.exists():
        img = Image(path=str(ICON_PATH))
        icons.append(Icon(src=img.to_data_uri(), mimeType="image/png"))

    # Create FastMCP server with icon
    mcp = FastMCP(
        name="mcp-server-motherduck",
        instructions=instructions,
        version=SERVER_VERSION,
        icons=icons if icons else None,
    )

    # Base URL for export download links
    _base_url = base_url.rstrip("/")

    # Define query tool annotations (dynamic based on read_only flag)
    query_annotations = {
        "readOnlyHint": read_only,
        "destructiveHint": not read_only,
        "openWorldHint": False,
    }

    # Catalog tool annotations (always read-only)
    catalog_annotations = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }

    # Switch database annotations (open world - can connect to any database)
    switch_db_annotations = {
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    }

    # Register query tool
    @mcp.tool(
        name="execute_query",
        title="Execute Query",
        description="Execute a SQL query on the DuckDB or MotherDuck database. Unqualified table names resolve to current_database() and current_schema() automatically. Fully qualified names (database.schema.table) are only needed when multiple DuckDB databases are attached or when connected to MotherDuck.",
        annotations=query_annotations,
    )
    def execute_query(sql: str, ctx: Context = None) -> str:
        """
        Execute a SQL query on the session's DuckDB database.

        Args:
            sql: SQL query to execute (DuckDB SQL dialect)

        Returns:
            JSON string with query results

        Raises:
            ValueError: If the query fails
        """
        sid = _get_session_id(ctx) if ctx else "default"
        client = session_mgr.get_client(sid)
        result = client.query(sql)
        if not result.get("success", True):
            raise ValueError(json.dumps(result, indent=2, default=str))
        return json.dumps(result, indent=2, default=str)

    # Register list_databases tool
    @mcp.tool(
        name="list_databases",
        title="List Databases",
        description="List all databases available in the connection. Useful when multiple DuckDB databases are attached or when connected to MotherDuck.",
        annotations=catalog_annotations,
    )
    def list_databases_tool() -> str:
        """
        List all databases available in the connection.

        Returns:
            JSON string with database list
        """
        result = list_databases_fn(db_client)
        return json.dumps(result, indent=2, default=str)

    # Register list_tables tool
    @mcp.tool(
        name="list_tables",
        title="List Tables",
        description="List all tables and views in a database with their comments. If database is not specified, uses the current database.",
        annotations=catalog_annotations,
    )
    def list_tables(database: str | None = None, schema: str | None = None) -> str:
        """
        List all tables and views in a database.

        Args:
            database: Database name to list tables from (defaults to current database)
            schema: Optional schema name to filter by

        Returns:
            JSON string with table/view list
        """
        result = list_tables_fn(db_client, database, schema)
        return json.dumps(result, indent=2, default=str)

    # Register list_columns tool
    @mcp.tool(
        name="list_columns",
        title="List Columns",
        description="List all columns of a table or view with their types and comments. If database/schema are not specified, uses the current database/schema.",
        annotations=catalog_annotations,
    )
    def list_columns(table: str, database: str | None = None, schema: str | None = None) -> str:
        """
        List all columns of a table or view.

        Args:
            table: Table or view name
            database: Database name (defaults to current database)
            schema: Schema name (defaults to current schema)

        Returns:
            JSON string with column list
        """
        result = list_columns_fn(table, db_client, database, schema)
        return json.dumps(result, indent=2, default=str)

    # Conditionally register switch_database_connection tool
    if allow_switch_databases:
        # Store server's read_only setting for switch_database_connection
        server_read_only_mode = read_only

        @mcp.tool(
            name="switch_database_connection",
            title="Switch Database Connection",
            description="Switch to a different database connection. For local files, use absolute paths only. The new connection respects the server's read-only/read-write mode. For local files, the file must exist unless create_if_not_exists=True (requires read-write mode).",
            annotations=switch_db_annotations,
        )
        def switch_database_connection(path: str, create_if_not_exists: bool = False) -> str:
            """
            Switch to a different primary database.

            Args:
                path: Database path. For local files, must be an absolute path.
                      Also accepts :memory:, md:database_name, or s3:// paths.
                create_if_not_exists: If True, create the database file if it doesn't exist.
                                   Only works in read-write mode.

            Returns:
                JSON string with result
            """
            result = switch_database_connection_fn(
                path=path,
                db_client=db_client,
                server_read_only=server_read_only_mode,
                create_if_not_exists=create_if_not_exists,
            )
            return json.dumps(result, indent=2, default=str)

    # Register file tools (when data_dir is configured)
    if data_dir:
        @mcp.tool(
            name="list_files",
            title="List Files",
            description="List data files available for import. Use filter to find a specific file by name or ID from chat context.",
            annotations=catalog_annotations,
        )
        def list_files_tool(filter: str | None = None, limit: int = 50, offset: int = 0) -> str:
            """
            List available data files.

            Args:
                filter: Only show files matching this string (file ID or name from chat)
                limit: Max files to return (default 50)
                offset: Skip first N files (default 0)

            Returns:
                JSON string with file list
            """
            result = list_files_fn(data_dir, filter, limit, offset)
            return json.dumps(result, indent=2, default=str)

        @mcp.tool(
            name="import_file",
            title="Import File",
            description="Import a data file as a DuckDB table. Auto-detects format (JSON, CSV, Parquet) from content. Creates a flattened detail table for JSON key-value objects.",
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        def import_file_tool(file_path: str, table_name: str | None = None, ctx: Context = None) -> str:
            """
            Import a file as a DuckDB table.

            Args:
                file_path: File name or path (relative to data dir or absolute)
                table_name: Optional custom table name (auto-generated from filename if omitted)

            Returns:
                JSON string with import results including schema
            """
            sid = _get_session_id(ctx) if ctx else "default"
            client = session_mgr.get_client(sid)
            result = import_file_fn(file_path, client, table_name, data_dir)
            return json.dumps(result, indent=2, default=str)

    # Register import_data tool (receive content from chat uploads)
    @mcp.tool(
        name="import_data",
        title="Import Data",
        description="Import raw data content (JSON or CSV) into a DuckDB table. Pass file content as a string.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def import_data_tool(
        content: str,
        format: str = "auto",
        table_name: str = "uploaded_data",
        ctx: Context = None,
    ) -> str:
        """
        Import raw data content as a DuckDB table.

        Args:
            content: Raw file content (JSON string, CSV text)
            format: Data format - "json", "csv", or "auto" (detect from content)
            table_name: Table name to create (default: uploaded_data)

        Returns:
            JSON string with import results including schema
        """
        sid = _get_session_id(ctx) if ctx else "default"
        client = session_mgr.get_client(sid)
        result = import_data_fn(content, client, format, table_name)
        return json.dumps(result, indent=2, default=str)

    # Register export_csv tool
    @mcp.tool(
        name="export_csv",
        title="Export CSV",
        description="Execute a SQL query and save results as a downloadable CSV file. Returns a download URL. Use when the user wants to download or save query results.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
        },
    )
    def export_csv_tool(sql: str, filename: str | None = None, ctx: Context = None) -> str:
        """
        Execute a query and export results as CSV.

        Args:
            sql: SQL query to execute
            filename: Optional output filename (auto-generated if omitted)

        Returns:
            JSON string with download URL and row count
        """
        sid = _get_session_id(ctx) if ctx else "default"
        client = session_mgr.get_client(sid)
        result = export_csv_fn(sql, client, _base_url, filename)
        return json.dumps(result, indent=2, default=str)

    # Register describe_data tool
    @mcp.tool(
        name="describe_data",
        title="Describe Data",
        description="Get summary statistics for a table: row count, column types, null counts, unique value counts, and sample values. No SQL required.",
        annotations=catalog_annotations,
    )
    def describe_data_tool(table: str, ctx: Context = None) -> str:
        """
        Get summary statistics for a table.

        Args:
            table: Table name to describe

        Returns:
            JSON string with table statistics
        """
        sid = _get_session_id(ctx) if ctx else "default"
        client = session_mgr.get_client(sid)
        result = describe_data_fn(table, client)
        return json.dumps(result, indent=2, default=str)

    logger.info(f"FastMCP server created with {len(mcp._tool_manager._tools)} tools")

    return mcp
