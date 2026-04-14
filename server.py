import asyncio
import os
import sys
import time

import asyncssh
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mikrotik-cli")

_conn: asyncssh.SSHClientConnection | None = None
_conn_lock = asyncio.Lock()


def escape_non_ascii(text: str) -> str:
    """Convert non-ASCII characters to RouterOS hex escape format (\\XX)."""
    result = []
    for char in text:
        if ord(char) > 127:
            for byte in char.encode("utf-8"):
                result.append(f"\\{byte:02X}")
        else:
            result.append(char)
    return "".join(result)


def get_config():
    host = os.environ.get("MIKROTIK_HOST")
    user = os.environ.get("MIKROTIK_USER")
    password = os.environ.get("MIKROTIK_PASSWORD")
    port = int(os.environ.get("MIKROTIK_PORT", "22"))

    if not host or not user or not password:
        missing = [k for k, v in {
            "MIKROTIK_HOST": host,
            "MIKROTIK_USER": user,
            "MIKROTIK_PASSWORD": password,
        }.items() if not v]
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return host, port, user, password


async def _get_conn() -> asyncssh.SSHClientConnection:
    global _conn
    if _conn is not None:
        return _conn
    async with _conn_lock:
        if _conn is not None:
            return _conn
        host, port, user, password = get_config()
        _conn = await asyncssh.connect(
            host,
            port=port,
            username=user,
            password=password,
            known_hosts=None,
        )
        return _conn


async def _close_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.close()
            await _conn.wait_closed()
        except Exception:
            pass
        _conn = None


async def _run_command(command: str) -> str:
    conn = await _get_conn()
    result = await asyncio.wait_for(conn.run(command), timeout=60)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return f"{stdout}\n[stderr]\n{stderr}".strip() if stderr else stdout.strip()


@mcp.tool()
async def cli(command: str) -> str:
    """Send a CLI command to MikroTik RouterOS via SSH and return the output.

    Note: If execution takes 1 second or longer, elapsed time is appended to the output. `[Elapsed: 3.xx s]`

    Args:
        command: RouterOS CLI command to execute (e.g. "/system/identity/print terse", "/ip/address/print")
            Always append `terse` to print commands to avoid empty output (e.g. "/interface/print terse")
    """
    command = escape_non_ascii(command)

    start = time.perf_counter()
    try:
        try:
            output = await _run_command(command)
        except (asyncssh.Error, OSError, TimeoutError):
            await _close_conn()
            output = await _run_command(command)
    except asyncssh.Error as e:
        output = f"SSH error: {e}"
    except OSError as e:
        output = f"Connection error: {e}"
    except TimeoutError:
        output = f"Timeout: command did not complete within 60s"

    elapsed = time.perf_counter() - start
    if elapsed >= 1.0:
        output += f"\n\n[Elapsed: {elapsed:.2f}s]"
    return output


if __name__ == "__main__":
    mcp.run(transport="stdio")
