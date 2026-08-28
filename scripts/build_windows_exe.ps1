param(
    [string]$Name = "MiniaturedWorld"
)

$ErrorActionPreference = "Stop"

if ([System.Environment]::OSVersion.Platform -ne "Win32NT") {
    throw "PyInstaller exe build is supported only on Windows."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --name $Name `
    --onefile `
    --paths src `
    --add-data "src\miniatured_world\content\defaults.json;miniatured_world\content" `
    src\miniatured_world\__main__.py

Write-Host "Build completed: dist\$Name.exe"
