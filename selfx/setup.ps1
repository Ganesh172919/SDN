$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
# pytest.ini writes its temp files under tmp/, which git ignores, so create it here
New-Item -ItemType Directory -Force -Path 'tmp' | Out-Null
Write-Output 'Setup complete. Run .\run.ps1 test, then .\run.ps1 dashboard'
