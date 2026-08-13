"""Native file dialogs for the web server process (Windows)."""

import json
import sys
from pathlib import Path
from typing import List, Optional

from grader_powershell import run_powershell_utf8_text

_B64_OUT = (
    "$b = [System.Text.Encoding]::UTF8.GetBytes($out); "
    "Write-Output ([Convert]::ToBase64String($b))"
)


def open_xlsx_files_dialog() -> List[str]:
    if sys.platform != "win32":
        return []
    script = rf"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Filter = 'Excel files (*.xlsx)|*.xlsx|All files (*.*)|*.*'
$d.Multiselect = $true
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  $out = $d.FileNames | ConvertTo-Json -Compress
  {_B64_OUT}
}}
"""
    output = run_powershell_utf8_text(script)
    if not output:
        return []
    try:
        parsed = json.loads(output)
        if isinstance(parsed, list):
            return [str(p) for p in parsed if p]
        if isinstance(parsed, str) and parsed:
            return [parsed]
    except json.JSONDecodeError:
        pass
    return []


def save_json_file(suggested_name: str, content: str) -> Optional[str]:
    if sys.platform != "win32":
        return None
    safe_name = suggested_name.replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.SaveFileDialog
$d.Filter = 'JSON files (*.json)|*.json|All files (*.*)|*.*'
$d.FileName = '{safe_name}'
if ($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {{
  $out = $d.FileName
  {_B64_OUT}
}}
"""
    path = run_powershell_utf8_text(script)
    if not path:
        return None
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.write(content)
    return path
