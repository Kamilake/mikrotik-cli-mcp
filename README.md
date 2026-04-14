# mikrotik-cli-mcp

MCP server that sends CLI commands to MikroTik RouterOS via SSH.

Single tool: `cli` — send any RouterOS CLI command and get the text output back.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `MIKROTIK_HOST` | Yes | — | RouterOS IP address or hostname |
| `MIKROTIK_USER` | Yes | — | SSH username |
| `MIKROTIK_PASSWORD` | Yes | — | SSH password |
| `MIKROTIK_PORT` | No | `22` | SSH port |

## Usage with Claude Desktop / VS Code

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "mikrotik": {
      "command": "docker",
      "args": ["run", "-i", "--rm",
        "-e", "MIKROTIK_HOST=10.1.25.40",
        "-e", "MIKROTIK_USER=admin",
        "-e", "MIKROTIK_PASSWORD=yourpassword",
        "kamilake/mikrotik-cli-mcp"
      ]
    }
  }
}
```

## Build from Source

### Docker

```bash
docker build -t mikrotik-cli-mcp .
```

### Without Docker

```bash
uv run server.py
```

## Example

Tool call: `cli(command="/system/identity/print")`

Response:
```
name: MikroTik
```
