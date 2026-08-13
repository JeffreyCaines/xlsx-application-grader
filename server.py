#!/usr/bin/env python3
"""Local static server for the XLSX Grader web app."""

import argparse
import os
import sys
import threading
import time

from grader_browser import open_default_browser
from grader_http import create_http_server, find_running_grader_server


def configure_console(debug: bool) -> None:
    if debug:
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.AllocConsole()
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        return

    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")


def wait_for_tab_connections(server, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    tracker = server.lifecycle_tracker
    while time.monotonic() < deadline:
        if tracker.has_connections():
            return True
        time.sleep(0.1)
    return tracker.has_connections()


def main() -> None:
    parser = argparse.ArgumentParser(description="XLSX Grader local web server")
    parser.add_argument("--port", type=int, default=None, help="Port to bind (default: 8765 or next free)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    parser.add_argument("--debug", action="store_true", help="Show a console and print server logs")
    args = parser.parse_args()

    configure_console(args.debug)

    existing = find_running_grader_server(args.port)
    if existing:
        url, _token = existing
        if args.debug:
            print(f"Grader server already running at {url}")
            print("Opening a new browser tab.")
        if not args.no_browser:
            open_default_browser(url)
        return

    try:
        server, url, launch_token = create_http_server(args.port, debug=args.debug)
    except FileNotFoundError as exc:
        if args.debug:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        if args.debug:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.debug:
        print(f"Serving XLSX Grader at {url}")
        print("Press Ctrl+C to stop.")

    if not args.no_browser:
        def maybe_open_browser() -> None:
            if wait_for_tab_connections(server, 2.0):
                if args.debug:
                    print("Reusing existing browser tab.")
                return
            open_default_browser(f"{url}?launcher={launch_token}")

        threading.Timer(0.5, maybe_open_browser).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if args.debug:
            print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
