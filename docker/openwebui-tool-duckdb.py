"""
Open WebUI Native Tool: DuckDB Data Analyzer

Install as a Tool in Open WebUI (Admin -> Workspace -> Tools -> Add).
Receives uploaded file IDs via __files__, fetches content from Open WebUI API,
then sends to DuckDB MCP server for import and analysis.

Open WebUI 0.8.x flow:
  User uploads file → Open WebUI saves to internal storage (+ RAG) →
  tool receives file ID → tool fetches raw content via /api/v1/files/{id}/content →
  sends to DuckDB MCP via import_data tool
"""

import json
import os
import httpx
from typing import List, Optional
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        MCP_SERVER_URL: str = Field(
            default="http://duckdb-mcp:8000/mcp",
            description="URL of the DuckDB MCP server (StreamableHTTP endpoint)",
        )
        OPENWEBUI_URL: str = Field(
            default="http://localhost:8080",
            description="Internal Open WebUI URL (for fetching uploaded files)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._session_id: Optional[str] = None

    async def _ensure_session(self) -> str:
        """Initialize MCP session if needed, return session ID."""
        if self._session_id:
            return self._session_id

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.valves.MCP_SERVER_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "openwebui-tool", "version": "1.0"},
                    },
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            self._session_id = resp.headers.get("mcp-session-id")
            return self._session_id

    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool and return parsed result."""
        session_id = await self._ensure_session()

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                self.valves.MCP_SERVER_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id or "",
                },
            )

        # Parse SSE response
        text = resp.text
        for line in text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                content = data.get("result", {}).get("content", [{}])
                if content:
                    try:
                        return json.loads(content[0].get("text", "{}"))
                    except json.JSONDecodeError:
                        return {"text": content[0].get("text", "")}
        return {"error": "No response from MCP server"}

    async def _get_file_content(self, file_obj: dict, __user__: dict = None) -> tuple[str, str]:
        """
        Fetch file content from Open WebUI's internal API.
        Returns (content, filename) tuple.

        Open WebUI 0.8.x stores files internally and passes file metadata
        (including ID) to tools. We fetch the actual content via the API.
        """
        file_id = file_obj.get("id", "")
        file_name = file_obj.get("name", "unknown")

        # Try reading directly from Open WebUI's upload path
        # In 0.8.x files are stored at /app/backend/data/uploads/<id>_<name>
        # or /app/backend/data/files/<id>/<name>
        for pattern in [
            f"/app/backend/data/uploads/{file_id}_{file_name}",
            f"/app/backend/data/uploads/{file_id}",
            f"/app/backend/data/files/{file_id}/{file_name}",
            f"/app/backend/data/files/{file_id}",
        ]:
            try:
                if os.path.isfile(pattern):
                    with open(pattern, "r") as f:
                        return f.read(), file_name
            except Exception:
                continue

        # Try scanning the uploads directory for a file matching the ID
        uploads_dir = "/app/backend/data/uploads"
        if os.path.isdir(uploads_dir):
            for entry in os.listdir(uploads_dir):
                if file_id in entry:
                    fpath = os.path.join(uploads_dir, entry)
                    if os.path.isfile(fpath):
                        try:
                            with open(fpath, "r") as f:
                                return f.read(), file_name
                        except Exception:
                            continue

        # Fallback: fetch via Open WebUI API
        api_key = ""
        if __user__ and "token" in __user__:
            api_key = __user__["token"]

        if file_id and api_key:
            base_url = self.valves.OPENWEBUI_URL.rstrip("/")
            headers = {"Authorization": f"Bearer {api_key}"}
            for endpoint in [
                f"{base_url}/api/v1/files/{file_id}/content",
                f"{base_url}/api/v1/files/{file_id}",
            ]:
                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(endpoint, headers=headers)
                        if resp.status_code == 200:
                            # Check if response is JSON metadata or actual content
                            ct = resp.headers.get("content-type", "")
                            if "application/json" in ct:
                                data = resp.json()
                                # Could be metadata with content field
                                if "content" in data:
                                    return data["content"], file_name
                                if "data" in data and "content" in data["data"]:
                                    return data["data"]["content"], file_name
                            else:
                                return resp.text, file_name
                except Exception:
                    continue

        return "", file_name

    async def upload_and_analyze(
        self,
        question: str,
        table_name: str = "uploaded_data",
        __files__: List[dict] = [],
        __user__: dict = {},
        __event_emitter__=None,
    ) -> str:
        """
        Upload a data file and import it into DuckDB for analysis.
        Attach a JSON or CSV file to your message, and this tool will
        import it into a queryable DuckDB table.

        :param question: What you want to know about the data
        :param table_name: Name for the imported table (default: uploaded_data)
        :param __files__: Files uploaded by the user (auto-populated by Open WebUI)
        :return: Import result with table schema
        """
        if not __files__:
            return "No file attached. Please upload a JSON or CSV file with your message."

        file_obj = __files__[0]
        file_name = file_obj.get("name", "unknown")

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": f"Reading {file_name}..."}}
            )

        content, file_name = await self._get_file_content(file_obj, __user__)

        if not content:
            # Debug dump
            safe_dump = {}
            for k, v in file_obj.items():
                if isinstance(v, dict):
                    safe_dump[k] = {fk: type(fv).__name__ for fk, fv in v.items()}
                elif isinstance(v, str):
                    safe_dump[k] = v[:200]
                else:
                    safe_dump[k] = type(v).__name__
            return (
                f"Could not read file content for '{file_name}'.\n\n"
                f"File object:\n```json\n{json.dumps(safe_dump, indent=2)}\n```"
            )

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": f"Importing {file_name}..."}}
            )

        # Detect format
        fmt = "auto"
        if file_name.endswith(".csv") or file_name.endswith(".tsv"):
            fmt = "csv"
        elif file_name.endswith(".json") or file_name.endswith(".jsonl"):
            fmt = "json"

        # Import via MCP
        result = await self._call_mcp_tool(
            "import_data",
            {"content": content, "format": fmt, "table_name": table_name},
        )

        if not result.get("success", False):
            return f"Import failed: {result.get('error', 'Unknown error')}"

        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": "Analyzing structure..."}}
            )

        # Describe the imported table
        desc = await self._call_mcp_tool("describe_data", {"table": table_name})

        summary = (
            f"**Imported `{file_name}` as table `{table_name}`**\n\n"
            f"- Rows: {result.get('rowCount', '?')}\n"
            f"- Columns: {result.get('columnCount', '?')}\n\n"
        )

        if result.get("note"):
            summary += f"> {result['note']}\n\n"

        summary += "**Columns:**\n"
        for col in result.get("columns", []):
            summary += f"- `{col['name']}` ({col['type']})\n"

        summary += f"\nTable is ready. Ask me anything about the data."

        return summary

    async def query_data(
        self,
        sql: str,
        __event_emitter__=None,
    ) -> str:
        """
        Run a SQL query on the DuckDB database.
        Use DuckDB SQL syntax. Tables created by upload_and_analyze are available.

        :param sql: SQL query to execute (DuckDB dialect)
        :return: Query results as formatted text
        """
        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": "Executing query..."}}
            )

        result = await self._call_mcp_tool("execute_query", {"sql": sql})

        if not result.get("success", False):
            return f"Query error: {result.get('error', 'Unknown error')}"

        # Format as markdown table
        columns = result.get("columns", [])
        rows = result.get("rows", [])

        if not columns:
            return "Query returned no results."

        header = "| " + " | ".join(str(c) for c in columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        body = "\n".join(
            "| " + " | ".join(str(v) for v in row) + " |" for row in rows
        )

        output = f"{header}\n{separator}\n{body}"

        if result.get("truncated"):
            output += f"\n\n*{result.get('warning', 'Results truncated.')}*"

        output += f"\n\n*{result.get('rowCount', 0)} rows returned.*"
        return output
