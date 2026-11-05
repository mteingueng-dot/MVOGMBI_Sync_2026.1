"""Pointage seulement sur le Wi-Fi du magasin (demande du propriétaire du 2026-11-04 : « les employés pour pointer
doivent être sur le Wi-Fi du magasin »).

Les appareils joignent le serveur par Tailscale : le serveur voit leur adresse Tailscale (100.x), pas le Wi-Fi. Le
réseau d'où vient l'appareil se lit dans Tailscale lui-même : l'adresse par laquelle le serveur le joint (« CurAddr »
de `tailscale status --json`, sinon la réponse de `tailscale ping`) est l'adresse publique de la connexion Internet
de ce réseau. Au magasin, c'est celle du Wi-Fi du magasin.

Réglages ([pointage] de config.toml, « Administration > Automatisation > Wi-Fi du magasin ») :
- `wifi` : nom du Wi-Fi du magasin (affiché aux employés) ;
- `adresses_magasin` : adresses publiques du magasin (ou débuts d'adresse) ; vide = pas de contrôle du Wi-Fi ;
- `[web] postes_pointage` : postes du magasin toujours permis (adresses Tailscale ou débuts d'adresse) ;
- `pause_hors_wifi_minutes` (5 par défaut, 0 = jamais) : un employé qui a pointé depuis son téléphone et dont le
  téléphone quitte le Wi-Fi du magasin pendant ce nombre de minutes de suite est mis en pause (à l'heure où il est
  parti) ; la pause se termine quand le téléphone revient sur le Wi-Fi (demande du propriétaire du 2026-11-04).
  Les pauses pointées par l'employé ne sont jamais terminées par l'application.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

DUREE = 30  # s : état de Tailscale gardé
PAUSE_MINUTES = 5  # minutes de suite hors du Wi-Fi avant la pause automatique
FICHIER_SUIVI = "pointage_telephones.json"  # employé -> téléphone suivi (adresse Tailscale), pause automatique
_MEMOIRE: dict = {}


def reglages(config: dict) -> dict:
    p, w = config.get("pointage", {}), config.get("web", {})
    return {"wifi": str(p.get("wifi") or ""), "adresses_magasin": _liste(p.get("adresses_magasin")),
            "postes": _liste(w.get("postes_pointage")),
            "pause_minutes": int(p.get("pause_hors_wifi_minutes", PAUSE_MINUTES) or 0)}


def _liste(valeur) -> list[str]:
    if isinstance(valeur, str):
        valeur = re.split(r"[;,\s]+", valeur)
    return [str(x).strip() for x in (valeur or []) if str(x).strip()]


def ecrire(config: dict, wifi: str, adresses: str, postes: str, pause_minutes: str | int = PAUSE_MINUTES) -> None:
    minutes = int(str(pause_minutes).strip() or 0)
    if minutes < 0:
        raise ValueError("Minutes hors du Wi-Fi : 0 ou plus.")
    config.setdefault("pointage", {}).update(wifi=wifi.strip(), adresses_magasin=_liste(adresses),
                                             pause_hors_wifi_minutes=minutes)
    config.setdefault("web", {})["postes_pointage"] = _liste(postes)


def _tailscale() -> str:
    for chemin in (shutil.which("tailscale"), r"C:\Program Files\Tailscale\tailscale.exe"):
        if chemin and Path(chemin).exists():
            return chemin
    return ""


def _executer(arguments: list[str], delai: float) -> str:
    exe = _tailscale()
    if not exe:
        return ""
    try:
        r = subprocess.run([exe, *arguments], capture_output=True, text=True, timeout=delai,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _sans_port(adresse: str) -> str:
    adresse = adresse.strip()
    if adresse.startswith("["):  # [ipv6]:port
        return adresse[1:].split("]")[0]
    return adresse.rsplit(":", 1)[0] if adresse.count(":") == 1 else adresse


def adresse_du_reseau(ip_tailscale: str) -> str:
    """Adresse publique (ou locale) du réseau d'où vient l'appareil, d'après Tailscale ; « » si inconnue (relais)."""
    gardee = _MEMOIRE.get(ip_tailscale)
    if gardee and time.time() - gardee[0] < DUREE:
        return gardee[1]
    adresse = ""
    try:
        etat = json.loads(_executer(["status", "--json"], 8) or "{}")
        for pair in (etat.get("Peer") or {}).values():
            if ip_tailscale in (pair.get("TailscaleIPs") or []) and pair.get("CurAddr"):
                adresse = _sans_port(pair["CurAddr"])
    except ValueError:
        pass
    if not adresse:  # passe par un relais : un ping établit le lien direct et donne l'adresse
        m = re.search(r"via ([0-9a-fA-F.:\[\]]+:\d+)", _executer(["ping", "--c", "3", "--timeout", "3s",
                                                                   ip_tailscale], 12))
        adresse = _sans_port(m.group(1)) if m else ""
    _MEMOIRE[ip_tailscale] = (time.time(), adresse)
    return adresse


def _commence(adresse: str, motifs: list[str]) -> bool:
    return any(adresse == m or (m.endswith((".", ":")) and adresse.startswith(m)) for m in motifs)


