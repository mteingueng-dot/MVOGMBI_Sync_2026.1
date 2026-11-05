# Certificat HTTPS Let's Encrypt pour https://app.marchemvogmbi.com (sans port), validé par le DNS.
# À lancer PAR LE PROPRIÉTAIRE sur le serveur (SERVDCSAGE), en Bureau à distance, dans un PowerShell
# « Exécuter en tant qu'administrateur » :
#     powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Programs\MVOGMBI_Sync\certificat_https.ps1" -Courriel vous@exemple.com
#
# Avant : télécharger win-acme (https://www.win-acme.com, version « x64 trimmed ») et décompresser wacs.exe dans
# C:\win-acme (ou donner -WinAcme "chemin\wacs.exe").
#
# Pourquoi le DNS : app.marchemvogmbi.com pointe vers l'adresse Tailscale (privée) du serveur ; Let's Encrypt ne peut
# pas le joindre par le web. win-acme affiche un enregistrement TXT « _acme-challenge.app » à créer dans la zone DNS
# chez WHC (comme les enregistrements A), puis Let's Encrypt le vérifie et donne le certificat (90 jours).
# Renouvellement : tâche planifiée de win-acme ; un nouveau TXT est demandé chaque fois (validation manuelle) ; le
# serveur web relit le certificat renouvelé tout seul (contrôle horaire).
#
# Ce que fait le script : demande le certificat (fichiers PEM dans C:\Certificats\MVOGMBI_Sync), puis inscrit dans
# config.toml : [web] port = 443, certificat = …-chain.pem, cle = …-key.pem. Relancer ensuite installer_web.ps1
# (pare-feu sur le port 443, Tailscale seulement) et le serveur web.
param(
    [Parameter(Mandatory = $true)][string]$Courriel,
    [string]$Nom = "app.marchemvogmbi.com",
    [string]$WinAcme = "",
    [string]$Dossier = "",
    [string]$Sortie = ""
)
$ErrorActionPreference = "Stop"
# dossier de MVOGMBI_Sync : celui du script, sinon l'emplacement d'installation habituel
if (-not $Dossier) { $Dossier = $PSScriptRoot }
if (-not $Dossier -and $MyInvocation.MyCommand.Path) { $Dossier = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $Dossier) { $Dossier = Join-Path $env:LOCALAPPDATA "Programs\MVOGMBI_Sync" }
if (-not $Sortie) { $Sortie = "C:\Certificats\MVOGMBI_Sync" }
if (-not $WinAcme) {
    $WinAcme = @("C:\win-acme\wacs.exe", (Join-Path $env:ProgramFiles "win-acme\wacs.exe"),
                 (Join-Path $Dossier "win-acme\wacs.exe")) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
               Select-Object -First 1
}
if (-not $WinAcme -or -not (Test-Path -LiteralPath $WinAcme)) {
    throw "wacs.exe introuvable : téléchargez win-acme (https://www.win-acme.com, « x64 trimmed ») et décompressez-le dans C:\win-acme, ou donnez -WinAcme ""chemin\wacs.exe""."
}
if ($Courriel -notmatch "^[^@\s]+@[^@\s]+\.[^@\s]+$" -or $Courriel -like "votre@*") {
    throw "Donnez votre vraie adresse de courriel : -Courriel vous@exemple.com (Let's Encrypt y envoie les avis d'expiration)."
}
Write-Host "Dossier de MVOGMBI_Sync : $Dossier"
Write-Host "win-acme : $WinAcme"
$config = Join-Path $Dossier "config.toml"
if (-not (Test-Path $config)) { throw "config.toml introuvable dans $Dossier : installez et réglez d'abord MVOGMBI_Sync." }
New-Item -ItemType Directory -Force $Sortie | Out-Null

Write-Host "Demande du certificat pour $Nom (validation DNS manuelle)."
Write-Host "Quand win-acme affiche l'enregistrement TXT : créez-le chez WHC, attendez quelques minutes, puis appuyez sur Entrée."
& $WinAcme --source manual --host $Nom --validationmode dns-01 --validation manual `
    --store pemfiles --pemfilespath $Sortie --accepttos --emailaddress $Courriel
if ($LASTEXITCODE -ne 0) { throw "win-acme n'a pas obtenu le certificat (code $LASTEXITCODE)." }

$chaine = Get-ChildItem $Sortie -Filter "*-chain.pem" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$cle = Get-ChildItem $Sortie -Filter "*-key.pem" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $chaine -or -not $cle) { throw "Fichiers PEM absents de $Sortie." }

# config.toml : [web] port 443, certificat, clé (chemins avec / : TOML accepte les deux)
$texte = Get-Content $config -Raw -Encoding UTF8
$c = $chaine.FullName.Replace("\", "/"); $k = $cle.FullName.Replace("\", "/")
if ($texte -notmatch "(?m)^\[web\]") { $texte = $texte.TrimEnd() + "`r`n`r`n[web]`r`n" }
foreach ($paire in @(@("port", "443"), @("certificat", "`"$c`""), @("cle", "`"$k`""))) {
    $motif = "(?ms)(^\[web\][^\[]*?^" + $paire[0] + "\s*=\s*)[^\r\n]*"
    if ([regex]::IsMatch($texte, $motif)) { $texte = [regex]::Replace($texte, $motif, "`${1}" + $paire[1]) }
    else { $texte = [regex]::Replace($texte, "(?m)^\[web\]\s*$", "[web]`r`n" + $paire[0] + " = " + $paire[1]) }
}
[IO.File]::WriteAllText($config, $texte, (New-Object Text.UTF8Encoding $false))
Write-Host "config.toml : [web] port = 443, certificat et clé inscrits."
Write-Host "Ensuite : relancez installer_web.ps1 (pare-feu 443), puis Administration > Automatisation >"
Write-Host "« Fichier du client (serveur.json) » pour les postes. Adresse : https://$Nom/"
