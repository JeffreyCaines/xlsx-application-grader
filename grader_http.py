"""Local HTTP server for serving the static XLSX Grader UI."""

import http.server
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional, Tuple

from grader_app_api import GraderAppApi
from grader_lifecycle import (
    DEFAULT_WEB_PORT,
    SessionLifecycleTracker,
    load_or_create_session_token,
    load_web_session,
    make_ws_accept,
    read_websocket_until_close,
    save_web_session,
)
from grader_paths import static_dir

_app_api = GraderAppApi()


def _query_param(params: dict, key: str, default: str = "") -> str:
    values = params.get(key, [default])
    raw = values[0] if values else default
    return urllib.parse.unquote(raw, encoding="utf-8", errors="surrogateescape")


def find_free_port(start: int = DEFAULT_WEB_PORT, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{start + attempts - 1}")


def resolve_bind_port(port: Optional[int]) -> int:
    if port is not None:
        return find_free_port(start=port, attempts=1)
    session = load_web_session()
    preferred = session.get("port", DEFAULT_WEB_PORT) if session else DEFAULT_WEB_PORT
    return find_free_port(start=preferred, attempts=20)


def probe_grader_server(port: int) -> Optional[Tuple[str, str]]:
    """Return (base_url, token) if a grader server is listening on port."""
    try:
        status_url = f"http://127.0.0.1:{port}/api/lifecycle/status"
        with urllib.request.urlopen(status_url, timeout=1) as response:
            data = json.loads(response.read().decode("utf-8"))
        token = data.get("token")
        if not token:
            return None
        return f"http://127.0.0.1:{port}/", token
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError, ValueError):
        return None


def find_running_grader_server(port: Optional[int] = None) -> Optional[Tuple[str, str]]:
    """Return (base_url, token) if an existing grader web server is already running."""
    session = load_web_session()
    ports_to_try: list[int] = []
    if port is not None:
        ports_to_try.append(port)
    if session and session.get("port"):
        session_port = session["port"]
        if session_port not in ports_to_try:
            ports_to_try.append(session_port)
    if not ports_to_try:
        ports_to_try.append(DEFAULT_WEB_PORT)

    expected_token = session.get("token") if session else None
    for candidate_port in ports_to_try:
        match = probe_grader_server(candidate_port)
        if not match:
            continue
        url, token = match
        if expected_token and token != expected_token:
            continue
        return url, token
    return None


class GraderHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    # WebSocket upgrades require HTTP/1.1. Firefox drops HTTP/1.0 101 responses.
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:
        if getattr(self.server, "debug", False):
            super().log_message(format, *args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/lifecycle/status":
            self._handle_lifecycle_status()
            return
        if path == "/ws/lifecycle":
            self._handle_ws_lifecycle(parsed)
            return
        if path == "/api/config-bundles":
            self._send_json(_app_api.list_config_bundles())
            return
        if path == "/api/app-state":
            raw = _app_api.read_app_state()
            self._send_text(raw if raw is not None else "{}")
            return
        if path == "/api/user-config":
            raw = _app_api.read_user_config()
            self._send_text(raw if raw is not None else "{}")
            return
        if path == "/api/file/exists":
            params = urllib.parse.parse_qs(parsed.query, encoding="utf-8")
            file_path = _query_param(params, "path")
            self._send_json({"exists": _app_api.file_exists(file_path)})
            return
        if path == "/api/proxy-path":
            params = urllib.parse.parse_qs(parsed.query, encoding="utf-8")
            original_name = _query_param(params, "name")
            self._send_json({"path": _app_api.grade_proxy_path(original_name)})
            return
        if path == "/api/file/bytes":
            params = urllib.parse.parse_qs(parsed.query, encoding="utf-8")
            file_path = _query_param(params, "path")
            try:
                content_b64 = _app_api.read_file_bytes(file_path)
                self._send_json({"content_b64": content_b64})
            except OSError:
                self.send_error(404)
            return
        if path.startswith("/api/config-bundle/"):
            workbook_key = urllib.parse.unquote(path.split("/api/config-bundle/", 1)[1])
            raw = _app_api.read_config_bundle(workbook_key)
            if raw is None:
                self.send_error(404)
                return
            self._send_text(raw)
            return
        super().do_GET()

    def do_PUT(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body_text()
        if path == "/api/app-state":
            _app_api.write_app_state(body)
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/user-config":
            _app_api.write_user_config(body)
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/file/bytes":
            try:
                payload = json.loads(body)
                _app_api.write_file_bytes(payload["path"], payload["content_b64"])
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except (KeyError, json.JSONDecodeError, OSError):
                self.send_error(400)
            return
        if path.startswith("/api/config-bundle/"):
            workbook_key = urllib.parse.unquote(path.split("/api/config-bundle/", 1)[1])
            _app_api.write_config_bundle(workbook_key, body)
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_body_text()
        if path == "/api/files/open":
            self._send_json({"paths": _app_api.open_xlsx_files()})
            return
        if path == "/api/config/save-file":
            try:
                payload = json.loads(body)
                saved = _app_api.save_config_file(payload["suggested_name"], payload["content"])
                self._send_json({"saved": saved})
            except (KeyError, json.JSONDecodeError, TypeError):
                self.send_error(400)
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/config-bundle/"):
            workbook_key = urllib.parse.unquote(path.split("/api/config-bundle/", 1)[1])
            deleted = _app_api.delete_config_bundle(workbook_key)
            if not deleted:
                self.send_error(404)
                return
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_error(404)

    def _read_body_text(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return ""
        return self.rfile.read(length).decode("utf-8")

    def _send_json(self, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_lifecycle_status(self) -> None:
        tracker = getattr(self.server, "lifecycle_tracker", None)
        payload = {
            "token": tracker.launch_token if tracker else "",
            "connections": tracker.connection_count() if tracker else 0,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ws_lifecycle(self, parsed: urllib.parse.ParseResult) -> None:
        tracker = getattr(self.server, "lifecycle_tracker", None)
        if tracker is None:
            self.send_error(503)
            return

        params = urllib.parse.parse_qs(parsed.query)
        token = params.get("token", [""])[0]
        role = params.get("role", ["unknown"])[0]
        if not token or token != tracker.launch_token:
            self.send_error(403)
            return

        if self.headers.get("Upgrade", "").lower() != "websocket":
            self.send_error(400, "Expected WebSocket upgrade")
            return

        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "Missing Sec-WebSocket-Key")
            return

        accept = make_ws_accept(key)
        self.close_connection = True
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        try:
            self.wfile.flush()
        except OSError:
            return

        tracker.on_connect()
        if getattr(self.server, "debug", False):
            print(
                f"WebSocket tab connected (role={role}, connections={tracker.connection_count()})"
            )
        try:
            read_websocket_until_close(self.connection)
        finally:
            tracker.on_disconnect()
            if getattr(self.server, "debug", False):
                print(
                    f"WebSocket tab disconnected (role={role}, connections={tracker.connection_count()})"
                )


def create_http_server(
    port: Optional[int] = None,
    launch_token: Optional[str] = None,
    debug: bool = False,
) -> Tuple[http.server.ThreadingHTTPServer, str, str]:
    root = static_dir()
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Static directory not found at {root}")

    chosen_port = resolve_bind_port(port)
    url = f"http://127.0.0.1:{chosen_port}/"
    token = launch_token or load_or_create_session_token()

    handler = lambda *h_args, directory=root, **kwargs: GraderHTTPRequestHandler(
        *h_args, directory=directory, **kwargs
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", chosen_port), handler)
    server.debug = debug
    tracker = SessionLifecycleTracker(server.shutdown, grace_seconds=10.0)
    tracker.set_launch_token(token)
    server.lifecycle_tracker = tracker
    save_web_session(chosen_port, token)
    return server, url, token