def autorise(config: dict, ip_client: str) -> tuple[bool, str]:
    """(permis, explication). Poste du magasin listé : permis ; sinon, si des adresses du magasin sont réglées,
    l'appareil doit venir de l'une d'elles (Wi-Fi du magasin)."""
    r = reglages(config)
    if _commence(ip_client, r["postes"]):
        return True, "poste du magasin"
    if not r["adresses_magasin"]:
        if r["postes"]:
            return False, "cet appareil n'est pas un poste du magasin"
        return False, "aucun poste ni Wi-Fi du magasin n'est réglé (Administration > Automatisation)"
    if _commence(ip_client, r["adresses_magasin"]):  # serveur sur le même réseau que le Wi-Fi du magasin
        return True, "Wi-Fi du magasin"
    reseau = adresse_du_reseau(ip_client)
    if reseau and _commence(reseau, r["adresses_magasin"]):
        return True, "Wi-Fi du magasin"
    nom = f"« {r['wifi']} »" if r["wifi"] else "du magasin"
    if not reseau:
        return False, f"réseau de l'appareil inconnu : connectez-vous au Wi-Fi {nom}, puis réessayez dans un instant"
    return False, f"l'appareil n'est pas sur le Wi-Fi {nom} (réseau {reseau})"


def sur_le_wifi(config: dict, ip: str) -> bool:
    """Téléphone sur le Wi-Fi du magasin (réseau lu dans Tailscale) ; inconnu ou hors ligne : faux."""
    motifs = reglages(config)["adresses_magasin"]
    if not motifs:
        return True
    if _commence(ip, motifs):
        return True
    _MEMOIRE.pop(ip, None)  # relu à chaque contrôle
    reseau = adresse_du_reseau(ip)
    return bool(reseau) and _commence(reseau, motifs)


# ---------------------------------------------------------------- suivi des téléphones (pause automatique)
def _suivi(racine) -> Path:
    return Path(racine) / "donnees" / FICHIER_SUIVI


def lire_suivi(racine) -> dict:
    try:
        return json.loads(_suivi(racine).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire_suivi(racine, suivi: dict) -> None:
    chemin = _suivi(racine)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(suivi, ensure_ascii=False, indent=1), encoding="utf-8")


def noter_pointage(racine, config: dict, employe: str, type_: str, ip: str) -> None:
    """Après un pointage depuis un appareil qui n'est pas un poste du magasin : le téléphone est suivi tant que
    l'employé est au travail ; un départ arrête le suivi."""
    from . import paie_temps as pt

    suivi = lire_suivi(racine)
    if type_ == pt.DEPART or _commence(ip, reglages(config)["postes"]):
        suivi.pop(employe, None)
    else:
        precedent = suivi.get(employe, {})
        suivi[employe] = {"ip": ip, "hors_depuis": "", "pause_auto": precedent.get("pause_auto", False)
                          if type_ == pt.PAUSE else False}
        if type_ == pt.PAUSE:  # pause pointée par l'employé : jamais terminée par l'application
            suivi[employe]["pause_auto"] = False
    _ecrire_suivi(racine, suivi)


def controler(racine, config: dict, maintenant=None, sur_wifi=None) -> list[str]:
    """Un tour de contrôle (chaque minute) : pause après N minutes de suite hors du Wi-Fi, fin de pause au retour.
    Rend ce qui a été fait (journal)."""
    from datetime import datetime, timedelta

    from . import paie_temps as pt

    minutes = reglages(config)["pause_minutes"]
    suivi = lire_suivi(racine)
    if not minutes or not suivi:
        return []
    maintenant = maintenant or datetime.now()
    sur_wifi = sur_wifi or (lambda ip: sur_le_wifi(config, ip))
    registre = pt.Registre(racine)
    fait, change = [], False
    for employe, info in list(suivi.items()):
        etat = registre.etat_actuel(employe)
        if etat == "":  # parti (départ pointé ailleurs) : plus de suivi
            suivi.pop(employe)
            change = True
            continue
        dedans = sur_wifi(info["ip"])
        try:
            nom = registre.employe(employe).nom
        except StopIteration:
            nom = employe
        if dedans:
            if info.get("hors_depuis"):
                info["hors_depuis"], change = "", True
            if etat == pt.PAUSE and info.get("pause_auto"):
                registre.pointer_auto(employe, pt.FIN_PAUSE, maintenant, "Retour Wi-Fi",
                                      "téléphone revenu sur le Wi-Fi du magasin")
                info["pause_auto"], change = False, True
                fait.append(f"{nom} : fin de pause (retour sur le Wi-Fi) à {maintenant:%H:%M}")
            continue
        if not info.get("hors_depuis"):
            info["hors_depuis"], change = maintenant.isoformat(timespec="seconds"), True
            continue
        depuis = datetime.fromisoformat(info["hors_depuis"])
        if etat in (pt.ARRIVEE, pt.FIN_PAUSE) and maintenant - depuis >= timedelta(minutes=minutes):
            registre.pointer_auto(employe, pt.PAUSE, depuis, "Hors Wi-Fi",
                                  f"téléphone hors du Wi-Fi du magasin {minutes} min de suite")
            info["pause_auto"], change = True, True
            fait.append(f"{nom} : en pause depuis {depuis:%H:%M} (hors du Wi-Fi du magasin)")
    if change:
        _ecrire_suivi(racine, suivi)
    return fait
