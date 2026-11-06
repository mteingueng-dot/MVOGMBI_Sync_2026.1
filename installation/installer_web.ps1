# Mise en service de l'application web de MVOGMBI_Sync sur le serveur (SERVDCSAGE, le serveur de Sage).
# Lancer depuis son dossier :
#     powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\MVOGMBI_Sync\installer_web.ps1"
# À lancer PAR LE PROPRIÉTAIRE, en Bureau à distance, dans un PowerShell « Exécuter en tant qu'administrateur »,
# après l'installation de MVOGMBI_Sync sur le serveur :
#     powershell -ExecutionPolicy Bypass -File "<dossier de MVOGMBI_Sync>\installer_web.ps1"
# Ce que fait le script (rien d'autre) :
#   1. [web] adresse = adresse Tailscale du serveur, port 8765 (config.toml de l'application) ;
#   2. règle du pare-feu Windows : port 8765 ouvert SEULEMENT sur la carte Tailscale (jamais sur Internet ni le réseau local) ;
#   3. tâche planifiée « MVOGMBI_Sync Web » : démarre le serveur web à l'ouverture de votre session, sous votre
#      compte (le jeton Clover est dans VOTRE coffre-fort Windows), relancée en cas d'arrêt.
# Retrait : powershell -File installer_web.ps1 -Retirer
param(
    [string]$Dossier = $PSScriptRoot,
    [int]$Port = 8765,
    [switch]$Retirer
)
$ErrorActionPreference = "Stop"
$Tache = "MVOGMBI_Sync Web"
$Regle = "MVOGMBI_Sync Web (Tailscale)"

if ($Retirer) {
    Unregister-ScheduledTask -TaskName $Tache -Confirm:$false -ErrorAction SilentlyContinue
    Remove-NetFirewallRule -DisplayName $Regle -ErrorAction SilentlyContinue
    Write-Host "Tâche et règle du pare-feu retirées."
    exit 0
}

$moteur = Join-Path $Dossier "MVOGMBI_Sync_Serveur.exe"
if (-not (Test-Path $moteur)) { throw "MVOGMBI_Sync_Serveur.exe introuvable dans $Dossier : installez d'abord MVOGMBI_Sync." }
$config = Join-Path $Dossier "config.toml"
if (-not (Test-Path $config)) { throw "config.toml introuvable : ouvrez une fois MVOGMBI_Sync et réglez Clover." }

# 1. adresse Tailscale (100.x.y.z)
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
       Where-Object { $_.InterfaceAlias -like "Tailscale*" -or $_.IPAddress -like "100.*" } |
       Select-Object -First 1).IPAddress
if (-not $ip) { throw "Aucune adresse Tailscale : connectez Tailscale sur ce serveur." }
$texte = Get-Content $config -Raw -Encoding UTF8
if ($texte -notmatch "(?m)^\[web\]") {
    $texte = $texte.TrimEnd() + "`r`n`r`n[web]`r`nadresse = `"$ip`"`r`nport = $Port`r`ninactivite_minutes = 5`r`n" +
             "# postes du magasin qui peuvent pointer (adresses Tailscale ou débuts d'adresse)`r`npostes_pointage = []`r`n"
    [IO.File]::WriteAllText($config, $texte, (New-Object Text.UTF8Encoding $false))
    Write-Host "config.toml : section [web] ajoutée ($ip, port $Port)."
} else {
    # configuration reprise d'un autre serveur : l'adresse d'écoute devient celle de CE serveur
    $texte = [regex]::Replace($texte, '(?ms)(^\[web\][^\[]*?^adresse\s*=\s*)"[^"]*"', "`${1}`"$ip`"")
    if ($texte -notmatch '(?ms)^\[web\][^\[]*?^adresse\s*=') {
        $texte = [regex]::Replace($texte, '(?m)^\[web\]\s*$', "[web]`r`nadresse = `"$ip`"")
    }
    [IO.File]::WriteAllText($config, $texte, (New-Object Text.UTF8Encoding $false))
    Write-Host "config.toml : [web] adresse = $ip (adresse Tailscale de ce serveur)."
}

# port réglé dans config.toml ([web] port : 443 avec HTTPS, voir certificat_https.ps1)
$texte = Get-Content $config -Raw -Encoding UTF8
$m = [regex]::Match($texte, '(?ms)^\[web\][^\[]*?^port\s*=\s*(\d+)')
if ($m.Success -and -not $PSBoundParameters.ContainsKey("Port")) { $Port = [int]$m.Groups[1].Value }
$https = [regex]::IsMatch($texte, '(?ms)^\[web\][^\[]*?^certificat\s*=\s*"[^"]+"')

# 2. pare-feu : Tailscale seulement
$carte = (Get-NetIPAddress -IPAddress $ip).InterfaceAlias
Remove-NetFirewallRule -DisplayName $Regle -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $Regle -Direction Inbound -Protocol TCP -LocalPort $Port -InterfaceAlias $carte `
    -Action Allow -Profile Any | Out-Null
Write-Host "Pare-feu : port $Port ouvert sur « $carte » seulement."

# 3. tâche planifiée, sous le compte de la personne (aucun mot de passe demandé)
$utilisateur = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $moteur -WorkingDirectory $Dossier
$reglages = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries
# À l'ouverture de la session, jamais au démarrage de Windows : sur SERVDC01 (constat), un programme lancé sans session
# (session 0) se fige (constat du 2026-11-03 : processus bloqué, 0,015 s de processeur). Verrouiller la session,
# ne pas la fermer. Le serveur n'a pas de fenêtre (2.18.0) : il tourne en arrière-plan ; une 2e copie s'arrête seule.
$principal = New-ScheduledTaskPrincipal -UserId $utilisateur -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $Tache -Action $action -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $utilisateur) `
    -Settings $reglages -Principal $principal -Force | Out-Null
Write-Host "Tâche « $Tache » : à l'ouverture de votre session (verrouillez la session, ne la fermez pas)."
Start-ScheduledTask -TaskName $Tache
Write-Host ""
if ($https -and $Port -eq 443) { Write-Host "Application web : https://app.marchemvogmbi.com/  (depuis un appareil connecté à Tailscale)" }
else { Write-Host "Application web : http://${ip}:$Port/  (depuis un appareil connecté à Tailscale)" }
Write-Host "Postes : copier client\MVOGMBI_Sync_Client.exe et le lancer (adresse demandée la 1re fois : ${ip})."
