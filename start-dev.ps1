# start-dev.ps1 — 一键后台启动前后端（无终端窗口）
# 用法：.\start-dev.ps1        启动   .\start-dev.ps1 -Stop   停止
# 排查失败：将下方 -WindowStyle Hidden 改为 Normal 即可看到进程输出
param([switch]$Stop)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$nodeExe = "D:\program file\nodejs\node.exe"
$pyExe = Join-Path $root ".venv-server\Scripts\python.exe"
$serverDir = Join-Path $root "server"
$frontDir = Join-Path $root "frontend"
$viteJs = Join-Path $frontDir "node_modules\vite\bin\vite.js"

function Stop-Dev {
  $py = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match "app:app" }
  $nd = Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match "vite.bin.vite.js" }
  $procs = @($py) + @($nd) | Where-Object { $_ }
  $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($Stop) { Stop-Dev; Write-Output "已停止前后端"; exit }

if (-not (Test-Path $pyExe)) { Write-Output "缺少 .venv-server，请先创建虚拟环境并装 fastapi/uvicorn/pydantic/python-multipart"; exit 1 }
if (-not (Test-Path $viteJs)) { Write-Output "缺少前端依赖，请先在 frontend/ 下 npm install"; exit 1 }

Stop-Dev
Start-Sleep -Seconds 3

Start-Process -FilePath $pyExe `
  -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory $serverDir -WindowStyle Hidden

Start-Process -FilePath $nodeExe `
  -ArgumentList $viteJs,"--host" `
  -WorkingDirectory $frontDir -WindowStyle Hidden

function Wait-Url($url, $name) {
  for ($i = 0; $i -lt 15; $i++) {
    try { (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2).StatusCode | Out-Null; Write-Output "$name  $url  OK"; return }
    catch { Start-Sleep -Seconds 1 }
  }
  Write-Output "$name 启动失败（排查：将脚本中对应 -WindowStyle 改为 Normal 后重跑）"
}
Wait-Url "http://127.0.0.1:8000/docs" "后端"
Wait-Url "http://localhost:5173" "前端"
Write-Output "停止：.\start-dev.ps1 -Stop"
