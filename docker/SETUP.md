# Open WebUI + DuckDB MCP Setup Guide

## Architecture

```
User (browser)
    |
Open WebUI (:3000)
    |                    |
Ollama (:11434)     MCPO proxy (:8000)
  local LLM              |
                    mcp-server-motherduck (extended)
                    [embedded DuckDB engine]
                         |
                    /data/*.json, *.csv, *.parquet
                    /data/analytics.duckdb
```

User drops a structured file into `./data/` -> asks a question in chat ->
LLM calls MCP tools (list_files, import_file, execute_query) ->
DuckDB processes the data -> only results go into LLM context.

## MCP Tools (7 total)

Based on [mcp-server-motherduck](https://github.com/motherduckdb/mcp-server-motherduck),
extended with 3 additional tools for structured file handling.

### File tools (new)

| Tool | Description |
|------|-------------|
| `list_files` | List structured data files (JSON, JSONL, CSV, Parquet) in `/data/` directory |
| `import_file` | Import a file as a DuckDB table with auto-detected schema. JSON key-value objects (like ACL configs) are automatically flattened into rows |
| `describe_data` | Get summary stats for a table: row count, column types, null counts, unique counts, sample values |

### Database tools (upstream)

| Tool | Description |
|------|-------------|
| `execute_query` | Execute any SQL query (DuckDB dialect) |
| `list_databases` | List all attached databases |
| `list_tables` | List tables and views in a database |
| `list_columns` | List columns with types for a table |

### LLM workflow

```
1. list_files()              -> sees acl_users.json (22.8 KB, json)
2. import_file("acl_users.json") -> table created: 51 rows, 2 columns (entity_key, entity_value)
3. describe_data("acl_users")    -> 51 unique keys, JSON column, sample values
4. execute_query("SELECT ...")   -> analytical queries, only results in context
```

## Prerequisites

- Docker + Docker Compose
- 8+ GB RAM (for Ollama + LLM model)
- GPU optional (for faster LLM inference)

## File Structure

```
duckdb-openwebui/
|-- docker-compose.yml           # 3 services: open-webui, ollama, mcpo
|-- mcp-server-motherduck/       # Extended MCP server source (built into MCPO image)
|   `-- src/mcp_server_motherduck/
|       |-- tools/
|       |   |-- list_files.py    # NEW: scan /data/ for importable files
|       |   |-- import_file.py   # NEW: auto-import JSON/CSV/Parquet as tables
|       |   |-- describe_data.py # NEW: table summary stats
|       |   |-- execute_query.py # upstream: raw SQL execution
|       |   |-- list_tables.py   # upstream: catalog browsing
|       |   |-- list_columns.py  # upstream: column info
|       |   `-- list_databases.py
|       |-- database.py          # DuckDB connection management
|       |-- server.py            # FastMCP server setup
|       `-- instructions.py      # LLM instructions sent on init
|-- mcpo/
|   |-- Dockerfile               # MCPO image + mcp-server-motherduck installed from source
|   `-- config.json              # MCPO -> MCP server config
|-- data/                        # Shared volume: put your data files here
`-- SETUP.md                     # This file
```

## Quick Start

### 1. Start the stack

```bash
cd duckdb-openwebui
docker compose up -d
```

Wait for all services:

```bash
docker compose logs -f
# Wait for "Open WebUI is running" and MCPO "Application startup complete"
```

### 2. Pull an LLM model

Best models for tool calling:

```bash
# 8 GB VRAM — DuckDB specialist
docker exec -it ollama ollama pull duckdb-nsql:7b

# 10 GB VRAM — best all-rounder
docker exec -it ollama ollama pull qwen3:8b

# 24 GB VRAM — best quality
docker exec -it ollama ollama pull qwen3:32b
```

### 3. Open the UI

Open http://localhost:3000 in your browser.
Create an admin account on first launch.

### 4. Configure the LLM for tool calling

1. **Admin Panel** -> **Settings** -> **Models**
2. Select your model -> **Advanced Parameters**
3. **Function Calling** -> set to **"Native"**

This is critical. Without Native mode, tool calling is unreliable.

### 5. Connect MCPO as a Tool provider

1. **Admin Panel** -> **Settings** -> **Tools**
2. Click **+** (Add Connection)
3. Enter URL: `http://mcpo:8000`
4. Click **Save**
5. You should see the DuckDB tools appear

### 6. Enable tools in chat

1. Open a new chat
2. Click **+** next to the message input
3. Toggle ON the **duckdb** tools
4. Now the LLM can call all 7 MCP tools

## Usage

### Put data files in the shared volume

```bash
# JSON (key-value objects, arrays, JSONL)
cp acl_users.json ./data/

# CSV
cp users_export.csv ./data/

# Parquet
cp analytics.parquet ./data/
```

### Ask the LLM to analyze

The LLM will use the tools automatically. Example prompts:

```
What files are available for analysis?
```

```
Import acl_users.json and show me the structure.
```

```
Find all users with access to the 192.168.1.0/24 subnet.
```

```
Group users that share identical access routes.
```

### How JSON import works

JSON key-value objects like:
```json
{"user1": {"access_to.0": "+ROUTE:10.20.1.45/32:tcp/80"}, "user2": {...}}
```

Are automatically flattened into rows:

| entity_key | entity_value |
|------------|-------------|
| user1 | {"access_to.0": "+ROUTE:10.20.1.45/32:tcp/80", ...} |
| user2 | {"access_to.0": "...", ...} |

The LLM can then query nested JSON fields with DuckDB syntax:
```sql
SELECT entity_key, entity_value->>'type' as user_type FROM acl_users;
```

## Configuration

### MCP server options

Edit `mcpo/config.json`:

```json
{
  "mcpServers": {
    "duckdb": {
      "command": "mcp-server-motherduck",
      "args": [
        "--db-path", "/data/analytics.duckdb",
        "--read-write",
        "--data-dir", "/data",
        "--max-rows", "2048",
        "--max-chars", "100000",
        "--query-timeout", "120"
      ]
    }
  }
}
```

| Flag | Default | Description |
|------|---------|-------------|
| `--db-path` | `:memory:` | DuckDB file path. Use a file for persistence across restarts |
| `--read-write` | off (read-only) | Required for import_file to create tables |
| `--data-dir` | none | Directory for data files. Enables list_files and import_file tools |
| `--max-rows` | 1024 | Max rows returned per query |
| `--max-chars` | 50000 | Max characters in query results |
| `--query-timeout` | -1 (disabled) | Query timeout in seconds |

### Use a different LLM backend (not Ollama)

Edit `docker-compose.yml`, in the `open-webui` service:

```yaml
environment:
  # Comment out Ollama:
  # - OLLAMA_BASE_URL=http://ollama:11434

  # Use OpenAI-compatible API:
  - OPENAI_API_BASE_URL=http://your-vllm-server:8000/v1
  - OPENAI_API_KEY=your-api-key
```

### Enable GPU for Ollama

Uncomment the `deploy` section in the `ollama` service in `docker-compose.yml`.

### Add more MCP servers

Edit `mcpo/config.json`:

```json
{
  "mcpServers": {
    "duckdb": {
      "command": "mcp-server-motherduck",
      "args": ["--db-path", "/data/analytics.duckdb", "--read-write", "--data-dir", "/data"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

Then restart:

```bash
docker compose restart mcpo
```

## Testing without Open WebUI

You can test the MCP server directly with curl:

```bash
# Build and run the MCP server alone
docker build -f test/Dockerfile -t mcp-duckdb-test .
docker run -d --name mcp-test -p 8080:8080 -v ./data:/data mcp-duckdb-test

# Initialize session
SESSION_ID=$(curl -si -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | grep -i 'mcp-session-id' | awk '{print $2}' | tr -d '\r')

# Call a tool
curl -s -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_files","arguments":{}}}'

# Clean up
docker rm -f mcp-test
```

## Troubleshooting

### MCPO tools don't appear in Open WebUI

1. Check MCPO is running: `curl http://localhost:8000/docs`
2. Check logs: `docker compose logs mcpo`
3. In Open WebUI, the URL must be `http://mcpo:8000` (Docker network), not `localhost`

### import_file returns wrong shape for JSON

If a JSON file imports as 1 row with many columns, it means DuckDB read it as a
flat object. The import_file tool automatically detects this and falls back to
row-based import using `json_each`. If this still fails, use `execute_query` directly:

```sql
SELECT j.key, j.value
FROM read_text('/data/your_file.json') t,
LATERAL json_each(t.content::JSON) j
```

### LLM doesn't use the tools

- Enable **Native** function calling mode (Admin -> Settings -> Models -> Advanced)
- Best models for tool use: `qwen3:8b`, `qwen3:32b`, `duckdb-nsql:7b`
- Make sure tools are toggled ON in the chat (click + next to input)

### DuckDB can't read files

1. Verify file is in `./data/` on host: `ls -la ./data/`
2. Check inside container: `docker exec mcpo ls /data/`
3. All file paths must use `/data/` prefix (container mount point)

### Out of memory

- Reduce model size: use `qwen3:8b` instead of larger models
- Set DuckDB memory limit: use `execute_query` with `SET memory_limit='2GB';`
- Increase Docker memory in Docker Desktop settings
