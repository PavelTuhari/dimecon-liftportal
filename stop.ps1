# Остановка серверов проекта dimecon.md.

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ports = 8080, 8090
Write-Host 'Останавливаю серверы проекта...' -ForegroundColor Yellow

$stopped = 0
foreach ($port in $ports) {
    foreach ($conn in Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host ("  порт {0}: {1} (PID {2})" -f $port, $proc.ProcessName, $proc.Id)
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            $stopped++
        }
    }
}
Write-Host ("Остановлено процессов: {0}" -f $stopped) -ForegroundColor Green

if (Get-Process mysqld -ErrorAction SilentlyContinue) {
    $answer = Read-Host 'Остановить также MySQL? (y/N)'
    if ($answer -match '^(y|д)') {
        Stop-Process -Name mysqld -Force -ErrorAction SilentlyContinue
        Write-Host 'MySQL остановлен.' -ForegroundColor Green
    } else {
        Write-Host 'MySQL продолжает работать.' -ForegroundColor DarkGray
    }
}
if ($env:DIMECON_NO_PAUSE -ne '1') { Read-Host 'Enter чтобы закрыть' }
