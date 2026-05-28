$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$ImageName = if ($env:AXURE_SHARE_IMAGE) { $env:AXURE_SHARE_IMAGE } else { "axure-share-runtime:latest" }
$ContainerName = if ($env:AXURE_SHARE_CONTAINER) { $env:AXURE_SHARE_CONTAINER } else { "axure-share" }
$AppPort = if ($env:AXURE_SHARE_PORT) { $env:AXURE_SHARE_PORT } else { "7855" }
$PipIndexUrl = if ($env:PIP_INDEX_URL) { $env:PIP_INDEX_URL } else { "https://pypi.tuna.tsinghua.edu.cn/simple" }

if (!(Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}

New-Item -ItemType Directory -Force -Path "instance", "uploads/prototypes", "uploads/source_files", "uploads/attachments" | Out-Null

docker build -t $ImageName .

docker rm -f $ContainerName 2>$null | Out-Null

docker run -d `
  --name $ContainerName `
  --restart unless-stopped `
  --env-file .env `
  -e FLASK_APP=app.py `
  -e PYTHONUNBUFFERED=1 `
  -e PIP_INDEX_URL=$PipIndexUrl `
  -p "$AppPort`:7855" `
  -v "$ProjectDir`:/workspace" `
  $ImageName

Write-Host "部署完成：http://localhost:$AppPort"
Write-Host "源码目录已挂载到容器 /workspace，修改代码后执行 docker restart $ContainerName 即可生效"
