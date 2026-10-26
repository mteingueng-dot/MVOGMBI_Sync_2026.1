"""Reconnaissance de caractères locale, sans service externe : moteur OCR intégré à Windows (Windows.Media.Ocr).

Sert aux factures fournisseurs numérisées (PDF images, photos de factures imprimées). Les pages PDF sont rendues
en image (pypdfium2, installé avec pdfplumber), puis lues par l'OCR de Windows appelé depuis PowerShell 5.1 (API
WinRT, présente sur Windows 10/11 et Windows Server avec expérience utilisateur). Les mots reviennent avec leur
position : on reconstitue les lignes de la facture d'après leur hauteur, ce qui garde les colonnes dans l'ordre.
L'écriture manuscrite n'est pas lue de façon fiable : ces factures se saisissent dans la page.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

LANGUE = "fr-CA"

SCRIPT = r"""
param([string]$Image, [string]$Langue)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Attendre($operation, [Type]$type) {
    $tache = $asTask.MakeGenericMethod($type).Invoke($null, @($operation)); $tache.Wait(-1) | Out-Null; $tache.Result }
[void][Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
[void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
[void][Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
[void][Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$fichier = Attendre ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Image)) ([Windows.Storage.StorageFile])
$flux = Attendre ($fichier.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decodeur = Attendre ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($flux)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Attendre ($decodeur.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$moteur = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new($Langue))
if (-not $moteur) { $moteur = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
$resultat = Attendre ($moteur.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$mots = foreach ($ligne in $resultat.Lines) { foreach ($mot in $ligne.Words) {
    [pscustomobject]@{ t = $mot.Text; x = [int]$mot.BoundingRect.X; y = [int]$mot.BoundingRect.Y;
                       h = [int]$mot.BoundingRect.Height } } }
[Console]::OutputEncoding = [Text.Encoding]::UTF8
@($mots) | ConvertTo-Json -Compress
"""


def mots_image(image: Path, langue: str = LANGUE) -> list[dict]:
    """Mots reconnus dans une image : [{t, x, y, h}, …]."""
    with tempfile.TemporaryDirectory() as dossier:
        script = Path(dossier) / "ocr.ps1"
        script.write_text(SCRIPT, encoding="utf-8-sig")
        sortie = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), str(Path(image).resolve()),
             langue], capture_output=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if sortie.returncode != 0:
        raise RuntimeError("OCR de Windows indisponible : " + sortie.stderr.decode("utf-8", "replace")[-400:])
    texte = sortie.stdout.decode("utf-8", "replace").strip()
    if not texte:
        return []
    donnees = json.loads(texte)
    return donnees if isinstance(donnees, list) else [donnees]


def lignes_depuis_mots(mots: list[dict]) -> list[str]:
    """Regroupe les mots en lignes (même hauteur à une demi-ligne près), de gauche à droite."""
    lignes: list[list[dict]] = []
    for mot in sorted(mots, key=lambda m: (m["y"], m["x"])):
        centre = mot["y"] + mot["h"] / 2
        for ligne in lignes:
            reference = ligne[0]
            if abs(centre - (reference["y"] + reference["h"] / 2)) <= max(reference["h"], mot["h"]) * 0.55:
                ligne.append(mot)
                break
        else:
            lignes.append([mot])
    return [" ".join(m["t"] for m in sorted(ligne, key=lambda m: m["x"])) for ligne in lignes]


def texte_image(image: Path) -> str:
    return "\n".join(lignes_depuis_mots(mots_image(image)))


def texte_pdf_numerise(chemin: Path, resolution: int = 300) -> str:
    """Texte d'un PDF sans couche texte : chaque page est rendue en image puis lue par l'OCR de Windows."""
    import pdfplumber

    pages = []
    with pdfplumber.open(chemin) as pdf, tempfile.TemporaryDirectory() as dossier:
        for numero, page in enumerate(pdf.pages, start=1):
            image = Path(dossier) / f"page{numero}.png"
            page.to_image(resolution=resolution).save(image)
            pages.append(texte_image(image))
    return "\n".join(pages)
