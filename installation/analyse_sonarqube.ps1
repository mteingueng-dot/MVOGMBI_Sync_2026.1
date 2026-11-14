# Analyse SonarQube du code de MVOGMBI_Sync (version 1.0.14, demande du propriétaire du 2026-11-13).
# Poste de développement avec Docker Desktop : lance un serveur SonarQube Community local (conteneur
# « mvogmbi-sonar », port 9100), analyse le code par l'image sonar-scanner-cli, puis écrit le résumé.
# Aucun code n'est envoyé hors du poste. Le mot de passe et le jeton du serveur local sont créés ici et
# gardés dans %LOCALAPPDATA%\MVOGMBI_Sync_Sonar (jamais dans le dépôt).
#
#   powershell -ExecutionPolicy Bypass -File installation\analyse_sonarqube.ps1
#
# Résultats : http://localhost:9100/dashboard?id=mvogmbi_sync et sortie\analyse_sonarqube.txt

$ErrorActionPreference = "Stop"
$racine = Split-Path -Parent $PSScriptRoot
$secrets = Join-Path $env:LOCALAPPDATA "MVOGMBI_Sync_Sonar"
New-Item -ItemType Directory -Force $secrets | Out-Null
$serveur = "http://localhost:9100"

if (-not (docker ps -a --format "{{.Names}}" | Select-String -SimpleMatch "mvogmbi-sonar")) {
    docker run -d --name mvogmbi-sonar -p 9100:9000 -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true sonarqube:community | Out-Null
} else {
    docker start mvogmbi-sonar | Out-Null
}
Write-Host "Démarrage de SonarQube…"
for ($i = 0; $i -lt 60; $i++) {
    try { if ((Invoke-RestMethod "$serveur/api/system/status").status -eq "UP") { break } } catch { }
    Start-Sleep 5
}

function Entete([string]$utilisateur, [string]$mdp) {
    @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${utilisateur}:$mdp")) }
}

$fichierMdp = Join-Path $secrets "admin.txt"
if (-not (Test-Path $fichierMdp)) {  # 1re fois : mot de passe « admin » d'origine remplacé
    $mdp = "Mvog-" + [guid]::NewGuid().ToString("N").Substring(0, 16) + "!A1"
    Invoke-RestMethod -Method Post "$serveur/api/users/change_password" -Headers (Entete "admin" "admin") `
        -Body @{ login = "admin"; previousPassword = "admin"; password = $mdp } | Out-Null
    Set-Content $fichierMdp $mdp -NoNewline
}
$h = Entete "admin" (Get-Content $fichierMdp -Raw)
$jeton = (Invoke-RestMethod -Method Post "$serveur/api/user_tokens/generate" -Headers $h `
    -Body @{ name = "analyse-" + (Get-Date -Format "yyyyMMddHHmmss"); type = "GLOBAL_ANALYSIS_TOKEN" }).token

docker run --rm -e SONAR_HOST_URL="http://host.docker.internal:9100" -e SONAR_TOKEN="$jeton" `
    -v "${racine}:/usr/src" sonarsource/sonar-scanner-cli:latest `
    "-Dsonar.projectKey=mvogmbi_sync" "-Dsonar.projectName=MVOGMBI_Sync" `
    "-Dsonar.sources=mvogmbi_sync,installation,documentation" "-Dsonar.tests=tests" `
    "-Dsonar.inclusions=**/*.py,**/*.js,**/*.ps1" "-Dsonar.exclusions=**/node_modules/**,**/build/**,**/dist/**" `
    "-Dsonar.python.version=3.13" "-Dsonar.scm.disabled=true"

do { Start-Sleep 5; $etat = Invoke-RestMethod "$serveur/api/ce/component?component=mvogmbi_sync" -Headers $h }
while ($etat.queue.Count -gt 0)

$mesures = (Invoke-RestMethod ("$serveur/api/measures/component?component=mvogmbi_sync&metricKeys=" +
    "ncloc,bugs,vulnerabilities,security_hotspots,code_smells,security_rating,reliability_rating,sqale_rating") -Headers $h).component.measures
$ouverts = (Invoke-RestMethod "$serveur/api/issues/search?componentKeys=mvogmbi_sync&ps=500&issueStatuses=OPEN,CONFIRMED" -Headers $h).issues
$lignes = @("Analyse SonarQube du $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "")
$lignes += $mesures | ForEach-Object { "$($_.metric) = $($_.value)" }
$lignes += "", "Constats ouverts : $($ouverts.Count)"
$lignes += $ouverts | ForEach-Object { "$($_.type) $($_.severity) $($_.rule) $($_.component.Split(':')[1]):$($_.line) $($_.message)" }
New-Item -ItemType Directory -Force (Join-Path $racine "sortie") | Out-Null
$lignes | Set-Content (Join-Path $racine "sortie\analyse_sonarqube.txt") -Encoding utf8
$lignes | Write-Host
Write-Host "`nTableau de bord : $serveur/dashboard?id=mvogmbi_sync"
