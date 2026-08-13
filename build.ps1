$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# UPX compression often hangs indefinitely on Windows; Set to 0 if facing issues.
$env:PYINSTALLER_UPX = "1"

function Get-PythonCommand {
    foreach ($candidate in @("py -3", "python", "python3")) {
        try {
            & cmd /c "$candidate --version" 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
            continue
        }
    }
    throw "Python not found. Install Python 3 and ensure 'py' or 'python' is available."
}

function Ensure-BuildDependencies {
    param([string]$PythonCommand)

    & cmd /c "$PythonCommand -m PyInstaller --version" 1>$null 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing build dependencies from requirements.txt..."
        & cmd /c "$PythonCommand -m pip install -r requirements.txt"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install requirements.txt"
        }
    }
}

function Remove-OutputExe {
    param([string]$ExePath)

    if (-not (Test-Path $ExePath)) {
        return
    }

    try {
        Remove-Item $ExePath -Force -ErrorAction Stop
    } catch {
        throw @"
Cannot overwrite '$ExePath'.
Close any running XLSX Grader window or server process, then run the build again.
"@
    }
}

function Invoke-Build {
    param(
        [string]$Label,
        [string]$SpecFile,
        [string]$OutputExe,
        [string]$PythonCommand
    )

    Write-Host ""
    Write-Host "=== $Label ==="
    Remove-OutputExe -ExePath $OutputExe
    $started = Get-Date
    & cmd /c "$PythonCommand -m PyInstaller --noconfirm --clean --log-level INFO $SpecFile"
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    $elapsed = (Get-Date) - $started
    Write-Host "$Label finished in $($elapsed.ToString('mm\:ss'))"
}

$python = Get-PythonCommand
Write-Host "Using: $python"
Ensure-BuildDependencies -PythonCommand $python

Invoke-Build -Label "Web server executable" -SpecFile "xlsx_application_grader_web.spec" -OutputExe "dist\xlsx_application_grader_web.exe" -PythonCommand $python
Invoke-Build -Label "Native app executable" -SpecFile "xlsx_application_grader.spec" -OutputExe "dist\xlsx_application_grader.exe" -PythonCommand $python

Write-Host ""
Write-Host "Build complete:"
Write-Host "  dist\xlsx_application_grader_web.exe  - local web server (opens Chrome or Edge)"
Write-Host "  dist\xlsx_application_grader.exe      - native desktop window (no web server)"

Read-Host -Prompt "Press Enter to exit"
