# Запуск проекта dimecon.md: MySQL, хаб документации и платформа LiftPortal.
# Окна серверов открываются свёрнутыми и живут независимо от этой консоли.
# Остановить: stop.ps1 (или stop.bat)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# ---- пути; при переносе проекта меняются здесь ----
$MysqlHome = 'D:\MySQL\mysql-8.4.0-winx64'
$MysqlIni  = 'D:\MySQL\my.ini'
$Py        = Join-Path $root '.venv\Scripts\python.exe'
$DocsPort  = 8080
$AppPort   = 8090

function Test-Port([int]$Port) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

Write-Host ''
Write-Host '===============================================' -ForegroundColor DarkCyan
Write-Host '  dimecon.md - документация и платформа' -ForegroundColor Cyan
Write-Host '===============================================' -ForegroundColor DarkCyan
Write-Host ''

if (-not (Test-Path $Py)) {
    Write-Host "[!] Не найдено окружение Python: $Py" -ForegroundColor Red
    Write-Host '    Создайте его:' -ForegroundColor Yellow
    Write-Host '        python -m venv .venv'
    Write-Host '        .venv\Scripts\pip install -r platform\requirements.txt'
    Read-Host 'Enter для выхода'
    exit 1
}

# ---- 1. MySQL ----
if (Get-Process mysqld -ErrorAction SilentlyContinue) {
    Write-Host '[1/3] MySQL уже работает' -ForegroundColor Green
} elseif (Test-Path (Join-Path $MysqlHome 'bin\mysqld.exe')) {
    Write-Host '[1/3] Запуск MySQL...' -ForegroundColor Yellow
    Start-Process -FilePath (Join-Path $MysqlHome 'bin\mysqld.exe') `
                  -ArgumentList "--defaults-file=$MysqlIni" -WindowStyle Hidden
    for ($i = 0; $i -lt 20 -and -not (Test-Port 3306); $i++) { Start-Sleep -Seconds 1 }
    if (Test-Port 3306) { Write-Host '      MySQL поднялся' -ForegroundColor Green }
    else { Write-Host '      MySQL не ответил — платформа откатится на SQLite' -ForegroundColor Yellow }
} else {
    Write-Host "[1/3] MySQL не найден в $MysqlHome — платформа откатится на SQLite" -ForegroundColor Yellow
}

# ---- 2. хаб документации ----
if (Test-Port $DocsPort) {
    Write-Host "[2/3] Порт $DocsPort уже занят — считаю, что документация запущена" -ForegroundColor Green
} else {
    Write-Host "[2/3] Хаб документации  ->  http://localhost:$DocsPort" -ForegroundColor Yellow
    & $Py (Join-Path $root 'tools\build_manifest.py') | Select-Object -First 1 | Out-Host
    Start-Process -FilePath $Py -ArgumentList '-m', 'http.server', "$DocsPort" `
                  -WorkingDirectory $root -WindowStyle Minimized
}

# ---- 3. платформа ----
if (Test-Port $AppPort) {
    Write-Host "[3/3] Порт $AppPort уже занят — считаю, что платформа запущена" -ForegroundColor Green
} else {
    Write-Host "[3/3] Платформа LiftPortal  ->  http://localhost:$AppPort" -ForegroundColor Yellow
    Start-Process -FilePath $Py -ArgumentList 'run.py' `
                  -WorkingDirectory (Join-Path $root 'platform') -WindowStyle Minimized
}

# ---- проверка ----
Write-Host ''
Write-Host 'Проверяю...' -ForegroundColor DarkGray
$ok = @{}
foreach ($pair in @(@{n = 'Документация'; u = "http://localhost:$DocsPort/index.html" },
                    @{n = 'Платформа'; u = "http://localhost:$AppPort/api/v1/health" })) {
    $ok[$pair.n] = $false
    for ($i = 0; $i -lt 25; $i++) {
        try {
            if ((Invoke-WebRequest -Uri $pair.u -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200) {
                $ok[$pair.n] = $true; break
            }
        } catch { Start-Sleep -Milliseconds 700 }
    }
    if ($ok[$pair.n]) { Write-Host ("  {0,-14} работает" -f $pair.n) -ForegroundColor Green }
    else { Write-Host ("  {0,-14} НЕ ОТВЕЧАЕТ" -f $pair.n) -ForegroundColor Red }
}

Write-Host ''
Write-Host 'Адреса:' -ForegroundColor Cyan
Write-Host "  Документация    http://localhost:$DocsPort"
Write-Host "  Платформа       http://localhost:$AppPort"
Write-Host "  Сайт компании   http://localhost:$AppPort/s/dimecon/"
Write-Host "  Кабинет         owner@dimecon.md / demo1234"
Write-Host ''
Write-Host 'Окна серверов свёрнуты в панель задач — закрывать их не нужно.' -ForegroundColor DarkGray
Write-Host 'Остановить всё: stop.bat' -ForegroundColor DarkGray
Write-Host ''

if ($ok['Документация']) { Start-Process "http://localhost:$DocsPort" }
if ($ok['Платформа']) { Start-Process "http://localhost:$AppPort" }
if ($env:DIMECON_NO_PAUSE -ne '1') { Read-Host 'Enter чтобы закрыть это окно (серверы продолжат работать)' }
