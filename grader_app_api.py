"""Shared filesystem and config API for native and web server shells."""

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from grader_file_dialogs import save_json_file, open_xlsx_files_dialog
from grader_paths import (
    CONFIG_PLATFORM_WEB,
    app_state_path,
    appdata_config_dir,
    appdata_root,
    config_bundle_path,
    grade_proxy_path,
    user_config_path,
)


def system_prefers_dark() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except OSError:
            pass
    elif sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return result.stdout.strip().lower() == "dark"
        except (OSError, subprocess.SubprocessError):
            pass
    return False


class GraderAppApi:
    def __init__(self, platform: str = CONFIG_PLATFORM_WEB) -> None:
        self._platform = platform

    def save_config_file(self, suggested_name: str, content: str) -> bool:
        path = save_json_file(suggested_name, content)
        return bool(path)

    def read_config_bundle(self, workbook_key: str):
        path = config_bundle_path(workbook_key, self._platform)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def write_config_bundle(self, workbook_key: str, content: str) -> bool:
        os.makedirs(appdata_config_dir(self._platform), exist_ok=True)
        path = config_bundle_path(workbook_key, self._platform)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return True

    def list_config_bundles(self):
        config_dir = appdata_config_dir(self._platform)
        if not os.path.isdir(config_dir):
            return []

        items = []
        for name in sorted(os.listdir(config_dir)):
            if not name.endswith(".json") or name == "app_state.json":
                continue
            workbook_key = name[:-5]
            path = os.path.join(config_dir, name)
            config_names = []
            parsed = None
            try:
                with open(path, encoding="utf-8") as handle:
                    parsed = json.load(handle)
                configs = parsed.get("configs") if isinstance(parsed, dict) else None
                if isinstance(configs, dict):
                    config_names = sorted(configs.keys())
            except (OSError, json.JSONDecodeError, TypeError):
                pass
            items.append({
                "workbook_key": workbook_key,
                "file_path": path,
                "filename": name,
                "config_names": config_names,
            })
        return items

    def delete_config_bundle(self, workbook_key: str) -> bool:
        path = config_bundle_path(workbook_key, self._platform)
        if not os.path.isfile(path):
            return False
        os.remove(path)
        return True

    def read_app_state(self):
        path = app_state_path(self._platform)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def write_app_state(self, content: str) -> bool:
        os.makedirs(appdata_config_dir(self._platform), exist_ok=True)
        with open(app_state_path(self._platform), "w", encoding="utf-8") as handle:
            handle.write(content)
        return True

    def read_user_config(self):
        path = user_config_path()
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def write_user_config(self, content: str) -> bool:
        os.makedirs(appdata_root(), exist_ok=True)
        with open(user_config_path(), "w", encoding="utf-8") as handle:
            handle.write(content)
        return True

    def file_exists(self, path: str) -> bool:
        return bool(path) and Path(path).is_file()

    def grade_proxy_path(self, original_name: str) -> str:
        return grade_proxy_path(original_name)

    def open_xlsx_files(self):
        return open_xlsx_files_dialog()

    def read_file_bytes(self, path: str) -> str:
        with Path(path).open("rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")

    def write_file_bytes(self, path: str, content_b64: str) -> bool:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as handle:
            handle.write(base64.b64decode(content_b64))
        return True
