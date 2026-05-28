$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$ContainerName = if ($env:AXURE_SHARE_CONTAINER) { $env:AXURE_SHARE_CONTAINER } else { "axure-share" }
$AppPort = if ($env:AXURE_SHARE_PORT) { $env:AXURE_SHARE_PORT } else { "7855" }

if ((Get-Command git -ErrorAction SilentlyContinue) -and (Test-Path ".git")) {
    git pull
}

docker restart $ContainerName

Write-Host "代码已更新，容器已重启：http://localhost:$AppPort"
