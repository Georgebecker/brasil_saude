# Sobe o painel na rede local com vigia automático.
#
# Por que existe: o servidor sozinho cai quando o terminal fecha, quando o
# processo filho morre ou quando o Windows suspende a sessão. Este script abre
# o vigia em segundo plano (ele reinicia o servidor sozinho), grava log em
# data/rede/vigia.log e imprime o endereço para abrir no celular.
#
#   powershell -ExecutionPolicy Bypass -File scripts\servir_auto.ps1
#
param(
    [int]$Porta = 8000,
    [switch]$Parar
)

$raiz = Split-Path -Parent $PSScriptRoot
$pastaRede = Join-Path $raiz "data\rede"
$log = Join-Path $pastaRede "vigia.log"
$pidFile = Join-Path $pastaRede "vigia.pid"
$python = Join-Path $raiz ".venv\Scripts\python.exe"

New-Item -ItemType Directory -Force -Path $pastaRede | Out-Null

if ($Parar) {
    # Mata o servidor que escuta a porta e o vigia registrado. Ordem importa:
    # sem matar o servidor primeiro, o próximo Start encontraria a porta ocupada.
    $dono = (Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue).OwningProcess
    foreach ($id in @($dono)) {
        if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
    }
    Get-CimInstance Win32_Process |
        Where-Object { $_.CommandLine -like "*vigia_rede.py*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Vigia e servidor encerrados."
    return
}

# Se o vigia já está batendo, não sobe outro: dois processos disputariam a porta.
$batimento = Join-Path $pastaRede "vigia.json"
if (Test-Path $batimento) {
    $quando = (Get-Item $batimento).LastWriteTime
    if ((Get-Date) - $quando -lt [TimeSpan]::FromSeconds(10)) {
        Write-Host "Já existe vigia ativo (veja $batimento). Use -Parar para encerrar."
        return
    }
}

$processo = Start-Process -FilePath $python `
    -ArgumentList @("scripts\vigia_rede.py", "--porta", "$Porta") `
    -WorkingDirectory $raiz `
    -RedirectStandardOutput $log `
    -RedirectStandardError "$log.erro" `
    -WindowStyle Hidden `
    -PassThru

# O Start-Process devolve o processo lançador; o PID do vigia vem do batimento
# que o próprio vigia grava — é a única fonte que não erra.
Start-Sleep -Seconds 5
$idVigia = "?"
if (Test-Path $batimento) {
    try {
        $idVigia = (Get-Content $batimento -Raw | ConvertFrom-Json).pid_vigia
    } catch {
        $idVigia = "?"
    }
}
Start-Sleep -Seconds 2

# Descobre o IPv4 privado do mesmo jeito que o servidor faz.
$endereco = $null
try {
    $endereco = (Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" -or $_.IPAddress -like "172.*" } |
        Select-Object -First 1).IPAddress
} catch {
    $endereco = $null
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Painel Brasil Saude no ar (vigia pid $idVigia)"
Write-Host "  Neste computador : http://127.0.0.1:$Porta"
if ($endereco) {
    Write-Host "  No celular       : http://${endereco}:$Porta"
} else {
    Write-Host "  No celular       : sem IPv4 privado encontrado"
}
Write-Host "  Log              : $log"
Write-Host "  Parar            : powershell -File scripts\servir_auto.ps1 -Parar"
Write-Host "============================================================"
