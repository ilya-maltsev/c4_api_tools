"""
MCP Tools for MotherDuck/DuckDB server.

Each tool is defined in its own module and exported here.
"""

from .describe_data import describe_data
from .execute_query import execute_query
from .export_csv import export_csv
from .import_data import import_data
from .import_file import import_file
from .list_columns import list_columns
from .list_databases import list_databases
from .list_files import list_files
from .list_tables import list_tables
from .switch_database_connection import switch_database_connection

__all__ = [
    "describe_data",
    "execute_query",
    "export_csv",
    "import_data",
    "import_file",
    "list_columns",
    "list_databases",
    "list_files",
    "list_tables",
    "switch_database_connection",
]
