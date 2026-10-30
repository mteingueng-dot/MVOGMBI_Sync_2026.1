"""Sauvegarde automatique des données de l'application (demande du propriétaire du 2026-10-29, priorité n° 1).

Le dossier donnees/ (correspondance validée, pointages, approbations, registres des factures, paiements, paies…)
n'existe qu'à un endroit : il est copié dans une archive .zip vérifiée, chaque nuit (traitement automatique) et à la
demande (Administration > Sauvegarde), avec config.toml (aucun secret : ils sont dans le coffre-fort de Windows et
se ressaisissent sur un autre poste). Les caches qui se refont seuls (cache_clover, manuels, *.cache.json) ne sont
pas copiés.

Dossier : [sauvegarde] dossier de config.toml, sinon OneDrive\\MVOGMBI_Sync_sauvegardes s'il existe, sinon un dossier
à côté de l'application (même disque : signalé). Conservation : la dernière de chacun des 14 derniers jours, des 8
dernières semaines et des 12 derniers mois. Restauration : l'état actuel est d'abord sauvegardé, puis l'archive
(vérifiée) est remise en place.
"""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

PREFIXE = "MVOGMBI_Sync_"
EXCLUS_DOSSIERS = {"cache_clover", "manuels", "__pycache__"}
EXCLUS_SUFFIXES = (".verrou", ".tmp", ".cache.json", ".lock")
JOURS, SEMAINES, MOIS = 14, 8, 12
ALERTE_JOURS = 2  # au-delà, l'accueil et le compte rendu le signalent


@dataclass
class Etat:
    quand: str = ""
    fichier: str = ""
    taille: int = 0
    fichiers: int = 0
    ok: bool = False
    message: str = ""


def dossier_par_defaut(racine: Path) -> Path:
    onedrive = os.environ.get("OneDriveCommercial") or os.environ.get("OneDrive")
    if onedrive and Path(onedrive).is_dir():
        return Path(onedrive) / "MVOGMBI_Sync_sauvegardes"
    return Path(racine).resolve().parent / "MVOGMBI_Sync_sauvegardes"


def dossier(racine: Path, config_toml: dict) -> Path:
    choisi = str(config_toml.get("sauvegarde", {}).get("dossier", "")).strip()
    return Path(choisi) if choisi else dossier_par_defaut(racine)


def meme_disque(racine: Path, cible: Path) -> bool:
    return Path(racine).resolve().drive.lower() == Path(cible).resolve().drive.lower() and \
        "onedrive" not in str(cible).lower()


def _a_copier(racine: Path):
    donnees = Path(racine) / "donnees"
    for chemin in sorted(donnees.rglob("*")):
        relatif = chemin.relative_to(racine)
        if not chemin.is_file() or any(p in EXCLUS_DOSSIERS for p in relatif.parts) \
                or chemin.name.endswith(EXCLUS_SUFFIXES):
            continue
        yield chemin, relatif.as_posix()
    config = Path(racine) / "config.toml"
    if config.exists():
        yield config, "config.toml"


def _etat_chemin(racine: Path) -> Path:
    return Path(racine) / "donnees" / "derniere_sauvegarde.json"


