param(
    [string]$Name = "MiniaturedWorld",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne "Win32NT") {
    throw "PyInstaller exe build is supported only on Windows."
}

$versionCheck = @"
from importlib.metadata import version
from sys import exit

pyside6 = version("PySide6")
parts = tuple(int(part) for part in pyside6.split(".")[:2])
if parts >= (6, 10):
    print(f"PySide6 {pyside6} is not accepted for this build. Use PySide6>=6.7,<6.10.")
    exit(1)
print(f"Using PySide6 {pyside6}")
"@

& $Python -c $versionCheck

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --name $Name `
    --onefile `
    --paths src `
    --hidden-import PySide6.QtCore `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtNetwork `
    --add-data "src\miniatured_world\content\defaults.json;miniatured_world\content" `
    src\miniatured_world\__main__.py

Write-Host "Build completed: dist\$Name.exe"
