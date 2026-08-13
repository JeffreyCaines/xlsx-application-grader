"""Shared paths for bundled static assets."""

import os
import re
import sys

CONFIG_PLATFORM_NATIVE = "native"
CONFIG_PLATFORM_WEB = "web"


def bundle_dir() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def static_dir() -> str:
    return os.path.join(bundle_dir(), "static")


def index_html_path() -> str:
    return os.path.join(static_dir(), "index.html")


def sanitize_config_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(name))[:120]


def appdata_root() -> str:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(appdata, "xlsx_application_grader")
    return os.path.join(os.path.expanduser("~"), ".xlsx_application_grader")


def appdata_config_dir(platform: str = CONFIG_PLATFORM_WEB) -> str:
    subdir = "native_configs" if platform == CONFIG_PLATFORM_NATIVE else "web_configs"
    return os.path.join(appdata_root(), subdir)


def config_bundle_path(workbook_key: str, platform: str = CONFIG_PLATFORM_WEB) -> str:
    safe_key = sanitize_config_key(workbook_key)
    return os.path.join(appdata_config_dir(platform), f"{safe_key}.json")


def app_state_path(platform: str = CONFIG_PLATFORM_WEB) -> str:
    return os.path.join(appdata_config_dir(platform), "app_state.json")


def user_config_path() -> str:
    return os.path.join(appdata_root(), "user_config.json")


def web_session_path() -> str:
    return os.path.join(appdata_root(), "web_session.json")


def grade_proxy_path(original_name: str) -> str:
    base = os.path.basename(str(original_name or "")).strip()
    stem = os.path.splitext(base)[0] or "workbook"
    return os.path.join(appdata_root(), f"Grades for - {stem}.xlsx")
