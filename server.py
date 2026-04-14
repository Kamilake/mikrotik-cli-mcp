import os
import sys

import asyncssh
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mikrotik-cli")


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


@mcp.tool()
async def cli(command: str) -> str:
    """Send a CLI command to MikroTik RouterOS via SSH and return the output.

    Args:
        command: RouterOS CLI command to execute (e.g. "/system/identity/print", "/ip/address/print")
    """
    host, port, user, password = get_config()
    command = escape_non_ascii(command)

    try:
        async with asyncssh.connect(
            host,
            port=port,
            username=user,
            password=password,
            known_hosts=None,
        ) as conn:
            result = await conn.run(command)
            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if stderr:
                return f"{stdout}\n[stderr]\n{stderr}".strip()
            return stdout.strip()
    except asyncssh.Error as e:
        return f"SSH error: {e}"
    except OSError as e:
        return f"Connection error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
