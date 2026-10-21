# Libera o painel na rede local (precisa de administrador).
#
# Por que isso é necessário: o Windows Firewall bloqueia conexões de entrada por
# padrão. Como este projeto não tem instalador, o Python nunca ganhou a regra que
# o instalador criaria — e o celular bate na porta e não recebe resposta.
#
# O script se eleva sozinho (aparece o pedido de administrador do Windows).
#
#   powershell -ExecutionPolicy Bypass -File scripts\liberar_firewall.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\liberar_firewall.ps1 -Porta 8080 -RedePrivada
param(
    [int]$Porta = 8000,
    [switch]$RedePrivada
)

$nomeRegra = "Brasil Saude $Porta"

function Testar-Admin {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if (-not (Testar-Admin)) {
    Write-Host "Elevando para administrador…"
    $argumentos = @(
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-Porta", "$Porta"
    )
    if ($RedePrivada) { $argumentos += "-RedePrivada" }
    Start-Process -FilePath "powershell.exe" -ArgumentList $argumentos -Verb RunAs
    return
}

# 1. Regra de porta em todos os perfis: a rede de casa pode estar classificada
#    como Pública, e uma regra só para "privada" não resolveria.
$existente = Get-NetFirewallRule -DisplayName $nomeRegra -ErrorAction SilentlyContinue
if ($existente) {
    Write-Host "Regra '$nomeRegra' já existe. Reaplicando para todos os perfis…"
    Set-NetFirewallRule -DisplayName $nomeRegra -Enabled True -Profile Any -Action Allow | Out-Null
} else {
    New-NetFirewallRule -DisplayName $nomeRegra `
        -Direction Inbound -Protocol TCP -LocalPort $Porta `
        -Action Allow -Profile Any | Out-Null
    Write-Host "Regra '$nomeRegra' criada (TCP $Porta, todos os perfis)."
}

# 2. Opcional: tratar a rede atual como privada. Em rede privada o Windows é
#    menos restritivo e permite descoberta do computador pelo celular.
if ($RedePrivada) {
    foreach ($perfil in Get-NetConnectionProfile) {
        if ($perfil.NetworkCategory -ne "Private") {
            try {
                Set-NetConnectionProfile -InterfaceIndex $perfil.InterfaceIndex -NetworkCategory Private -ErrorAction Stop
                Write-Host "Rede '$($perfil.Name)' agora está como Privada."
            } catch {
                Write-Host "Não foi possível mudar '$($perfil.Name)': $($_.Exception.Message)"
            }
        }
    }
}

# 3. Mostra o endereço para conferir no celular.
$endereco = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" -or $_.IPAddress -like "172.*" } |
    Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "Pronto. No celular (mesmo Wi-Fi): http://${endereco}:$Porta"
Write-Host "Se ainda não abrir, o roteador pode estar com isolamento de clientes ligado."
Write-Host ""
Read-Host "Pressione Enter para fechar"