def derniere(racine: Path) -> Etat:
    try:
        return Etat(**json.loads(_etat_chemin(racine).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return Etat()


def en_retard(racine: Path, maintenant: datetime | None = None) -> str:
    """Texte d'alerte si aucune sauvegarde réussie depuis ALERTE_JOURS jours ; « » sinon."""
    e = derniere(racine)
    if not e.ok or not e.quand:
        return "Aucune sauvegarde des données n'a encore été faite."
    age = (maintenant or datetime.now()) - datetime.fromisoformat(e.quand)
    if age > timedelta(days=ALERTE_JOURS):
        return f"Dernière sauvegarde des données il y a {age.days} jours ({e.quand[:16].replace('T', ' ')})."
    return ""


def verifier(archive: Path, attendus: int | None = None) -> str:
    """« » si l'archive se relit entièrement (contrôle CRC de chaque fichier) ; sinon la raison."""
    try:
        with zipfile.ZipFile(archive) as z:
            mauvais = z.testzip()
            if mauvais:
                return f"fichier abîmé dans l'archive : {mauvais}"
            if attendus is not None and len(z.namelist()) != attendus:
                return f"{len(z.namelist())} fichiers au lieu de {attendus}"
    except (OSError, zipfile.BadZipFile) as exc:
        return f"archive illisible : {exc}"
    return ""


def sauvegarder(racine: Path, config_toml: dict, cible: Path | None = None, prefixe: str = PREFIXE,
                maintenant: datetime | None = None) -> Etat:
    """Archive .zip de donnees/ + config.toml, vérifiée, puis conservation ; l'état est noté dans donnees/."""
    racine = Path(racine)
    cible = Path(cible) if cible else dossier(racine, config_toml)
    maintenant = maintenant or datetime.now()
    etat = Etat(quand=maintenant.isoformat(timespec="seconds"))
    try:
        cible.mkdir(parents=True, exist_ok=True)
        archive = cible / f"{prefixe}{maintenant:%Y-%m-%d_%H%M%S}.zip"
        provisoire = archive.with_suffix(".partiel")
        fichiers = list(_a_copier(racine))
        with zipfile.ZipFile(provisoire, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for chemin, nom in fichiers:
                try:
                    z.write(chemin, nom)
                except PermissionError:  # fichier ouvert ailleurs (Excel) : copié par lecture simple
                    z.writestr(nom, chemin.read_bytes())
        probleme = verifier(provisoire, len(fichiers))
        if probleme:
            provisoire.unlink(missing_ok=True)
            raise RuntimeError(probleme)
        provisoire.replace(archive)
        etat.fichier, etat.taille, etat.fichiers, etat.ok = str(archive), archive.stat().st_size, len(fichiers), True
        if prefixe == PREFIXE:
            supprimees = conserver(cible, maintenant.date())
            etat.message = f"{len(supprimees)} ancienne(s) sauvegarde(s) retirée(s)" if supprimees else ""
        if meme_disque(racine, cible):
            etat.message = ("Dossier de sauvegarde sur le même disque que les données : une panne de ce disque "
                            "perdrait les deux. Choisissez un autre disque ou OneDrive. " + etat.message).strip()
    except Exception as exc:
        etat.ok, etat.message = False, str(exc)
    if prefixe == PREFIXE:  # une sauvegarde « avant restauration » ne remplace pas l'état de la dernière
        _etat_chemin(racine).parent.mkdir(parents=True, exist_ok=True)
        _etat_chemin(racine).write_text(json.dumps(asdict(etat), ensure_ascii=False, indent=1), encoding="utf-8")
    return etat


def archives(cible: Path) -> list[Path]:
    """Sauvegardes du dossier, la plus récente d'abord."""
    if not Path(cible).is_dir():
        return []
    return sorted((p for p in Path(cible).glob("MVOGMBI_Sync*.zip") if p.is_file()), key=lambda p: p.name,
                  reverse=True)


def _jour(archive: Path) -> date | None:
    try:
        return datetime.strptime(archive.stem[len(PREFIXE):len(PREFIXE) + 10], "%Y-%m-%d").date()
    except ValueError:
        return None


def a_garder(noms: list[Path], aujourdhui: date) -> set[Path]:
    """La plus récente de chacun des JOURS derniers jours, SEMAINES dernières semaines et MOIS derniers mois."""
    gardees: set[Path] = set()
    vues_jour, vues_semaine, vues_mois = set(), set(), set()
    for a in sorted(noms, key=lambda p: p.name, reverse=True):
        j = _jour(a)
        if j is None:
            gardees.add(a)  # nom inconnu : jamais supprimé
            continue
        if (aujourdhui - j).days < JOURS and j not in vues_jour:
            gardees.add(a)
            vues_jour.add(j)
        semaine = j.isocalendar()[:2]
        if (aujourdhui - j).days < SEMAINES * 7 and semaine not in vues_semaine:
            gardees.add(a)
            vues_semaine.add(semaine)
        mois = (j.year, j.month)
        if (aujourdhui.year - j.year) * 12 + aujourdhui.month - j.month < MOIS and mois not in vues_mois:
            gardees.add(a)
            vues_mois.add(mois)
    if noms:
        gardees.add(max(noms, key=lambda p: p.name))  # jamais la plus récente
    return gardees


def conserver(cible: Path, aujourdhui: date) -> list[Path]:
    toutes = [a for a in archives(cible) if a.name.startswith(PREFIXE)]
    gardees = a_garder(toutes, aujourdhui)
    retirees = [a for a in toutes if a not in gardees]
    for a in retirees:
        a.unlink(missing_ok=True)
    return retirees


def restaurer(racine: Path, config_toml: dict, archive: Path) -> tuple[Etat, int]:
    """Remet en place une sauvegarde : vérifiée d'abord, l'état actuel est sauvegardé (« avant restauration »),
    puis chaque fichier est réécrit (seulement donnees/… et config.toml). Renvoie (sauvegarde de l'état actuel,
    nombre de fichiers restaurés)."""
    racine = Path(racine)
    probleme = verifier(Path(archive))
    if probleme:
        raise RuntimeError(f"Sauvegarde inutilisable : {probleme}")
    avant = sauvegarder(racine, config_toml, Path(archive).parent / "avant_restauration",
                        prefixe="MVOGMBI_Sync_avant_restauration_")
    if not avant.ok:
        raise RuntimeError(f"L'état actuel n'a pas pu être sauvegardé : rien n'est restauré ({avant.message}).")
    n = 0
    with zipfile.ZipFile(archive) as z:
        for nom in z.namelist():
            chemin = Path(nom)
            if chemin.is_absolute() or ".." in chemin.parts or not (nom == "config.toml"
                                                                     or chemin.parts[0] == "donnees"):
                continue  # jamais en dehors de l'application
            destination = racine / chemin
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(z.read(nom))
            n += 1
    return avant, n
