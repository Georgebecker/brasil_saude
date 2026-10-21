# Diagnóstico do acesso pelo celular, em linguagem de gente.
#
# Roda sem administrador e responde, em ordem, às perguntas que importam:
#   1. o servidor está escutando em todas as interfaces?
#   2. o computador tem IP na rede local?
#   3. a rede está classificada como Pública (Windows bloqueia entrada)?
#   4. existe regra de firewall liberando a porta?
#   5. o painel responde pelo endereço de rede (não só pelo localhost)?
#
#   powershell -ExecutionPolicy Bypass -File scripts\diagnosticar_rede.ps1
param([int]$Porta = 8000)

Write-Host "=== Brasil Saude - diagnostico de rede ==="
Write-Host ""

$problemas = @()

# 1. Escuta
$escuta = Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue
if (-not $escuta) {
    $problemas += "Nada escutando na porta $Porta. Rode: powershell -File scripts\servir_auto.ps1"
    Write-Host "[1] Escuta      : NADA na porta $Porta"
} else {
    $enderecos = ($escuta.LocalAddress | Sort-Object -Unique) -join ", "
    Write-Host "[1] Escuta      : $enderecos (pid $($escuta[0].OwningProcess))"
    if ($enderecos -notmatch "0\.0\.0\.0|::") {
        $problemas += "O servidor escuta só em $enderecos; o celular não alcança. Use host 0.0.0.0."
    }
}

# 2. IP local
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" -or $_.IPAddress -like "172.*" } |
    Select-Object -First 1).IPAddress
Write-Host "[2] IPv4 local  : $(if ($ip) { $ip } else { 'nenhum (sem Wi-Fi/cabo?)' })"
if (-not $ip) { $problemas += "Sem IPv4 privado: confira se o Wi-Fi está conectado." }

# 3. Perfil de rede
$perfil = Get-NetConnectionProfile | Select-Object -First 1
if ($perfil) {
    Write-Host "[3] Rede        : '$($perfil.Name)' classificada como $($perfil.NetworkCategory)"
    if ($perfil.NetworkCategory -eq "Public") {
        $problemas += "Rede como Pública: o Windows bloqueia entrada. Rode scripts\liberar_firewall.ps1 -RedePrivada"
    }
}

# 4. Firewall
$regra = Get-NetFirewallRule -DisplayName "Brasil Saude $Porta" -ErrorAction SilentlyContinue
if ($regra) {
    Write-Host "[4] Firewall    : regra 'Brasil Saude $Porta' existe (perfil $($regra.Profile), $($regra.Action))"
} else {
    Write-Host "[4] Firewall    : SEM regra para a porta $Porta"
    $problemas += "Falta liberar a porta: rode (como admin) scripts\liberar_firewall.ps1"
}

# 5. Resposta pelo IP de rede
if ($ip) {
    try {
        $resposta = Invoke-WebRequest -UseBasicParsing "http://${ip}:$Porta/api/rede" -TimeoutSec 8
        Write-Host "[5] HTTP via IP : $($resposta.StatusCode) em http://${ip}:$Porta"
    } catch {
        Write-Host "[5] HTTP via IP : FALHOU em http://${ip}:$Porta"
        $problemas += "Não respondeu pelo IP de rede: o firewall está barrando."
    }
}

Write-Host ""
if ($problemas.Count -eq 0) {
    Write-Host "Tudo certo. No celular: http://${ip}:$Porta"
    Write-Host "Se o celular ainda não abrir, desligue o 'isolamento de clientes' (AP isolation) no roteador."
} else {
    Write-Host "O que corrigir:"
    $i = 1
    foreach ($p in $problemas) { Write-Host "  $i. $p"; $i++ }
}
