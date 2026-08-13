"""Open URLs in the system default browser."""

import webbrowser


def open_default_browser(url: str) -> None:
    webbrowser.open(url)
