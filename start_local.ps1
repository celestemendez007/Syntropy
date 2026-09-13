param([int]$Port = 8000, [switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
if (-not $SkipBuild) {
    Push-Location (Join-Path $projectRoot 'src/frontend')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'La compilación del frontend falló.' }
    } finally { Pop-Location }
}
try {
    $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
    if ($health.mode -eq 'synthetic-demo') {
        Write-Output "BA A Tiempo ya está disponible en http://127.0.0.1:$Port"
        exit 0
    }
} catch { }
$pythonExe = (Get-Command python.exe).Source
$localPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $localPython) { $pythonExe = $localPython }
$backendDir = Join-Path $projectRoot 'src/backend'
$serverArgs = @('-B', '-m', 'uvicorn', 'main:app', '--app-dir', ('"' + $backendDir + '"'), '--host', '127.0.0.1', '--port', "$Port")
$process = Start-Process -FilePath $pythonExe -ArgumentList $serverArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'server.stderr.log') -PassThru
@{ pid = $process.Id; port = $Port; startedAt = (Get-Date).ToString('o'); executable = $pythonExe } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'server.json')
for ($attempt=0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) { throw "El servidor terminó. Revisa .runtime/server.stderr.log" }
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
        if ($health.status -eq 'ok') { Write-Output "BA A Tiempo: http://127.0.0.1:$Port"; exit 0 }
    } catch { }
}
throw 'El servidor no respondió dentro del tiempo esperado.'
