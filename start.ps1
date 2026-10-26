param(
    [int]$Port = 5000,
    [switch]$Seed,
    [switch]$DebugMode
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Virtual environment not found. Follow README.md first.' }
if (-not (Test-Path -LiteralPath (Join-Path $root '.env'))) { throw 'Configure .env using .env.example first.' }

function Test-TcpPort([int]$Number) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Number, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(1000)) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false } finally { $client.Dispose() }
}

Push-Location $root
try {
    $targetJson = & $python -c "import json,os; from dotenv import load_dotenv; from sqlalchemy.engine import make_url; load_dotenv('.env'); url=make_url(os.environ['DATABASE_URL']); print(json.dumps({'host':url.host,'port':url.port or 3306}))"
    if ($LASTEXITCODE -ne 0) { throw 'DATABASE_URL is invalid.' }
    $target = $targetJson | ConvertFrom-Json
    $portableRoot = Join-Path $root '.local'
    if ($target.host -in @('127.0.0.1','localhost') -and $target.port -eq 13308 -and -not (Test-TcpPort 13308) -and (Test-Path -LiteralPath $portableRoot)) {
        $installation = Get-ChildItem -LiteralPath $portableRoot -Directory -Filter 'mysql-8.*-winx64' | Sort-Object Name -Descending | Select-Object -First 1
        if ($installation) {
            $database = Join-Path $portableRoot 'mysql-data'
            if (-not (Test-Path -LiteralPath $database)) { throw 'Local MySQL data directory is missing. No database was initialized or reset.' }
            $server = Join-Path $installation.FullName 'bin/mysqld.exe'
            $log = Join-Path $portableRoot 'mysql-error.log'
            $arguments = @('--no-defaults', ('--basedir="{0}"' -f $installation.FullName), ('--datadir="{0}"' -f $database), '--port=13308', '--bind-address=127.0.0.1', '--mysqlx=OFF', ('--log-error="{0}"' -f $log))
            Start-Process -FilePath $server -ArgumentList $arguments -WindowStyle Hidden
            for ($attempt = 0; $attempt -lt 15; $attempt++) {
                if (Test-TcpPort 13308) { break }
                Start-Sleep -Seconds 1
            }
        }
    }
    & $python scripts/check_database.py
    if ($LASTEXITCODE -ne 0) { throw 'Cannot connect to MySQL 8. Check .env and the database server.' }
    & $python -m flask --app run.py upgrade-safe
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
    if ($Seed) {
        & $python -m flask --app run.py seed-demo
        if ($LASTEXITCODE -ne 0) { throw 'Demo seeding failed.' }
    }
    if (Test-TcpPort $Port) { throw "Port $Port is in use. Use -Port with another port, or open the existing app." }
    Write-Host "SiWarga: http://127.0.0.1:$Port"
    $arguments = @('-m', 'flask', '--app', 'run.py', 'run', '--host=127.0.0.1', "--port=$Port")
    if ($DebugMode) { $arguments += '--debug' }
    & $python @arguments
} finally {
    Pop-Location
}
