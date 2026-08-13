"""PowerShell subprocess helpers (Windows). Dialog output is base64 UTF-8 on stdout."""

import base64
import subprocess
import sys


def run_powershell_bytes(script: str) -> bytes:
    if sys.platform != "win32":
        return b""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Sta", "-Command", script],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        return b""
    return result.stdout


def run_powershell_utf8_text(script: str) -> str:
    """Decode stdout from a script that emits UTF-8 text as base64."""
    raw = run_powershell_bytes(script)
    if not raw:
        return ""
    ascii_out = raw.decode("ascii", errors="ignore").strip()
    if not ascii_out:
        return ""
    return base64.b64decode(ascii_out).decode("utf-8")
