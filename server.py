import os
import re
import shlex
import sys

import asyncssh
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mikrotik-cli")


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


def _apply_grep(text: str, grep_args: str) -> str:
    """Apply grep-like filtering to text. Supports -i (ignore case) and -v (invert)."""
    parts = shlex.split(grep_args)
    invert = False
    ignore_case = False
    pattern = None

    i = 0
    while i < len(parts):
        if parts[i] == "-v":
            invert = True
        elif parts[i] == "-i":
            ignore_case = True
        elif parts[i] == "-iv" or parts[i] == "-vi":
            invert = True
            ignore_case = True
        else:
            pattern = parts[i]
            break
        i += 1

    if pattern is None:
        return text

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        regex = re.compile(re.escape(pattern), flags)

    lines = text.splitlines()
    filtered = [l for l in lines if (not regex.search(l)) == invert]
    return "\n".join(filtered)


def _parse_pipeline(command: str) -> tuple[str, list[str]]:
    """Split 'command | grep pattern | grep pattern2' into (command, [grep_args, ...])."""
    parts = command.split("|")
    base = parts[0].strip()
    greps = []
    for part in parts[1:]:
        stripped = part.strip()
        if stripped.lower().startswith("grep "):
            greps.append(stripped[5:])
        elif stripped.lower() == "grep":
            continue
        else:
            # Not a grep pipe — treat as part of the base command
            base += " | " + stripped
    return base, greps


def _split_commands(command: str) -> list[tuple[str, str]]:
    """Split on && and ; operators. Returns [(command, operator)] where operator is '&&', ';', or ''."""
    tokens = re.split(r'(&&|;)', command)
    result = []
    for i in range(0, len(tokens), 2):
        cmd = tokens[i].strip()
        op = tokens[i + 1].strip() if i + 1 < len(tokens) else ""
        if cmd:
            result.append((cmd, op))
    return result


async def _run_one(conn: asyncssh.SSHClientConnection, command: str) -> tuple[str, bool]:
    """Run a single command (with optional | grep pipes). Returns (output, success)."""
    base, greps = _parse_pipeline(command)
    result = await conn.run(base)
    stdout = result.stdout or ""
    stderr = result.stderr or ""

    if stderr:
        output = f"{stdout}\n[stderr]\n{stderr}".strip()
        return output, False

    output = stdout.strip()
    for grep_args in greps:
        output = _apply_grep(output, grep_args)
    return output, True


@mcp.tool()
async def cli(command: str) -> str:
    """Send a CLI command to MikroTik RouterOS via SSH and return the output.

    Supports shell-like operators that are parsed locally:
      - `;`  — run commands sequentially (always continues)
      - `&&` — run next command only if the previous one succeeded
      - `| grep <pattern>` — filter output lines (supports -i, -v flags)

    Examples:
        /system/identity/print
        /ip/address/print | grep ether1
        /interface/print ; /ip/address/print
        /system/resource/print && /ip/route/print | grep -i dst

    Args:
        command: RouterOS CLI command(s) to execute
    """
    host, port, user, password = get_config()

    try:
        async with asyncssh.connect(
            host,
            port=port,
            username=user,
            password=password,
            known_hosts=None,
        ) as conn:
            commands = _split_commands(command)
            outputs = []

            for cmd, op in commands:
                output, success = await _run_one(conn, cmd)
                outputs.append(output)
                if op == "&&" and not success:
                    break

            return "\n".join(outputs)
    except asyncssh.Error as e:
        return f"SSH error: {e}"
    except OSError as e:
        return f"Connection error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
