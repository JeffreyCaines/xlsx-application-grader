#!/usr/bin/env python3
"""Native desktop shell for the XLSX Grader web app."""

import os
import sys

import webview

from grader_app_api import GraderAppApi, system_prefers_dark
from grader_paths import CONFIG_PLATFORM_NATIVE, index_html_path, static_dir


class NativeAppApi(GraderAppApi):
    def __init__(self) -> None:
        super().__init__(platform=CONFIG_PLATFORM_NATIVE)

    def system_prefers_dark(self) -> bool:
        return system_prefers_dark()


def main() -> None:
    root = static_dir()
    index = index_html_path()
    if not os.path.isdir(root):
        print(f"Error: static directory not found at {root}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(index):
        print(f"Error: UI not found at {index}", file=sys.stderr)
        sys.exit(1)

    webview.create_window(
        "XLSX Grader",
        index,
        width=1400,
        height=900,
        min_size=(960, 640),
        js_api=NativeAppApi(),
    )
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    main()
