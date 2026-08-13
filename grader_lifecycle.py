"""Web session lifecycle tracking for the local web server."""

import base64
import hashlib
import json
import os
import secrets
import struct
import threading
from typing import Callable, Optional

from grader_paths import web_session_path

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_WEB_PORT = 8765


def generate_launch_token() -> str:
    return secrets.token_urlsafe(16)


def load_web_session() -> Optional[dict]:
    path = web_session_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def save_web_session(port: int, token: str) -> None:
    path = web_session_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"port": port, "token": token, "pid": os.getpid()}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


def load_or_create_session_token() -> str:
    session = load_web_session()
    if session and session.get("token"):
        return session["token"]
    return generate_launch_token()


def make_ws_accept(key: str) -> str:
    digest = hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _recv_exact(conn, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        chunk = conn.recv(size - len(buf))
        if not chunk:
            return bytes(buf)
        buf.extend(chunk)
    return bytes(buf)


def _send_ws_pong(conn, payload: bytes) -> None:
    length = len(payload)
    if length < 126:
        header = bytes([0x8A, length])
    elif length < 65536:
        header = bytes([0x8A, 126]) + struct.pack(">H", length)
    else:
        header = bytes([0x8A, 127]) + struct.pack(">Q", length)
    conn.sendall(header + payload)


def read_websocket_until_close(conn) -> None:
    """Read WebSocket frames until the client closes or the socket fails."""
    while True:
        try:
            header = _recv_exact(conn, 2)
            if len(header) < 2:
                break
            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F
            if length == 126:
                ext = _recv_exact(conn, 2)
                if len(ext) < 2:
                    break
                length = struct.unpack(">H", ext)[0]
            elif length == 127:
                ext = _recv_exact(conn, 8)
                if len(ext) < 8:
                    break
                length = struct.unpack(">Q", ext)[0]
            mask = b""
            if masked:
                mask = _recv_exact(conn, 4)
                if len(mask) < 4:
                    break
            data = _recv_exact(conn, length) if length else b""
            if len(data) < length:
                break
            if masked and data:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                break
            if opcode == 0x9:
                _send_ws_pong(conn, data)
                continue
            if opcode == 0xA:
                continue
        except OSError:
            break


class SessionLifecycleTracker:
    """Tracks browser tabs; shuts down after all tabs stay disconnected."""

    def __init__(self, shutdown_fn: Callable[[], None], grace_seconds: float = 10.0) -> None:
        self._shutdown_fn = shutdown_fn
        self._grace_seconds = grace_seconds
        self._lock = threading.Lock()
        self._connection_count = 0
        self._timer: Optional[threading.Timer] = None
        self.launch_token: str = ""

    def set_launch_token(self, token: str) -> None:
        self.launch_token = token

    def on_connect(self) -> None:
        with self._lock:
            self._connection_count += 1
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def on_disconnect(self) -> None:
        with self._lock:
            self._connection_count = max(0, self._connection_count - 1)
            if self._connection_count == 0:
                self._timer = threading.Timer(self._grace_seconds, self._shutdown_if_still_disconnected)
                self._timer.daemon = True
                self._timer.start()

    def has_connections(self) -> bool:
        with self._lock:
            return self._connection_count > 0

    def connection_count(self) -> int:
        with self._lock:
            return self._connection_count

    def _shutdown_if_still_disconnected(self) -> None:
        with self._lock:
            if self._connection_count > 0:
                return
        self._shutdown_fn()
