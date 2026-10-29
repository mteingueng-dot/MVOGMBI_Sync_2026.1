"""Informations de l'entreprise lues dans Clover (nom, adresse, téléphone, site web) pour l'en-tête des impressions et
des PDF (demande du propriétaire du 2026-10-28). Lues au plus une fois par jour et gardées dans
donnees/entreprise_clover.json : une impression ne dépend jamais d'Internet."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

FICHIER = "entreprise_clover.json"


@dataclass
class Entreprise:
    nom: str = "Marché MVOG-MBI Sherbrooke"
    adresse: str = ""
    ville: str = ""
    telephone: str = ""
    site: str = ""
    lu_le: str = ""


def _telephone(texte: str) -> str:
    chiffres = re.sub(r"\D", "", texte or "")
    if len(chiffres) == 11 and chiffres.startswith("1"):
        chiffres = chiffres[1:]
    return f"{chiffres[:3]} {chiffres[3:6]}-{chiffres[6:]}" if len(chiffres) == 10 else (texte or "")


def depuis_clover(marchand: dict) -> Entreprise:
    """Fiche du marchand Clover (expand=address) -> informations d'en-tête, mises en forme."""
    a = marchand.get("address") or {}
    rue = ", ".join(x.strip() for x in (a.get("address1"), a.get("address2"), a.get("address3")) if x and x.strip())
    code = (a.get("zip") or "").replace(" ", "").upper()
    code = f"{code[:3]} {code[3:]}" if len(code) == 6 else code
    ville = (a.get("city") or "").strip().title()
    ville = " ".join(x for x in (f"{ville} ({a['state']})" if a.get("state") and ville else ville, code) if x)
    return Entreprise(nom=(marchand.get("name") or Entreprise.nom).strip(), adresse=rue, ville=ville,
                      telephone=_telephone(a.get("phoneNumber") or marchand.get("phoneNumber") or ""),
                      site=(marchand.get("website") or "").strip(), lu_le=date.today().isoformat())


def lire(racine: Path) -> Entreprise:
    """Informations gardées (sans Internet) ; valeurs par défaut si elles n'ont jamais été lues."""
    chemin = Path(racine) / "donnees" / FICHIER
    try:
        return Entreprise(**json.loads(chemin.read_text(encoding="utf-8")))
    except Exception:
        return Entreprise()


def actualiser(racine: Path, forcer: bool = False) -> Entreprise:
    """Relit Clover si les informations datent d'avant aujourd'hui ; en cas d'échec, garde les anciennes."""
    actuelle = lire(racine)
    if not forcer and actuelle.lu_le == date.today().isoformat():
        return actuelle
    try:
        from .__main__ import charger_config
        from .api_clover import ClientClover

        client = ClientClover(charger_config(Path(racine) / "config.toml"))
        reponse = client.session.get(client._url("").rstrip("/"), params={"expand": "address"}, timeout=30)
        reponse.raise_for_status()
        entreprise = depuis_clover(reponse.json())
    except BaseException:  # SystemExit compris (jeton absent) : l'en-tête garde les informations connues
        return actuelle
    chemin = Path(racine) / "donnees" / FICHIER
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(asdict(entreprise), ensure_ascii=False, indent=1), encoding="utf-8")
    return entreprise
