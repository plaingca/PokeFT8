$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
py -3.13 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 with Tkinter, then run setup again.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -X utf8 prepare_reference.py
if ($LASTEXITCODE -ne 0) { throw 'Reference preparation failed.' }
Write-Host 'Setup complete. Add your own Pokemon Red.gb, then run Start-Demo.cmd.'
