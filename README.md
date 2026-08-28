# XLSX Application Grader

Desktop and browser app for scoring rows in an Excel workbook. You open an `.xlsx` file, grade one applicant row at a time, and write scores into `Grade for: …` columns plus `Sum of All Grades`. The original workbook is never overwritten. Grades go to a proxy copy.

The UI is a static web page (`static/index.html`). SheetJS (`static/vendor/xlsx.full.min.js`) reads and writes the workbook in the browser. Python only hosts the UI, file dialogs, and on-disk storage.

End-user steps are in [static/user-manual.html](static/user-manual.html).

## Ways to run it

| Mode | Entry point | UI | Where grades and configs live |
| --- | --- | --- | --- |
| Native Windows app | `app_native.py` or `xlsx_application_grader.exe` | Edge WebView2 window | `%APPDATA%\xlsx_application_grader\` |
| Local web server | `server.py` or `xlsx_application_grader_web.exe` | Default browser at `http://127.0.0.1:8765/` | Same AppData folder, under `web_configs` |
| Hosted website | Deploy the `static/` folder | Browser on any non-localhost HTTP(S) host | This browser only (IndexedDB). Nothing is uploaded. |

Native and local-web configs are stored separately (`native_configs` vs `web_configs`). Theme is shared in `user_config.json`.

The hosted mode is detected in the page: localhost HTTP(S) uses the Python API; any other HTTP(S) host uses IndexedDB.

## Run from source

Needs Python 3 on Windows.

```bash
pip install -r requirements.txt
```

Native window (WebView2 / Edge Chromium):

```bash
python app_native.py
```

Local server (opens the default browser unless `--no-browser`):

```bash
python server.py
```

Useful `server.py` flags:

- `--port N` bind that port (default is 8765, or the next free port)
- `--no-browser` do not open a tab
- `--debug` show a console and server logs

If a grader server is already running, a new launch reuses it and opens another tab. When every tab disconnects, the server stops after about 10 seconds.

User manual while the server is up: `http://127.0.0.1:8765/user-manual.html`.

## Build Windows EXEs

```bash
build.bat
```

or:

```powershell
.\build.ps1
```

Output:

- `dist\xlsx_application_grader.exe` native desktop window
- `dist\xlsx_application_grader_web.exe` local web server

Close any running grader window or server before rebuilding. The build cannot overwrite a locked EXE.

## Project layout

| Path | Role |
| --- | --- |
| `static/index.html` | Grader UI and all spreadsheet logic |
| `static/user-manual.html` | End-user manual |
| `static/vendor/xlsx.full.min.js` | SheetJS workbook parser |
| `app_native.py` | pywebview desktop shell |
| `server.py` | Local static server and `/api/*` routes |
| `grader_http.py` | HTTP handlers, file API, lifecycle WebSocket |
| `grader_app_api.py` | Shared filesystem and config API |
| `grader_paths.py` | AppData paths and proxy file names |
| `grader_lifecycle.py` | Tab tracking and auto-shutdown |
| `grader_file_dialogs.py` | Windows open/save dialogs (PowerShell) |
| `xlsx_application_grader.spec` | PyInstaller spec for the native EXE |
| `xlsx_application_grader_web.spec` | PyInstaller spec for the web EXE |

## Data on disk (Windows EXEs)

Root: `%APPDATA%\xlsx_application_grader\`

| Item | Path |
| --- | --- |
| Grade proxy | `Grades for - {workbook stem}.xlsx` |
| Native configs | `native_configs\{workbook key}.json` |
| Web configs | `web_configs\{workbook key}.json` |
| Open-file session | `native_configs/app_state.json` or `web_configs/app_state.json` |
| Theme | `user_config.json` |
| Local web session | `web_session.json` |

If the proxy for that workbook name already exists, the app reopens it instead of copying again.

On the hosted website the same names are keys in IndexedDB (`xlsx_application_grader`). Clearing site data removes grades and configs. There is no cross-device sync.

## Grading behavior

- Row 1 is headers. Data starts at row 2.
- Checking **Grade** on a column creates score inputs. **Submit all** writes `Grade for: {header}` and updates `Sum of All Grades`.
- Empty grade fields are skipped. Non-numeric values are rejected.
- **Copy grades** copies tab-separated grade columns (and the sum column when it has data) for paste into Excel.
- Layout, graded/hidden columns, current row, and auto-advance are stored per workbook in a named config (default name `default`). **New Config** is the last item in **Active Config**.
